from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User

from ._helpers import check_password_policy

DEMO_USERS = [
    ("admin@example.com", "管理 花子", True),
    ("employee1@example.com", "社員 一郎", False),
    ("employee2@example.com", "社員 二郎", False),
    ("employee3@example.com", "社員 三郎", False),
]


class Command(BaseCommand):
    help = "デモ用のユーザー（管理者1名・社員3名）を作成する。作成済みのユーザーはスキップする。"

    def handle(self, *args, **options):
        password = settings.DEMO_PASSWORD
        if not password:
            raise CommandError(
                "環境変数 DEMO_PASSWORD が設定されていません（.env を確認してください）。"
            )
        check_password_policy(password)

        for email, name, is_admin in DEMO_USERS:
            if User.objects.filter(email=email).exists():
                self.stdout.write(f"スキップ（作成済み）: {email}")
                continue
            User.objects.create_user(email=email, name=name, password=password, is_admin=is_admin)
            suffix = "（管理者）" if is_admin else ""
            self.stdout.write(self.style.SUCCESS(f"作成: {email}{suffix}"))
