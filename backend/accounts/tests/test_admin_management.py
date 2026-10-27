import threading

import pytest
from django.db import connection
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.admin_services import revoke_admin
from accounts.exceptions import LastAdmin
from accounts.models import User

pytestmark = pytest.mark.django_db

ADMINS = "/api/v1/admin/admins"
REVOKE = "/api/v1/admin/admins/revoke"
USERS = "/api/v1/admin/users"
PASSWORD = "valid-password-2026"


def make_user(name, is_admin=False, is_active=True):
    user = User.objects.create_user(
        email=f"{name}@example.com", name=name, password=PASSWORD, is_admin=is_admin
    )
    if not is_active:
        user.is_active = False
        user.save()
    return user


def api(user=None):
    client = APIClient()
    if user is not None:
        client.credentials(HTTP_X_ACCESS_TOKEN=str(AccessToken.for_user(user)))
    return client


def is_admin(user):
    User.objects.get(id=user.id).refresh_from_db()
    return User.objects.get(id=user.id).is_admin


@pytest.fixture
def admin():
    return make_user("admin", is_admin=True)


@pytest.fixture
def member():
    return make_user("member")


class TestAccess:
    @pytest.mark.parametrize(
        ("method", "url"),
        [("get", ADMINS), ("get", USERS), ("post", ADMINS), ("post", REVOKE)],
    )
    def test_requires_login_and_admin_permission(self, method, url, member):
        assert getattr(api(), method)(url, {"user_ids": [1]}, format="json").status_code == 401
        response = getattr(api(member), method)(url, {"user_ids": [1]}, format="json")
        assert response.status_code == 403


class TestLists:
    def test_lists_active_admins_only(self, admin):
        other = make_user("other", is_admin=True)
        make_user("inactive-admin", is_admin=True, is_active=False)
        make_user("member")

        body = api(admin).get(ADMINS).json()

        assert body["count"] == 2
        assert [u["id"] for u in body["results"]] == [admin.id, other.id]
        assert set(body["results"][0]) == {"id", "name", "email", "created_at"}

    def test_lists_active_non_admins_only(self, admin, member):
        make_user("inactive", is_active=False)

        body = api(admin).get(USERS).json()

        assert [u["id"] for u in body["results"]] == [member.id]

    def test_paging(self, admin):
        for i in range(5):
            make_user(f"user{i}")

        first = api(admin).get(USERS, {"page_size": 2}).json()
        last = api(admin).get(USERS, {"page_size": 2, "page": 3}).json()

        assert first["count"] == 5
        assert first["page"] == 1
        assert first["page_size"] == 2
        assert len(first["results"]) == 2
        assert len(last["results"]) == 1

    def test_page_size_is_capped(self, admin):
        assert api(admin).get(USERS, {"page_size": 1000}).json()["page_size"] == 100

    def test_search_by_name_or_email(self, admin):
        taro = make_user("taro")
        make_user("hanako")
        User.objects.filter(id=taro.id).update(name="山田太郎")

        by_name = api(admin).get(USERS, {"q": "太郎"}).json()
        by_email = api(admin).get(USERS, {"q": "HANAKO@"}).json()
        none = api(admin).get(USERS, {"q": "存在しない"}).json()

        assert [u["id"] for u in by_name["results"]] == [taro.id]
        assert by_email["count"] == 1
        assert none["count"] == 0

    def test_search_treats_wildcards_literally(self, admin, member):
        assert api(admin).get(USERS, {"q": "%"}).json()["count"] == 0


class TestGrant:
    def test_grants_admin_to_all_targets(self, admin):
        a, b = make_user("a"), make_user("b")

        response = api(admin).post(ADMINS, {"user_ids": [a.id, b.id]}, format="json")

        assert response.status_code == 204
        assert is_admin(a) and is_admin(b)

    def test_granting_to_an_admin_is_not_an_error(self, admin):
        assert api(admin).post(ADMINS, {"user_ids": [admin.id]}, format="json").status_code == 204

    def test_all_or_nothing_when_a_target_is_invalid(self, admin, member):
        inactive = make_user("inactive", is_active=False)

        for bad in (inactive.id, 99999):
            response = api(admin).post(ADMINS, {"user_ids": [member.id, bad]}, format="json")

            assert response.status_code == 400
            assert response.json()["error"]["code"] == "INVALID_TARGET"
            assert not is_admin(member)

    @pytest.mark.parametrize("body", [{}, {"user_ids": []}, {"user_ids": ["a"]}, {"user_ids": 1}])
    def test_rejects_invalid_user_ids(self, admin, body):
        response = api(admin).post(ADMINS, body, format="json")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_rejects_more_than_100_targets(self, admin):
        response = api(admin).post(ADMINS, {"user_ids": list(range(1, 102))}, format="json")

        assert response.status_code == 400

    def test_granted_user_can_use_admin_api_with_the_same_token(self, admin, member):
        client = api(member)
        assert client.get(ADMINS).status_code == 403

        api(admin).post(ADMINS, {"user_ids": [member.id]}, format="json")

        assert client.get(ADMINS).status_code == 200


class TestRevoke:
    def test_revokes_admin_from_all_targets(self, admin):
        a, b = make_user("a", is_admin=True), make_user("b", is_admin=True)

        response = api(admin).post(REVOKE, {"user_ids": [a.id, b.id]}, format="json")

        assert response.status_code == 204
        assert not is_admin(a) and not is_admin(b)
        assert is_admin(admin)

    def test_revoked_admin_loses_access_with_the_same_token(self, admin):
        other = make_user("other", is_admin=True)
        client = api(other)
        assert client.get(ADMINS).status_code == 200

        api(admin).post(REVOKE, {"user_ids": [other.id]}, format="json")

        assert client.get(ADMINS).status_code == 403

    def test_revoking_a_non_admin_is_not_an_error(self, admin, member):
        assert api(admin).post(REVOKE, {"user_ids": [member.id]}, format="json").status_code == 204

    def test_cannot_revoke_self(self, admin):
        other = make_user("other", is_admin=True)

        response = api(admin).post(REVOKE, {"user_ids": [other.id, admin.id]}, format="json")

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CANNOT_REVOKE_SELF"
        assert is_admin(other)  # 全員失敗

    def test_all_or_nothing_when_a_target_is_invalid(self, admin):
        other = make_user("other", is_admin=True)

        response = api(admin).post(REVOKE, {"user_ids": [other.id, 99999]}, format="json")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_TARGET"
        assert is_admin(other)

    def test_cannot_leave_zero_admins(self, admin):
        # 実行する管理者が、すでに有効でなくなっている（最後の1人を外そうとする）場合
        other = make_user("other", is_admin=True)
        User.objects.filter(id=admin.id).update(is_active=False)

        with pytest.raises(LastAdmin):
            revoke_admin(actor_id=admin.id, user_ids=[other.id])

        assert is_admin(other)


@pytest.mark.django_db(transaction=True)
def test_concurrent_revocations_never_leave_zero_admins():
    from django.db import transaction

    a, b = make_user("a", is_admin=True), make_user("b", is_admin=True)
    locked = threading.Event()
    release = threading.Event()
    outcome = []

    def a_revokes_b():
        try:
            with transaction.atomic():
                revoke_admin(a.id, [b.id])
                locked.set()  # コミットする前に、もう片方を動かす
                release.wait(5)
        finally:
            connection.close()

    def b_revokes_a():
        try:
            revoke_admin(b.id, [a.id])
            outcome.append("revoked")
        except LastAdmin:
            outcome.append("last_admin")
        finally:
            connection.close()

    first = threading.Thread(target=a_revokes_b)
    first.start()
    assert locked.wait(5)
    second = threading.Thread(target=b_revokes_a)
    second.start()
    second.join(0.5)  # ロックを待っている間は、終わらない
    assert second.is_alive()
    release.set()
    first.join()
    second.join()

    assert outcome == ["last_admin"]
    assert User.objects.filter(is_admin=True, is_active=True).count() == 1
