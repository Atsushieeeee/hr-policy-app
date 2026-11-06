import re

import pytest
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User
from accounts.permissions import HasAdminPermission
from config.urls import admin_urlpatterns
from core.views import AdminAPIView

pytestmark = pytest.mark.django_db

PASSWORD = "valid-password-2026"
PING = "/api/v1/admin/ping"


@pytest.fixture
def admin_user():
    return User.objects.create_user(
        email="admin@example.com", name="管理者権限あり", password=PASSWORD, is_admin=True
    )


@pytest.fixture
def normal_user():
    return User.objects.create_user(
        email="normal@example.com", name="管理者権限なし", password=PASSWORD
    )


def token_of(user):
    return str(AccessToken.for_user(user))


def get(client, url, user=None, token=None):
    headers = {}
    if user is not None:
        token = token_of(user)
    if token:
        headers["HTTP_X_ACCESS_TOKEN"] = token
    return client.get(url, **headers)


class TestAdminApiAccess:
    def test_unauthenticated_gets_401(self, client):
        response = get(client, PING)

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"

    def test_user_without_admin_permission_gets_403(self, client, normal_user):
        response = get(client, PING, user=normal_user)

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"

    def test_user_with_admin_permission_succeeds(self, client, admin_user):
        response = get(client, PING, user=admin_user)

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_invalid_token_gets_401(self, client):
        response = get(client, PING, token="invalid-token")

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "TOKEN_INVALID"

    def test_deactivated_admin_gets_401(self, client, admin_user):
        token = token_of(admin_user)
        admin_user.is_active = False
        admin_user.save()

        assert get(client, PING, token=token).status_code == 401


class TestPermissionChangeIsReflectedImmediately:
    def test_revoking_admin_permission_takes_effect_with_the_same_token(self, client, admin_user):
        token = token_of(admin_user)
        assert get(client, PING, token=token).status_code == 200

        admin_user.is_admin = False
        admin_user.save()

        assert get(client, PING, token=token).status_code == 403

    def test_granting_admin_permission_takes_effect_with_the_same_token(self, client, normal_user):
        token = token_of(normal_user)
        assert get(client, PING, token=token).status_code == 403

        normal_user.is_admin = True
        normal_user.save()

        assert get(client, PING, token=token).status_code == 200


def _admin_endpoints():
    """/admin/ 配下に登録されたすべてのAPIと、それぞれが受け付けるメソッド。"""
    endpoints = []
    for pattern in admin_urlpatterns:
        view_class = pattern.callback.cls
        methods = [m for m in ("get", "post", "put", "patch", "delete") if hasattr(view_class, m)]
        endpoints.extend((str(pattern.pattern), view_class, m) for m in methods)
    return endpoints


@pytest.mark.parametrize(
    ("path", "view_class", "method"),
    _admin_endpoints(),
    ids=lambda v: v if isinstance(v, str) else getattr(v, "__name__", str(v)),
)
class TestEveryAdminEndpointIsProtected:
    """管理者用APIを追加したときに、権限の付け忘れを自動で検出する。"""

    def test_requires_admin_permission_class(self, path, view_class, method):
        assert issubclass(view_class, AdminAPIView)
        assert HasAdminPermission in view_class.permission_classes

    def test_permission_matrix(self, client, admin_user, normal_user, path, view_class, method):
        # パスに、<int:pk> のような部分があれば、実在しうる値（1）に置き換える
        url = "/api/v1/admin/" + re.sub(r"<[^>]+>", "1", path)
        call = getattr(client, method)

        unauthenticated = call(url)
        without_permission = call(url, HTTP_X_ACCESS_TOKEN=token_of(normal_user))
        with_permission = call(url, HTTP_X_ACCESS_TOKEN=token_of(admin_user))

        assert unauthenticated.status_code == 401
        assert without_permission.status_code == 403
        assert with_permission.status_code not in (401, 403)
