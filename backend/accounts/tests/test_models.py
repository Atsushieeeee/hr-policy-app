import pytest
from django.db import IntegrityError

from accounts.models import User

pytestmark = pytest.mark.django_db


def test_create_user_normalizes_email_to_lowercase():
    user = User.objects.create_user(email="  Taro@Example.COM ", name="太郎", password="x" * 12)

    assert user.email == "taro@example.com"


def test_user_is_not_admin_and_is_active_by_default():
    user = User.objects.create_user(email="a@example.com", name="A", password="x" * 12)

    assert user.is_admin is False
    assert user.is_active is True


def test_password_is_hashed():
    user = User.objects.create_user(email="a@example.com", name="A", password="plain-password-1")

    assert user.password != "plain-password-1"
    assert user.check_password("plain-password-1")


def test_user_without_password_cannot_log_in():
    user = User.objects.create_user(email="a@example.com", name="A")

    assert user.has_usable_password() is False


def test_email_must_be_unique():
    User.objects.create_user(email="a@example.com", name="A", password="x" * 12)

    with pytest.raises(IntegrityError):
        User.objects.create_user(email="a@example.com", name="B", password="x" * 12)


def test_email_is_unique_regardless_of_case():
    User.objects.create_user(email="a@example.com", name="A", password="x" * 12)

    with pytest.raises(IntegrityError):
        User.objects.create_user(email="A@Example.com", name="B", password="x" * 12)


def test_get_by_natural_key_ignores_case():
    user = User.objects.create_user(email="a@example.com", name="A", password="x" * 12)

    assert User.objects.get_by_natural_key("A@EXAMPLE.com") == user
