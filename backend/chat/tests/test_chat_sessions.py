import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from chat.models import ChatMessage, ChatSession
from chat.services import MAX_HISTORY_MESSAGES

pytestmark = pytest.mark.django_db

CURRENT = "/api/v1/chat/sessions/current"
SESSIONS = "/api/v1/chat/sessions"
MESSAGES = "/api/v1/chat/messages"


@pytest.fixture(autouse=True)
def use_fake_rag(settings, registered_policy):
    settings.RAG_BACKEND = "fake"


def make_user(name):
    return User.objects.create_user(
        email=f"{name}@example.com", name=name, password="valid-password-2026"
    )


@pytest.fixture
def taro():
    return make_user("taro")


def api(user=None):
    client = APIClient()
    if user is not None:
        client.credentials(HTTP_X_ACCESS_TOKEN=str(AccessToken.for_user(user)))
    return client


def add_exchange(session, question, found=True, sources=None):
    ChatMessage.objects.create(session=session, role="user", content=question)
    ChatMessage.objects.create(
        session=session,
        role="assistant",
        content=f"{question}への回答",
        is_no_answer=not found,
        sources=sources or [],
    )


class TestAccess:
    def test_requires_login(self):
        assert api().get(CURRENT).status_code == 401
        assert api().post(SESSIONS).status_code == 401


class TestCurrentSession:
    def test_no_session_yet(self, taro):
        response = api(taro).get(CURRENT)

        assert response.status_code == 200
        assert response.json() == {"session_id": None, "messages": []}

    def test_returns_messages_oldest_first(self, taro):
        session = ChatSession.objects.create(user=taro)
        add_exchange(session, "質問1")
        add_exchange(session, "質問2")

        body = api(taro).get(CURRENT).json()

        assert body["session_id"] == session.id
        assert [m["content"] for m in body["messages"]] == [
            "質問1",
            "質問1への回答",
            "質問2",
            "質問2への回答",
        ]
        assert [m["role"] for m in body["messages"]] == ["user", "assistant"] * 2

    def test_message_fields(self, taro):
        session = ChatSession.objects.create(user=taro)
        add_exchange(
            session,
            "質問",
            sources=[{"policy_id": 5, "article": "第7条", "page": 2}],
        )

        question, reply = api(taro).get(CURRENT).json()["messages"]

        assert set(question) == {"id", "role", "content", "found", "sources", "created_at"}
        assert question["found"] is None
        assert reply["found"] is True
        # 内部の値（policy_id）は返さない
        assert reply["sources"] == [{"article": "第7条", "page": 2}]

    def test_no_answer_reply_has_found_false(self, taro):
        session = ChatSession.objects.create(user=taro)
        add_exchange(session, "質問", found=False)

        reply = api(taro).get(CURRENT).json()["messages"][1]

        assert reply["found"] is False

    def test_returns_only_the_latest_session(self, taro):
        old = ChatSession.objects.create(user=taro)
        add_exchange(old, "古い会話")
        latest = ChatSession.objects.create(user=taro)
        add_exchange(latest, "新しい会話")

        body = api(taro).get(CURRENT).json()

        assert body["session_id"] == latest.id
        assert body["messages"][0]["content"] == "新しい会話"

    def test_empty_latest_session_is_returned_as_empty(self, taro):
        old = ChatSession.objects.create(user=taro)
        add_exchange(old, "古い会話")
        empty = ChatSession.objects.create(user=taro)

        assert api(taro).get(CURRENT).json() == {"session_id": empty.id, "messages": []}

    def test_does_not_return_other_users_session(self, taro):
        other = make_user("hanako")
        add_exchange(ChatSession.objects.create(user=other), "他人の質問")

        assert api(taro).get(CURRENT).json() == {"session_id": None, "messages": []}

    def test_limits_to_the_latest_messages_in_order(self, taro):
        session = ChatSession.objects.create(user=taro)
        for i in range(MAX_HISTORY_MESSAGES // 2 + 5):
            add_exchange(session, f"質問{i}")

        messages = api(taro).get(CURRENT).json()["messages"]

        assert len(messages) == MAX_HISTORY_MESSAGES
        assert messages[-1]["content"] == f"質問{MAX_HISTORY_MESSAGES // 2 + 4}への回答"
        ids = [m["id"] for m in messages]
        assert ids == sorted(ids)


class TestNewSession:
    def test_creates_a_session_that_becomes_the_latest(self, taro):
        add_exchange(ChatSession.objects.create(user=taro), "古い会話")

        response = api(taro).post(SESSIONS)

        assert response.status_code == 201
        session_id = response.json()["session_id"]
        assert api(taro).get(CURRENT).json() == {"session_id": session_id, "messages": []}

    def test_first_session_is_created(self, taro):
        response = api(taro).post(SESSIONS)

        assert response.status_code == 201
        assert ChatSession.objects.filter(user=taro).count() == 1

    def test_reuses_the_latest_session_when_it_is_still_empty(self, taro):
        first = api(taro).post(SESSIONS).json()["session_id"]

        response = api(taro).post(SESSIONS)

        assert response.status_code == 200
        assert response.json()["session_id"] == first
        assert ChatSession.objects.filter(user=taro).count() == 1

    def test_question_after_new_session_goes_into_it(self, taro):
        add_exchange(ChatSession.objects.create(user=taro), "古い会話")
        session_id = api(taro).post(SESSIONS).json()["session_id"]

        response = api(taro).post(
            MESSAGES, {"question": "新しい質問", "session_id": session_id}, format="json"
        )

        assert response.json()["session_id"] == session_id
        body = api(taro).get(CURRENT).json()
        assert body["session_id"] == session_id
        assert body["messages"][0]["content"] == "新しい質問"

    def test_does_not_affect_other_users(self, taro):
        other = make_user("hanako")
        add_exchange(ChatSession.objects.create(user=other), "他人の質問")

        api(taro).post(SESSIONS)

        assert api(other).get(CURRENT).json()["messages"][0]["content"] == "他人の質問"
