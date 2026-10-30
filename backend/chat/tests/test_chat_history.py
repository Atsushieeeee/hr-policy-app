from unittest.mock import patch

import pytest
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from chat.models import ChatMessage, ChatSession
from chat.services import hash_question, normalize_question
from rag.base import Answer, RagError, Source

pytestmark = pytest.mark.django_db

URL = "/api/v1/chat/messages"


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


def ask(client, user, question="有給休暇は何日ですか？", **extra):
    return client.post(
        URL,
        data={"question": question, **extra},
        content_type="application/json",
        HTTP_X_ACCESS_TOKEN=str(AccessToken.for_user(user)),
    )


class TestSave:
    def test_first_question_creates_a_session_and_saves_both_messages(
        self, client, taro, registered_policy
    ):
        response = ask(client, taro)

        assert response.status_code == 200
        body = response.json()
        session = ChatSession.objects.get()
        assert session.user == taro
        assert body["session_id"] == session.id
        question, reply = ChatMessage.objects.order_by("id")
        assert (question.role, question.content) == ("user", "有給休暇は何日ですか？")
        assert question.normalized_question == "有給休暇は何日ですか"
        assert question.question_hash == hash_question("有給休暇は何日ですか")
        assert reply.role == "assistant"
        assert reply.content == body["answer"]
        assert reply.id == body["message_id"]
        assert reply.sources == [{"policy_id": registered_policy.id, "article": "第7条", "page": 2}]
        assert reply.is_no_answer is False
        assert reply.feedback is None

    def test_answer_is_saved_without_question_fields(self, client, taro):
        ask(client, taro)

        reply = ChatMessage.objects.get(role="assistant")

        assert reply.normalized_question == ""
        assert reply.question_hash == ""

    def test_follow_up_continues_the_same_session(self, client, taro):
        first = ask(client, taro).json()

        second = ask(client, taro, "それは何日までですか？", session_id=first["session_id"]).json()

        assert second["session_id"] == first["session_id"]
        assert ChatSession.objects.count() == 1
        assert ChatMessage.objects.filter(session_id=first["session_id"]).count() == 4

    def test_without_session_id_a_new_session_is_started_each_time(self, client, taro):
        ask(client, taro)
        ask(client, taro)

        assert ChatSession.objects.count() == 2

    def test_not_found_answer_is_saved_as_no_answer(self, client, taro):
        answer = Answer(text="見つかりませんでした", sources=[], found=False)
        with patch("chat.views.get_rag_client") as get_client:
            get_client.return_value.answer.return_value = answer
            ask(client, taro)

        reply = ChatMessage.objects.get(role="assistant")
        assert reply.is_no_answer is True
        assert reply.sources == []

    def test_multiple_sources_are_saved(self, client, taro, registered_policy):
        answer = Answer(text="回答", sources=[Source("第1条", 1), Source("第2条", None)])
        with patch("chat.views.get_rag_client") as get_client:
            get_client.return_value.answer.return_value = answer
            ask(client, taro)

        sources = ChatMessage.objects.get(role="assistant").sources
        assert sources == [
            {"policy_id": registered_policy.id, "article": "第1条", "page": 1},
            {"policy_id": registered_policy.id, "article": "第2条", "page": None},
        ]


class TestNothingIsSavedOnFailure:
    def test_ai_error_does_not_create_a_session(self, client, taro):
        error = RagError("AIでエラー", code="AI_ERROR", status=502)
        with patch("chat.views.get_rag_client") as get_client:
            get_client.return_value.answer.side_effect = error
            response = ask(client, taro)

        assert response.status_code == 502
        assert ChatSession.objects.count() == 0
        assert ChatMessage.objects.count() == 0

    def test_ai_error_in_an_existing_session_saves_nothing_more(self, client, taro):
        session_id = ask(client, taro).json()["session_id"]
        error = RagError("AIでエラー", code="AI_ERROR", status=502)
        with patch("chat.views.get_rag_client") as get_client:
            get_client.return_value.answer.side_effect = error
            ask(client, taro, "追質問", session_id=session_id)

        assert ChatMessage.objects.count() == 2

    def test_unregistered_policy_does_not_create_a_session(self, client, taro, registered_policy):
        registered_policy.delete()

        response = ask(client, taro)

        assert response.status_code == 409
        assert ChatSession.objects.count() == 0

    def test_invalid_question_does_not_create_a_session(self, client, taro):
        assert ask(client, taro, "").status_code == 400
        assert ChatSession.objects.count() == 0


class TestSessionOwnership:
    def test_other_users_session_is_not_found(self, client, taro):
        session_id = ask(client, taro).json()["session_id"]
        hanako = make_user("hanako")

        with patch("chat.views.get_rag_client") as get_client:
            response = ask(client, hanako, "質問", session_id=session_id)

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
        get_client.assert_not_called()  # AIを呼ばない
        assert ChatMessage.objects.count() == 2

    def test_missing_session_is_not_found(self, client, taro):
        response = ask(client, taro, session_id=99999)

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    @pytest.mark.parametrize("session_id", ["abc", 0, -1, None])
    def test_invalid_session_id_is_rejected(self, client, taro, session_id):
        response = ask(client, taro, session_id=session_id)

        assert response.status_code == 400
        assert ChatSession.objects.count() == 0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("有給休暇は何日ですか？", "有給休暇は何日ですか"),
        ("有給休暇は何日ですか", "有給休暇は何日ですか"),
        ("  有給休暇は   何日ですか?  ", "有給休暇は 何日ですか"),
        ("有給休暇は　何日ですか。", "有給休暇は 何日ですか"),
        ("ＡＢＣ　Ｄｅｆ？？", "abc def"),
        ("Paid Leave?", "paid leave"),
        ("？", ""),
        ("   ", ""),
        ("1.5日?", "1.5日"),
    ],
)
def test_normalize_question(text, expected):
    assert normalize_question(text) == expected


def test_same_question_in_different_notations_has_the_same_hash():
    a = hash_question(normalize_question("有給休暇は何日ですか？"))
    b = hash_question(normalize_question("  有給休暇は何日ですか "))

    assert a == b
    assert len(a) == 64


def test_empty_question_has_no_hash():
    assert hash_question(normalize_question("？")) == ""
