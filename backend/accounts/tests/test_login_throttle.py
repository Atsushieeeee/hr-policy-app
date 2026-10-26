import pytest

from accounts.models import User

pytestmark = pytest.mark.django_db

PASSWORD = "valid-password-2026"
LOGIN = "/api/v1/auth/login"


@pytest.fixture(autouse=True)
def fake_clock(clock):
    return clock


@pytest.fixture
def user():
    return User.objects.create_user(email="taro@example.com", name="太郎", password=PASSWORD)


def login(client, email="taro@example.com", password=PASSWORD, ip="10.0.0.1"):
    return client.post(
        LOGIN,
        data={"email": email, "password": password},
        content_type="application/json",
        REMOTE_ADDR=ip,
    )


def fail(client, times, email="taro@example.com", ip="10.0.0.1"):
    return [login(client, email=email, password="wrong-password-2026", ip=ip) for _ in range(times)]


class TestIpRateLimit:
    def test_blocks_the_11th_attempt_within_a_minute(self, client):
        # アカウントのロックに当たらないよう、メールアドレスを毎回変える
        for i in range(10):
            assert login(client, email=f"user{i}@example.com").status_code == 401

        response = login(client, email="user10@example.com")

        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"
        assert int(response["Retry-After"]) > 0

    def test_other_ip_is_not_affected(self, client):
        for i in range(10):
            login(client, email=f"user{i}@example.com")

        assert login(client, email="x@example.com", ip="10.0.0.2").status_code == 401

    def test_limit_is_lifted_after_a_minute(self, client, clock):
        for i in range(11):
            login(client, email=f"user{i}@example.com")

        clock.advance(61)

        assert login(client, email="again@example.com").status_code == 401

    def test_successful_logins_are_counted_too(self, client, user):
        for _ in range(10):
            assert login(client).status_code == 200

        assert login(client).status_code == 429


class TestAccountLockout:
    def test_locks_after_5_consecutive_failures(self, client, user):
        responses = fail(client, 5)

        assert [r.status_code for r in responses[:4]] == [401] * 4
        assert responses[4].status_code == 429
        body = responses[4].json()["error"]
        assert body["code"] == "LOGIN_LOCKED"
        assert "約15分" in body["message"]
        assert responses[4]["Retry-After"] == "900"

    def test_correct_password_is_rejected_while_locked(self, client, user):
        fail(client, 5)

        response = login(client)

        assert response.status_code == 429
        assert response.json()["error"]["code"] == "LOGIN_LOCKED"

    def test_remaining_time_decreases(self, client, user, clock):
        fail(client, 5)
        clock.advance(300)

        response = login(client)

        assert response.status_code == 429
        assert response["Retry-After"] == "600"
        assert "約10分" in response.json()["error"]["message"]

    def test_lock_is_lifted_after_15_minutes(self, client, user, clock):
        fail(client, 5)
        clock.advance(901)

        assert login(client).status_code == 200

    def test_success_resets_failure_count(self, client, user):
        fail(client, 4)
        assert login(client).status_code == 200

        responses = fail(client, 4)

        assert [r.status_code for r in responses] == [401] * 4

    def test_unregistered_email_is_locked_in_the_same_way(self, client):
        # ロックの有無から、アカウントが存在するかどうかが分からないようにする
        responses = fail(client, 5, email="nobody@example.com")

        assert [r.status_code for r in responses] == [401, 401, 401, 401, 429]
        assert responses[4].json()["error"]["code"] == "LOGIN_LOCKED"

    def test_email_is_case_insensitive(self, client, user):
        variants = [
            "taro@example.com",
            "TARO@example.com",
            " Taro@Example.com ",
            "taro@Example.COM",
        ]
        for email in variants:
            login(client, email=email, password="wrong-password-2026")

        response = login(client, email="TARO@EXAMPLE.COM", password="wrong-password-2026")

        assert response.status_code == 429

    def test_other_accounts_are_not_affected(self, client, user):
        User.objects.create_user(email="hanako@example.com", name="花子", password=PASSWORD)
        fail(client, 5, email="taro@example.com")

        assert login(client, email="hanako@example.com", ip="10.0.0.2").status_code == 200
