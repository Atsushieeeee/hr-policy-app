import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from chat.models import ChatMessage, ChatSession
from faq.models import FAQ

pytestmark = pytest.mark.django_db

URL = "/api/v1/admin/faq-candidates"
SOURCES = [{"policy_id": 1, "article": "第7条", "page": 2}]


def make_user(name, is_admin=False):
    return User.objects.create_user(
        email=f"{name}@example.com", name=name, password="valid-password-2026", is_admin=is_admin
    )


@pytest.fixture
def admin_user():
    return make_user("admin", is_admin=True)


@pytest.fixture
def admin(admin_user):
    client = APIClient()
    client.credentials(HTTP_X_ACCESS_TOKEN=str(AccessToken.for_user(admin_user)))
    return client


def ask(user, question, answer="回答です", sources=SOURCES, no_answer=False, session=None):
    """質問と回答を、1往復、保存する。回答のメッセージを返す。"""
    from chat.services import hash_question, normalize_question

    session = session or ChatSession.objects.create(user=user)
    normalized = normalize_question(question)
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.USER,
        content=question,
        normalized_question=normalized,
        question_hash=hash_question(normalized),
    )
    return ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content=answer,
        sources=sources,
        is_no_answer=no_answer,
    )


def candidates(admin, **params):
    return admin.get(URL, params).json()


class TestGrouping:
    def test_groups_questions_that_differ_only_in_notation(self, admin):
        user = make_user("a")
        ask(user, "有給は何日？")
        ask(user, "有給は何日")
        ask(user, "有給は何日？？")

        body = candidates(admin)

        assert body["count"] == 1
        assert body["results"][0]["ask_count"] == 3

    def test_orders_by_ask_count_then_most_recent(self, admin):
        user = make_user("a")
        ask(user, "少ない質問")
        for _ in range(3):
            ask(user, "多い質問")
        ask(user, "同数の新しい質問")

        questions = [c["question"] for c in candidates(admin)["results"]]

        assert questions == ["多い質問", "同数の新しい質問", "少ない質問"]

    def test_counts_distinct_users(self, admin):
        a, b = make_user("a"), make_user("b")
        ask(a, "有給は何日？")
        ask(a, "有給は何日？")
        ask(b, "有給は何日？")

        result = candidates(admin)["results"][0]

        assert (result["ask_count"], result["user_count"]) == (3, 2)

    def test_uses_the_latest_useful_answer(self, admin):
        user = make_user("a")
        ask(user, "有給は何日？", answer="古い回答")
        newest = ask(user, "有給は何日", answer="新しい回答")

        result = candidates(admin)["results"][0]

        assert result["answer"] == "新しい回答"
        assert result["question"] == "有給は何日"
        assert result["source_message_id"] == newest.id
        assert result["sources"] == SOURCES

    def test_skips_answers_without_sources_when_picking_the_answer(self, admin):
        user = make_user("a")
        useful = ask(user, "有給は何日？", answer="根拠つきの回答")
        ask(user, "有給は何日？", answer="該当なし", sources=[], no_answer=True)

        result = candidates(admin)["results"][0]

        assert result["answer"] == "根拠つきの回答"
        assert result["source_message_id"] == useful.id
        assert result["ask_count"] == 2


class TestExclusion:
    def test_excludes_no_answer_questions(self, admin):
        ask(make_user("a"), "副業は？", answer="該当なし", sources=[], no_answer=True)

        assert candidates(admin)["count"] == 0

    def test_excludes_answers_without_sources(self, admin):
        ask(make_user("a"), "質問", answer="根拠のない回答", sources=[])

        assert candidates(admin)["count"] == 0

    def test_ignores_a_question_without_an_answer(self, admin):
        session = ChatSession.objects.create(user=make_user("a"))
        ChatMessage.objects.create(
            session=session,
            role=ChatMessage.Role.USER,
            content="答えのない質問",
            normalized_question="答えのない質問",
            question_hash="x" * 64,
        )

        assert candidates(admin)["count"] == 0

    def test_answer_is_the_reply_to_that_question_in_the_same_session(self, admin):
        a, b = make_user("a"), make_user("b")
        first = ask(a, "質問1", answer="aの回答1")
        ask(b, "質問2", answer="bの回答")
        ask(a, "質問2", answer="aの回答2", session=first.session)

        by_question = {c["question"]: c["answer"] for c in candidates(admin)["results"]}

        assert by_question["質問1"] == "aの回答1"
        assert by_question["質問2"] == "aの回答2"

    def test_excludes_registered_questions_by_source_message(self, admin, admin_user):
        user = make_user("a")
        reply = ask(user, "有給は何日？")
        ask(user, "別の質問")
        FAQ.objects.create(
            question="年次有給休暇は何日付与されますか？",
            answer="10日",
            source_message=reply,
            created_by=admin_user,
        )

        body = candidates(admin)

        assert [c["question"] for c in body["results"]] == ["別の質問"]

    def test_excludes_registered_questions_by_question_text(self, admin, admin_user):
        ask(make_user("a"), "有給は何日？")
        FAQ.objects.create(question="有給は何日", answer="10日", created_by=admin_user)

        assert candidates(admin)["count"] == 0

    def test_include_registered_shows_them_with_a_flag(self, admin, admin_user):
        user = make_user("a")
        reply = ask(user, "有給は何日？")
        ask(user, "別の質問")
        FAQ.objects.create(question="x", answer="y", source_message=reply, created_by=admin_user)

        body = candidates(admin, include_registered="true")

        flags = {c["question"]: c["registered"] for c in body["results"]}
        assert flags == {"有給は何日？": True, "別の質問": False}


class TestResponse:
    def test_does_not_expose_who_asked(self, admin):
        user = make_user("secret-person")
        ask(user, "有給は何日？")

        response = admin.get(URL)

        text = response.content.decode()
        assert user.email not in text
        assert user.name not in text
        assert set(response.json()["results"][0]) == {
            "question",
            "ask_count",
            "user_count",
            "last_asked_at",
            "answer",
            "sources",
            "source_message_id",
            "registered",
        }

    def test_paginates(self, admin):
        user = make_user("a")
        for i in range(3):
            ask(user, f"質問{i}")

        body = candidates(admin, page_size=2, page=2)

        assert (body["count"], body["page"], body["page_size"]) == (3, 2, 2)
        assert len(body["results"]) == 1

    def test_empty(self, admin):
        assert candidates(admin) == {"count": 0, "page": 1, "page_size": 20, "results": []}
