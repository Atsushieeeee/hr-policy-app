import pytest
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User

pytestmark = pytest.mark.django_db

URL = "/api/v1/chat/messages"


@pytest.fixture(autouse=True)
def setup(settings, clock):
    settings.RAG_BACKEND = "fake"  # AIは呼ばない


def make_user(name):
    return User.objects.create_user(
        email=f"{name}@example.com", name=name, password="valid-password-2026"
    )


def ask(client, user, question="質問"):
    return client.post(
        URL,
        data={"question": question},
        content_type="application/json",
        HTTP_X_ACCESS_TOKEN=str(AccessToken.for_user(user)),
    )


class TestPerUserLimit:
    def test_blocks_the_11th_request_within_a_minute(self, client):
        user = make_user("taro")
        for _ in range(10):
            assert ask(client, user).status_code == 200

        response = ask(client, user)

        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"
        assert int(response["Retry-After"]) > 0

    def test_other_users_are_not_affected(self, client):
        taro, hanako = make_user("taro"), make_user("hanako")
        for _ in range(11):
            ask(client, taro)

        assert ask(client, hanako).status_code == 200

    def test_limit_is_lifted_after_a_minute(self, client, clock):
        user = make_user("taro")
        for _ in range(11):
            ask(client, user)

        clock.advance(61)

        assert ask(client, user).status_code == 200

    def test_daily_limit(self, client, clock, set_rate):
        set_rate("chat_day", "3/day")
        user = make_user("taro")
        for _ in range(3):
            assert ask(client, user).status_code == 200

        assert ask(client, user).status_code == 429
        clock.advance(24 * 60 * 60 + 1)
        assert ask(client, user).status_code == 200

    def test_unauthenticated_requests_are_rejected_before_counting(self, client):
        for _ in range(15):
            response = client.post(URL, data={"question": "質問"}, content_type="application/json")

            assert response.status_code == 401


class TestAiGlobalLimit:
    def test_limit_is_shared_by_all_users(self, client, set_rate):
        set_rate("ai_global_minute", "2/min")
        taro, hanako = make_user("taro"), make_user("hanako")

        assert ask(client, taro).status_code == 200
        assert ask(client, hanako).status_code == 200
        response = ask(client, taro)

        assert response.status_code == 429
        error = response.json()["error"]
        assert error["code"] == "AI_BUSY"
        assert "AIが混み合っています" in error["message"]
        assert int(response["Retry-After"]) > 0

    def test_limit_is_lifted_after_a_minute(self, client, clock, set_rate):
        set_rate("ai_global_minute", "1/min")
        user = make_user("taro")
        ask(client, user)
        assert ask(client, user).status_code == 429

        clock.advance(61)

        assert ask(client, user).status_code == 200

    def test_global_daily_limit(self, client, clock, set_rate):
        set_rate("ai_global_day", "2/day")
        user = make_user("taro")
        assert ask(client, user).status_code == 200
        clock.advance(61)
        assert ask(client, user).status_code == 200
        clock.advance(61)

        response = ask(client, user)

        assert response.status_code == 429
        assert response.json()["error"]["code"] == "AI_BUSY"

    def test_invalid_questions_do_not_consume_the_ai_budget(self, client, set_rate):
        set_rate("ai_global_minute", "2/min")
        user = make_user("taro")
        for _ in range(3):
            assert ask(client, user, question="").status_code == 400

        assert ask(client, user).status_code == 200
        assert ask(client, user).status_code == 200
        assert ask(client, user).status_code == 429
