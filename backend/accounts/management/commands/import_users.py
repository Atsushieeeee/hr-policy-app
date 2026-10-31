import csv
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from accounts.import_services import CREATE, ERROR, SKIP, CsvFormatError, ImportReport, import_users
from audit.models import AuditLog
from audit.services import record

STATUS_LABELS = {CREATE: "作成", SKIP: "スキップ", ERROR: "エラー"}


class Command(BaseCommand):
    help = (
        "CSV（email,name,is_admin,password）からユーザーを一括で作成する。"
        "登録済みのメールアドレスは、更新せずスキップする。"
        "password を省略した行は、ランダムなパスワードを生成する。"
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="取り込むCSVファイル（UTF-8）")
        parser.add_argument(
            "--atomic", action="store_true", help="エラーが1行でもあれば、1件も作成しない"
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="作成せず、検証の結果だけを表示する"
        )
        parser.add_argument(
            "--output",
            help="結果（生成したパスワードを含む）をCSVに書き出す。指定すると、画面にはパスワードを表示しない",
        )

    def handle(self, *args, csv_path, atomic, dry_run, output, **options):
        try:
            text = Path(csv_path).read_text(encoding="utf-8-sig")
        except FileNotFoundError as e:
            raise CommandError(f"ファイルが見つかりません: {csv_path}") from e
        except UnicodeDecodeError as e:
            raise CommandError(
                "UTF-8 のCSVを指定してください（文字コードを読み取れません）。"
            ) from e

        # 作成したあとに書き出せなくならないよう、先にファイルを作っておく
        out_file = self._create_output(output) if output else None
        try:
            report = import_users(text, atomic=atomic, dry_run=dry_run)
        except CsvFormatError as e:
            if out_file:
                out_file.close()
                os.unlink(output)
            raise CommandError(str(e)) from e

        if out_file:
            self._write_output(out_file, output, report)
        self._print_report(report, dry_run, show_passwords=not output)
        if report.executed:
            # 取り込んだユーザーは、ユーザーのテーブルに残るため、件数だけを記録する
            record(
                AuditLog.Action.USERS_IMPORT,
                detail={
                    "filename": Path(csv_path).name,
                    "created": report.count(CREATE),
                    "skipped": report.count(SKIP),
                    "errors": report.count(ERROR),
                },
            )

        if report.count(ERROR):
            raise CommandError(
                "エラーがあります。" + ("1件も作成していません。" if atomic and not dry_run else "")
            )

    def _print_report(self, report: ImportReport, dry_run: bool, show_passwords: bool):
        created_label = "作成" if report.executed else "作成予定"
        for r in report.results:
            if r.status == CREATE:
                role = "管理者" if r.is_admin else "社員"
                line = f"行{r.line}: {created_label} {r.email}（{role}）"
                if r.generated_password and show_passwords:
                    line += f" 仮パスワード: {r.generated_password}"
                self.stdout.write(self.style.SUCCESS(line))
            elif r.status == SKIP:
                self.stdout.write(f"行{r.line}: スキップ {r.email}（{r.message}）")
            else:
                self.stdout.write(
                    self.style.ERROR(f"行{r.line}: エラー {r.email or '-'}（{r.message}）")
                )

        self.stdout.write("")
        self.stdout.write(
            f"{created_label}: {report.count(CREATE)}件 / スキップ: {report.count(SKIP)}件"
            f" / エラー: {report.count(ERROR)}件"
        )
        if not report.executed and not dry_run:
            self.stdout.write(self.style.WARNING("--atomic のため、1件も作成していません。"))
        if report.executed and show_passwords:
            if any(r.generated_password for r in report.results):
                self.stdout.write(
                    self.style.WARNING(
                        "生成したパスワードは、この画面にしか表示されません。控えてください。"
                        "（控えそこなったときは、set_password で再設定できます）"
                    )
                )

    def _create_output(self, output: str):
        # 他のユーザーが読めないよう、権限を 600 にして作る。既存のファイルは上書きしない
        try:
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as e:
            raise CommandError(f"すでにファイルがあります（上書きしません）: {output}") from e
        except OSError as e:
            raise CommandError(f"結果のファイルを作れません: {output}（{e.strerror}）") from e
        # Excel で開いても文字化けしないよう、BOM つきにする
        return os.fdopen(fd, "w", encoding="utf-8-sig", newline="")

    def _write_output(self, out_file, output: str, report: ImportReport):
        created_label = "作成" if report.executed else "作成予定"
        with out_file:
            writer = csv.writer(out_file)
            writer.writerow(["行", "email", "name", "is_admin", "結果", "仮パスワード", "メモ"])
            for r in report.results:
                label = created_label if r.status == CREATE else STATUS_LABELS[r.status]
                writer.writerow(
                    [
                        r.line,
                        r.email,
                        r.name,
                        r.is_admin,
                        label,
                        r.generated_password or "",
                        r.message,
                    ]
                )
        self.stdout.write(f"結果を書き出しました: {output}（配布したら、削除してください）")
