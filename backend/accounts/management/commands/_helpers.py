from getpass import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import CommandError


def resolve_password(password):
    """--password が無ければ、画面で入力を求める（シェルの履歴に残さないため）。"""
    if password is None:
        password = getpass("パスワード: ")
        if password != getpass("パスワード（確認）: "):
            raise CommandError("パスワードが一致しません。")
    check_password_policy(password)
    return password


def check_password_policy(password):
    try:
        validate_password(password)
    except ValidationError as e:
        raise CommandError("パスワードが要件を満たしていません: " + " ".join(e.messages)) from e
