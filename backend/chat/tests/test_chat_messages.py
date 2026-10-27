from unittest.mock import patch

import pytest
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from rag.base import RagError

pytestmark = pytest.mark.django_db

URL = "/api/v1/chat/messages"
PASSWORD = "valid-password-2026"


@pytest.fixture(autouse=True)
def use_fake_rag(settings, registered_policy):
    # テストではAIを呼ばず、固定の回答を返す実装を使う。規程は、登録済みにしておく
    settings.RAG_BACKEND = "fake"


@pytest.fixture
def user():
    return User.objects.create_user(email="taro@example.com", name="太郎", password=PASSWORD)


@pytest.fixture
def logged_in(client, user):
    """ログイン済みの状態（以降のリクエストに、アクセストークンが付く）。"""
    client.defaults["HTTP_X_ACCESS_TOKEN"] = str(AccessToken.for_user(user))
    return client


def post(client, body):
    return client.post(URL, data=body, content_type="application/json")


class TestAuthentication:
    def test_requires_login(self, client):
        with patch("chat.views.get_rag_client") as get_client:
            response = post(client, {"question": "有給休暇は何日ですか？"})

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"
        get_client.assert_not_called()  # 認証に失敗したときは、AIを呼ばない

    def test_rejects_invalid_token(self, client):
        client.defaults["HTTP_X_ACCESS_TOKEN"] = "invalid-token"

        with patch("chat.views.get_rag_client") as get_client:
            response = post(client, {"question": "有給休暇は何日ですか？"})

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "TOKEN_INVALID"
        get_client.assert_not_called()

    def test_rejects_deactivated_user(self, logged_in, user):
        user.is_active = False
        user.save()

        assert post(logged_in, {"question": "質問"}).status_code == 401

    @pytest.mark.parametrize("is_admin", [False, True])
    def test_available_regardless_of_admin_permission(self, client, is_admin):
        member = User.objects.create_user(
            email="member@example.com", name="利用者", password=PASSWORD, is_admin=is_admin
        )
        client.defaults["HTTP_X_ACCESS_TOKEN"] = str(AccessToken.for_user(member))

        assert post(client, {"question": "質問"}).status_code == 200


def test_returns_answer_with_sources(logged_in):
    response = post(logged_in, {"question": "有給休暇は何日ですか？"})

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert "有給休暇は何日ですか？" in body["answer"]
    assert body["sources"] == [{"article": "第7条", "page": 2}]


@pytest.mark.parametrize("question", ["", "   ", "あ" * 1001])
def test_rejects_invalid_question(logged_in, question):
    response = post(logged_in, {"question": question})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_rejects_missing_question(logged_in):
    response = post(logged_in, {})

    assert response.status_code == 400


def test_accepts_question_of_max_length(logged_in):
    response = post(logged_in, {"question": "あ" * 1000})

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("status", "code"),
    [(429, "AI_RATE_LIMITED"), (503, "AI_UNAVAILABLE"), (502, "AI_ERROR")],
)
def test_returns_ai_error_with_matching_status(logged_in, status, code):
    error = RagError("AIでエラー", code=code, status=status)
    with patch("chat.views.get_rag_client") as get_client:
        get_client.return_value.answer.side_effect = error
        response = post(logged_in, {"question": "質問"})

    assert response.status_code == status
    assert response.json() == {"error": {"code": code, "message": "AIでエラー"}}
