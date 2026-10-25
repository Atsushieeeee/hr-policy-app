from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email

from accounts.models import User

from ._helpers import resolve_password


class Command(BaseCommand):
    help = "ユーザーを1件作成する。--password を省略すると、画面で入力を求める。"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--admin", action="store_true", help="管理者として作成する")
        parser.add_argument("--password")

    def handle(self, *args, email, name, admin, password, **options):
        try:
            validate_email(email)
        except ValidationError as e:
            raise CommandError("メールアドレスの形式が正しくありません。") from e

        normalized = User.objects.normalize(email)
        if User.objects.filter(email=normalized).exists():
            raise CommandError(f"すでに登録されています: {normalized}")

        user = User.objects.create_user(
            email=normalized,
            name=name,
            password=resolve_password(password),
            is_admin=admin,
        )
        role = "管理者" if user.is_admin else "社員"
        self.stdout.write(self.style.SUCCESS(f"作成しました: {user.email}（{role}）"))
