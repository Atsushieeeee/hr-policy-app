import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from policies.services import ProcessingFailure, extract_policy_text
from rag.evals.cases import CASES
from rag.evals.scoring import CaseResult, run_eval, summarize
from rag.factory import get_rag_client

DEFAULT_POLICY = settings.BASE_DIR.parent / "samples" / "dummy_policy.pdf"
# AI全体の上限（12回/分）に収まる間隔（秒）
DEFAULT_INTERVAL = 5.5


class Command(BaseCommand):
    help = (
        "評価セットの質問をAIに送り、回答の精度を採点する。"
        "規程はサンプルのPDFを使い、DBの規程は変更しない。"
    )

    def add_arguments(self, parser):
        parser.add_argument("--policy", default=str(DEFAULT_POLICY), help="評価に使う規程のPDF")
        parser.add_argument("--limit", type=int, help="先頭からこの件数だけ実行する")
        parser.add_argument(
            "--interval", type=float, default=DEFAULT_INTERVAL, help="AIを呼ぶ間隔（秒）"
        )
        parser.add_argument(
            "--fail-under",
            type=float,
            help="全体の合格率（0〜1）がこれを下回ったら、終了コードを1にする",
        )

    def handle(self, *args, **options):
        policy_text = self._load_policy(Path(options["policy"]))
        cases = CASES[: options["limit"]] if options["limit"] else CASES
        client = get_rag_client()

        self.stdout.write(f"{len(cases)}件を実行します（RAG_BACKEND={settings.RAG_BACKEND}）")
        results = run_eval(
            client, policy_text, cases, interval=options["interval"], on_result=self._print_result
        )
        summary = summarize(results)

        self.stdout.write("")
        self.stdout.write(f"合格: {summary.passed}/{summary.total}（{summary.pass_rate:.0%}）")
        self.stdout.write(f"エラー: {summary.errors}件（以下の一致率からは除く）")
        self.stdout.write(f"該当なしの判定の一致率: {summary.found}")
        self.stdout.write(f"条の一致率: {summary.article}")
        self.stdout.write(f"ページの一致率: {summary.page}")

        threshold = options["fail_under"]
        if threshold is not None and summary.pass_rate < threshold:
            self.stderr.write(f"合格率が基準（{threshold:.0%}）を下回りました")
            sys.exit(1)

    def _load_policy(self, path):
        if not path.is_file():
            raise CommandError(f"規程のPDFが見つかりません: {path}")
        try:
            _, text = extract_policy_text(path.read_bytes())
        except ProcessingFailure as failure:
            raise CommandError(f"規程を取り込めませんでした: {failure.message}") from failure
        return text

    def _print_result(self, result: CaseResult):
        case = result.case
        if result.error:
            line = f"ERROR {case.id}: {result.error}"
            self.stdout.write(self.style.WARNING(line))
            return
        if result.passed:
            self.stdout.write(self.style.SUCCESS(f"PASS  {case.id}"))
            return
        sources = "、".join(f"{s.article} p.{s.page}" for s in result.answer.sources) or "なし"
        expected = f"{case.article} p.{case.page}" if case.found else "該当なし"
        actual = f"found={result.answer.found}, 根拠: {sources}"
        self.stdout.write(self.style.ERROR(f"FAIL  {case.id}: 「{case.question}」"))
        self.stdout.write(f"        期待: {expected} / 実際: {actual}")
