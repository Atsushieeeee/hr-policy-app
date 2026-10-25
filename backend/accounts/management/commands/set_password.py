from django.core.management.base import BaseCommand, CommandError

from accounts.models import User

from ._helpers import resolve_password


class Command(BaseCommand):
    help = "ユーザーのパスワードを再設定する（再設定の画面は提供しないため、このコマンドで行う）。"

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--password")

    def handle(self, *args, email, password, **options):
        normalized = User.objects.normalize(email)
        try:
            user = User.objects.get(email=normalized)
        except User.DoesNotExist as e:
            raise CommandError(f"ユーザーが見つかりません: {normalized}") from e

        user.set_password(resolve_password(password))
        user.save(update_fields=["password", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"パスワードを更新しました: {user.email}"))
