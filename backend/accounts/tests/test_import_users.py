import csv

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.import_services import CsvFormatError, import_users
from accounts.models import User

pytestmark = pytest.mark.django_db

VALID_PASSWORD = "valid-password-2026"
HEADER = "email,name,is_admin,password\n"


def statuses(report):
    return [r.status for r in report.results]


class TestImportUsers:
    def test_creates_users_with_given_password_and_role(self):
        report = import_users(
            HEADER + f"a@example.com,A,true,{VALID_PASSWORD}\nb@example.com,B,,\n"
        )

        assert statuses(report) == ["create", "create"]
        assert report.executed
        a = User.objects.get(email="a@example.com")
        assert a.is_admin and a.check_password(VALID_PASSWORD)
        assert User.objects.get(email="b@example.com").is_admin is False

    def test_generates_a_valid_password_when_omitted(self):
        report = import_users(HEADER + "a@example.com,A,,\n")

        generated = report.results[0].generated_password
        assert generated and len(generated) >= 12
        assert User.objects.get(email="a@example.com").check_password(generated)

    def test_given_password_is_not_reported_back(self):
        report = import_users(HEADER + f"a@example.com,A,,{VALID_PASSWORD}\n")

        assert report.results[0].generated_password is None

    def test_password_and_is_admin_columns_are_optional(self):
        report = import_users("email,name\na@example.com,A\n")

        assert statuses(report) == ["create"]
        assert User.objects.get(email="a@example.com").is_admin is False

    def test_existing_email_is_skipped_not_updated(self):
        User.objects.create_user(email="a@example.com", name="元の名前", password=VALID_PASSWORD)

        report = import_users(HEADER + "A@Example.com,新しい名前,true,\n")

        assert statuses(report) == ["skip"]
        user = User.objects.get(email="a@example.com")
        assert user.name == "元の名前" and user.is_admin is False

    def test_duplicate_in_file_uses_the_first_row(self):
        report = import_users(HEADER + "a@example.com,最初,,\na@example.com,二番目,true,\n")

        assert statuses(report) == ["create", "skip"]
        assert User.objects.get(email="a@example.com").name == "最初"

    @pytest.mark.parametrize(
        "row",
        [
            "not-an-email,A,,",
            "a@example.com,,,",
            "a@example.com,A,maybe,",
            "a@example.com,A,,short",
            "a@example.com,A,,,extra",
            "a@example.com,{}".format("あ" * 101),
        ],
    )
    def test_invalid_rows_are_errors(self, row):
        report = import_users(HEADER + row + "\n")

        assert statuses(report) == ["error"]
        assert report.results[0].message
        assert not User.objects.exists()

    def test_errors_do_not_stop_other_rows_by_default(self):
        report = import_users(HEADER + "bad,A,,\nb@example.com,B,,\n")

        assert statuses(report) == ["error", "create"]
        assert User.objects.filter(email="b@example.com").exists()

    def test_atomic_creates_nothing_when_any_row_has_an_error(self):
        report = import_users(HEADER + "a@example.com,A,,\nbad,B,,\n", atomic=True)

        assert statuses(report) == ["create", "error"]
        assert not report.executed
        assert not User.objects.exists()

    def test_atomic_creates_everything_when_there_is_no_error(self):
        report = import_users(HEADER + "a@example.com,A,,\nb@example.com,B,,\n", atomic=True)

        assert report.executed
        assert User.objects.count() == 2

    def test_dry_run_changes_nothing(self):
        report = import_users(HEADER + "a@example.com,A,,\n", dry_run=True)

        assert statuses(report) == ["create"]
        assert not report.executed
        assert report.results[0].generated_password is None
        assert not User.objects.exists()

    def test_blank_lines_are_ignored_and_line_numbers_are_kept(self):
        report = import_users(HEADER + "\na@example.com,A,,\n,,,\nbad,B,,\n")

        assert [(r.line, r.status) for r in report.results] == [(3, "create"), (5, "error")]

    def test_columns_are_case_insensitive_and_values_are_trimmed(self):
        report = import_users("Email , Name ,IS_ADMIN\n a@example.com , A , TRUE \n")

        assert statuses(report) == ["create"]
        user = User.objects.get(email="a@example.com")
        assert user.name == "A" and user.is_admin

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "email\na@example.com\n",
            "email,name,role\na@example.com,A,x\n",
            "email,email,name\n",
        ],
    )
    def test_format_errors_stop_everything(self, text):
        with pytest.raises(CsvFormatError):
            import_users(text)


class TestCommand:
    def write(self, tmp_path, text, encoding="utf-8"):
        path = tmp_path / "users.csv"
        path.write_bytes(text.encode(encoding))
        return str(path)

    def test_imports_a_utf8_file_with_bom(self, tmp_path, capsys):
        path = self.write(tmp_path, HEADER + "a@example.com,鈴木,,\n", encoding="utf-8-sig")

        call_command("import_users", path)

        out = capsys.readouterr().out
        assert User.objects.get(email="a@example.com").name == "鈴木"
        assert "作成: 1件" in out and "仮パスワード:" in out

    def test_output_file_has_passwords_and_the_screen_does_not(self, tmp_path, capsys):
        path = self.write(
            tmp_path, HEADER + f"a@example.com,A,,\nb@example.com,B,,{VALID_PASSWORD}\n"
        )
        result_path = str(tmp_path / "result.csv")

        call_command("import_users", path, output=result_path)

        out = capsys.readouterr().out
        with open(result_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        generated = rows[0]["仮パスワード"]
        assert generated and generated not in out
        assert User.objects.get(email="a@example.com").check_password(generated)
        assert rows[1]["仮パスワード"] == ""
        assert (tmp_path / "result.csv").stat().st_mode & 0o777 == 0o600

    def test_output_file_is_never_overwritten(self, tmp_path):
        path = self.write(tmp_path, HEADER + "a@example.com,A,,\n")
        result = tmp_path / "result.csv"
        result.write_text("大事なファイル")

        with pytest.raises(CommandError, match="上書きしません"):
            call_command("import_users", path, output=str(result))

        assert result.read_text() == "大事なファイル"
        assert not User.objects.exists()

    def test_output_file_is_removed_when_the_csv_format_is_wrong(self, tmp_path):
        path = self.write(tmp_path, "a@example.com,A\n")
        result = tmp_path / "result.csv"

        with pytest.raises(CommandError, match="必須の列"):
            call_command("import_users", path, output=str(result))

        assert not result.exists()

    def test_exits_with_an_error_when_a_row_is_invalid(self, tmp_path, capsys):
        path = self.write(tmp_path, HEADER + "bad,A,,\nb@example.com,B,,\n")

        with pytest.raises(CommandError, match="エラーがあります"):
            call_command("import_users", path)

        assert User.objects.filter(email="b@example.com").exists()
        assert "行2: エラー" in capsys.readouterr().out

    def test_atomic_error_message_says_nothing_was_created(self, tmp_path):
        path = self.write(tmp_path, HEADER + "bad,A,,\nb@example.com,B,,\n")

        with pytest.raises(CommandError, match="1件も作成していません"):
            call_command("import_users", path, atomic=True)

        assert not User.objects.exists()

    def test_dry_run_reports_without_creating(self, tmp_path, capsys):
        path = self.write(tmp_path, HEADER + "a@example.com,A,,\n")

        call_command("import_users", path, dry_run=True)

        assert "作成予定: 1件" in capsys.readouterr().out
        assert not User.objects.exists()

    def test_missing_file_and_bad_encoding_and_bad_format(self, tmp_path):
        with pytest.raises(CommandError, match="見つかりません"):
            call_command("import_users", str(tmp_path / "none.csv"))
        sjis = self.write(tmp_path, HEADER + "a@example.com,鈴木,,\n", encoding="cp932")
        with pytest.raises(CommandError, match="UTF-8"):
            call_command("import_users", sjis)
        no_header = self.write(tmp_path, "a@example.com,A\n")
        with pytest.raises(CommandError, match="必須の列"):
            call_command("import_users", no_header)

    def test_sample_csv_is_valid(self, settings):
        sample = settings.BASE_DIR.parent / "samples" / "users.csv"

        call_command("import_users", str(sample), dry_run=True)
