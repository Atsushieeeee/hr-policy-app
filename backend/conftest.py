import pytest
from rest_framework.throttling import SimpleRateThrottle


class FakeClock:
    """時間の経過を、テストで自由に進められる時計。"""

    def __init__(self):
        self.value = 1_000_000.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


@pytest.fixture
def clock(monkeypatch):
    """レート制限とアカウントのロックが参照する時計を、差し替える。"""
    fake = FakeClock()
    monkeypatch.setattr(SimpleRateThrottle, "timer", fake)
    monkeypatch.setattr("accounts.lockout.now", fake)
    return fake


@pytest.fixture
def set_rate(monkeypatch):
    """レート制限の値を、テスト中だけ変更する（例: set_rate("chat_day", "3/day")）。"""

    def _set(scope, rate):
        monkeypatch.setitem(SimpleRateThrottle.THROTTLE_RATES, scope, rate)

    return _set


@pytest.fixture(autouse=True)
def fast_password_hasher(settings):
    """テストを速くするため、パスワードのハッシュを軽い方式にする（本番の設定には影響しない）。"""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
