from pathlib import Path

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


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """アップロードされたファイルは、テストごとの一時フォルダに保存する。"""
    settings.MEDIA_ROOT = str(tmp_path / "media")


@pytest.fixture
def registered_policy(db):
    """現行の規程が登録されている状態にする（PDFの取り込みを通さず、直接作る）。"""
    from accounts.models import User
    from policies.models import PolicyDocument

    admin = User.objects.create_user(
        email="policy-admin@example.com", name="管理者", password="x", is_admin=True
    )
    return PolicyDocument.objects.create(
        title="就業規則",
        original_filename="policy.pdf",
        file="policies/dummy.pdf",
        file_size=1,
        sha256="0" * 64,
        page_count=1,
        status=PolicyDocument.Status.READY,
        extracted_text="[p.1]\n第1条 テスト用の規程",
        uploaded_by=admin,
    )


@pytest.fixture
def samples(settings):
    """サンプルのPDFがあるフォルダ（リポジトリの samples/）。"""
    return Path(settings.BASE_DIR).parent / "samples"
