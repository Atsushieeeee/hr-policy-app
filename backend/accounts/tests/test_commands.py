import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import User

pytestmark = pytest.mark.django_db

VALID_PASSWORD = "valid-password-2026"


def test_create_user_creates_employee():
    call_command("create_user", email="a@example.com", name="A", password=VALID_PASSWORD)

    user = User.objects.get(email="a@example.com")
    assert user.is_admin is False
    assert user.check_password(VALID_PASSWORD)


def test_create_user_with_admin_flag():
    call_command(
        "create_user", email="a@example.com", name="A", password=VALID_PASSWORD, admin=True
    )

    assert User.objects.get(email="a@example.com").is_admin is True


def test_create_user_rejects_duplicate_email():
    call_command("create_user", email="a@example.com", name="A", password=VALID_PASSWORD)

    with pytest.raises(CommandError, match="すでに登録されています"):
        call_command("create_user", email="A@example.com", name="B", password=VALID_PASSWORD)


def test_create_user_rejects_invalid_email():
    with pytest.raises(CommandError, match="形式"):
        call_command("create_user", email="not-an-email", name="A", password=VALID_PASSWORD)


@pytest.mark.parametrize("password", ["short", "1234567890123456", "password1234"])
def test_create_user_rejects_weak_password(password):
    with pytest.raises(CommandError, match="要件を満たしていません"):
        call_command("create_user", email="a@example.com", name="A", password=password)

    assert not User.objects.filter(email="a@example.com").exists()


def test_set_password_updates_password():
    call_command("create_user", email="a@example.com", name="A", password=VALID_PASSWORD)

    call_command("set_password", email="a@example.com", password="another-password-2026")

    assert User.objects.get(email="a@example.com").check_password("another-password-2026")


def test_set_password_fails_for_unknown_user():
    with pytest.raises(CommandError, match="見つかりません"):
        call_command("set_password", email="none@example.com", password=VALID_PASSWORD)


def test_seed_demo_creates_one_admin_and_three_employees(settings):
    settings.DEMO_PASSWORD = VALID_PASSWORD

    call_command("seed_demo")

    assert User.objects.count() == 4
    assert User.objects.filter(is_admin=True).count() == 1
    assert User.objects.get(email="employee1@example.com").check_password(VALID_PASSWORD)


def test_seed_demo_can_run_repeatedly(settings):
    settings.DEMO_PASSWORD = VALID_PASSWORD

    call_command("seed_demo")
    call_command("seed_demo")

    assert User.objects.count() == 4


def test_seed_demo_requires_demo_password(settings):
    settings.DEMO_PASSWORD = ""

    with pytest.raises(CommandError, match="DEMO_PASSWORD"):
        call_command("seed_demo")
