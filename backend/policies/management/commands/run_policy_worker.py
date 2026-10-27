import time

from django.conf import settings
from django.core.management.base import BaseCommand

from policies.services import claim_next, expire_stale_processing, process_policy


class Command(BaseCommand):
    help = (
        "アップロードされた規程のPDFを、順に取り込むワーカー。"
        "--once を付けると、処理待ちを片付けて終了する。"
    )

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="処理待ちを片付けたら終了する")

    def handle(self, *args, once, **options):
        self.stdout.write("規程の取り込みワーカーを開始しました")
        while True:
            expire_stale_processing()
            policy = claim_next()
            if policy is not None:
                self.stdout.write(f"処理を開始: id={policy.id} {policy.original_filename}")
                process_policy(policy)
                policy.refresh_from_db()
                self.stdout.write(f"処理を終了: id={policy.id} 状態={policy.status}")
                continue
            if once:
                return
            time.sleep(settings.POLICY_WORKER_POLL_SECONDS)
