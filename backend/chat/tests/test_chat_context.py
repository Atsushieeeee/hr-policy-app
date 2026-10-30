from unittest.mock import patch

import pytest
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from chat.models import ChatMessage, ChatSession
from chat.services import recent_history
from rag.base import Answer, Turn

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


def ask(client, user, question, **extra):
    return client.post(
        URL,
        data={"question": question, **extra},
        content_type="application/json",
        HTTP_X_ACCESS_TOKEN=str(AccessToken.for_user(user)),
    )


def add_turns(session, count, found=True):
    for i in range(1, count + 1):
        ChatMessage.objects.create(session=session, role="user", content=f"質問{i}")
        ChatMessage.objects.create(
            session=session, role="assistant", content=f"回答{i}", is_no_answer=not found
        )


class TestHistoryPassedToAi:
    def test_first_question_has_empty_history(self, client, taro):
        with patch("chat.views.get_rag_client") as get_client:
            get_client.return_value.answer.return_value = Answer(text="回答")
            ask(client, taro, "有給休暇は何日ですか？")

        assert get_client.return_value.answer.call_args.args[2] == []

    def test_follow_up_receives_previous_turns_in_order(self, client, taro):
        session_id = ask(client, taro, "有給休暇は何日ですか？").json()["session_id"]
        first_answer = ChatMessage.objects.get(role="assistant").content
        with patch("chat.views.get_rag_client") as get_client:
            get_client.return_value.answer.return_value = Answer(text="回答")
            ask(client, taro, "それは何日までですか？", session_id=session_id)

        history = get_client.return_value.answer.call_args.args[2]
        assert history == [Turn("有給休暇は何日ですか？", first_answer)]

    def test_new_session_does_not_receive_previous_conversation(self, client, taro):
        ask(client, taro, "最初の会話")
        with patch("chat.views.get_rag_client") as get_client:
            get_client.return_value.answer.return_value = Answer(text="回答")
            ask(client, taro, "別の会話")

        assert get_client.return_value.answer.call_args.args[2] == []

    def test_history_is_not_included_when_the_ai_call_is_blocked_by_missing_session(
        self, client, taro
    ):
        other = make_user("hanako")
        session = ChatSession.objects.create(user=other)
        add_turns(session, 1)

        with patch("chat.views.get_rag_client") as get_client:
            response = ask(client, taro, "質問", session_id=session.id)

        assert response.status_code == 404
        get_client.assert_not_called()


class TestRecentHistory:
    def test_none_session_has_no_history(self):
        assert recent_history(None) == []

    def test_returns_only_the_latest_n_turns_oldest_first(self, taro, settings):
        settings.CHAT_CONTEXT_TURNS = 3
        session = ChatSession.objects.create(user=taro)
        add_turns(session, 5)

        history = recent_history(session)

        assert history == [Turn("質問3", "回答3"), Turn("質問4", "回答4"), Turn("質問5", "回答5")]

    def test_default_is_five_turns(self, taro):
        session = ChatSession.objects.create(user=taro)
        add_turns(session, 8)

        assert [t.question for t in recent_history(session)] == [f"質問{i}" for i in range(4, 9)]

    def test_does_not_include_other_sessions(self, taro):
        mine = ChatSession.objects.create(user=taro)
        other = ChatSession.objects.create(user=make_user("hanako"))
        add_turns(mine, 1)
        add_turns(other, 2)

        assert recent_history(mine) == [Turn("質問1", "回答1")]

    def test_not_found_turns_are_included(self, taro):
        session = ChatSession.objects.create(user=taro)
        add_turns(session, 1, found=False)

        assert recent_history(session) == [Turn("質問1", "回答1")]

    def test_zero_turns_disables_context(self, taro, settings):
        settings.CHAT_CONTEXT_TURNS = 0
        session = ChatSession.objects.create(user=taro)
        add_turns(session, 2)

        assert recent_history(session) == []
