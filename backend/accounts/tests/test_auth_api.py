from datetime import timedelta

import pytest
from django.conf import settings
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User

pytestmark = pytest.mark.django_db

PASSWORD = "valid-password-2026"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/me"
COOKIE = settings.AUTH_REFRESH_COOKIE_NAME


@pytest.fixture
def user():
    return User.objects.create_user(email="taro@example.com", name="太郎", password=PASSWORD)


def login(client, email="taro@example.com", password=PASSWORD):
    return client.post(
        LOGIN, data={"email": email, "password": password}, content_type="application/json"
    )


def me(client, token=None, **headers):
    if token:
        headers["HTTP_X_ACCESS_TOKEN"] = token
    return client.get(ME, **headers)


class TestLogin:
    def test_returns_access_token_and_user(self, client, user):
        response = login(client)

        assert response.status_code == 200
        body = response.json()
        assert body["access"]
        assert body["user"] == {
            "id": user.id,
            "email": "taro@example.com",
            "name": "太郎",
            "is_admin": False,
        }
        assert "refresh" not in body  # リフレッシュトークンはJSONに含めない

    def test_sets_refresh_token_in_http_only_cookie(self, client, user):
        response = login(client)

        cookie = response.cookies[COOKIE]
        assert cookie.value
        assert cookie["httponly"]
        assert cookie["samesite"] == "Lax"
        assert cookie["path"] == "/api/v1/auth"
        assert cookie["max-age"] == 7 * 24 * 60 * 60
        assert bool(cookie["secure"]) == settings.AUTH_COOKIE_SECURE

    def test_email_is_case_insensitive(self, client, user):
        assert login(client, email="TARO@Example.COM").status_code == 200

    def test_updates_last_login(self, client, user):
        assert user.last_login is None

        login(client)

        user.refresh_from_db()
        assert user.last_login is not None

    def test_failures_return_same_response(self, client, user):
        inactive = User.objects.create_user(email="off@example.com", name="停止", password=PASSWORD)
        inactive.is_active = False
        inactive.save()

        responses = [
            login(client, password="wrong-password-2026"),  # パスワード違い
            login(client, email="nobody@example.com"),  # 未登録
            login(client, email="off@example.com"),  # 無効化済み
            client.post(LOGIN, data={}, content_type="application/json"),  # 入力なし
        ]

        for response in responses:
            assert response.status_code == 401
            assert response.json() == responses[0].json()
        assert responses[0].json()["error"]["code"] == "INVALID_CREDENTIALS"
        assert COOKIE not in responses[0].cookies


class TestMe:
    def test_returns_user_with_valid_token(self, client, user):
        token = login(client).json()["access"]

        response = me(client, token)

        assert response.status_code == 200
        assert response.json()["email"] == "taro@example.com"

    def test_requires_token(self, client, user):
        response = me(client)

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"

    def test_rejects_invalid_token(self, client, user):
        response = me(client, "invalid-token")

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "TOKEN_INVALID"

    def test_rejects_expired_token(self, client, user):
        token = AccessToken.for_user(user)
        token.set_exp(lifetime=timedelta(seconds=-1))

        response = me(client, str(token))

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "TOKEN_INVALID"

    def test_ignores_authorization_header(self, client, user):
        # Basic認証を前段に置いても干渉しないよう、Authorization ヘッダは使わない
        token = login(client).json()["access"]

        response = me(client, HTTP_AUTHORIZATION=f"Bearer {token}")

        assert response.status_code == 401

    def test_reflects_permission_change_immediately(self, client, user):
        token = login(client).json()["access"]
        assert me(client, token).json()["is_admin"] is False

        user.is_admin = True
        user.save()

        assert me(client, token).json()["is_admin"] is True

    def test_rejects_token_of_deactivated_user(self, client, user):
        token = login(client).json()["access"]

        user.is_active = False
        user.save()

        assert me(client, token).status_code == 401


class TestRefresh:
    def test_issues_new_access_token_and_rotates_refresh_token(self, client, user):
        old_refresh = login(client).cookies[COOKIE].value

        response = client.post(REFRESH)

        assert response.status_code == 200
        assert me(client, response.json()["access"]).status_code == 200
        assert response.cookies[COOKIE].value != old_refresh

    def test_requires_cookie(self, client, user):
        response = client.post(REFRESH)

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "REFRESH_INVALID"

    def test_used_refresh_token_cannot_be_reused(self, client, user):
        old_refresh = login(client).cookies[COOKIE].value
        client.post(REFRESH)

        client.cookies[COOKIE] = old_refresh
        response = client.post(REFRESH)

        assert response.status_code == 401

    def test_reuse_revokes_all_tokens_of_the_user(self, client, user):
        old_refresh = login(client).cookies[COOKIE].value
        new_refresh = client.post(REFRESH).cookies[COOKIE].value

        client.cookies[COOKIE] = old_refresh  # 盗まれた古いトークンが使われた想定
        client.post(REFRESH)

        client.cookies[COOKIE] = new_refresh  # 正規の最新トークンも使えなくなる
        assert client.post(REFRESH).status_code == 401

    def test_rejects_deactivated_user(self, client, user):
        login(client)
        user.is_active = False
        user.save()

        assert client.post(REFRESH).status_code == 401

    def test_rejects_garbage_cookie(self, client, user):
        client.cookies[COOKIE] = "garbage"

        assert client.post(REFRESH).status_code == 401


class TestLogout:
    def test_deletes_cookie_and_invalidates_refresh_token(self, client, user):
        refresh = login(client).cookies[COOKIE].value

        response = client.post(LOGOUT)

        assert response.status_code == 204
        assert response.cookies[COOKIE].value == ""
        client.cookies[COOKIE] = refresh
        assert client.post(REFRESH).status_code == 401

    def test_succeeds_without_cookie(self, client, user):
        assert client.post(LOGOUT).status_code == 204
