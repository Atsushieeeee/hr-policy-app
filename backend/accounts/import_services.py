import csv
import io
import secrets
from dataclasses import dataclass, field

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from .models import User

REQUIRED_COLUMNS = ("email", "name")
KNOWN_COLUMNS = (*REQUIRED_COLUMNS, "is_admin", "password")
MAX_EMAIL_LENGTH = 254
MAX_NAME_LENGTH = 100
GENERATED_PASSWORD_BYTES = 12  # 16文字になる

TRUE_VALUES = {"true", "1", "yes"}
FALSE_VALUES = {"false", "0", "no", ""}

CREATE = "create"
SKIP = "skip"
ERROR = "error"


class CsvFormatError(Exception):
    """CSV全体の形式の誤り（ヘッダーが無い、必須の列が足りないなど）。1件も処理しない。"""


@dataclass
class RowResult:
    line: int
    email: str
    name: str
    is_admin: bool
    # create: 作成する（作成した） / skip: スキップ / error: エラー
    status: str
    message: str = ""
    # パスワードを指定しなかった行に、生成したパスワードが入る（作成したときだけ）
    generated_password: str | None = None


@dataclass
class ImportReport:
    results: list[RowResult]
    # 実際に作成したか（--dry-run と、--atomic でエラーがあったときは False）
    executed: bool

    def count(self, status: str) -> int:
        return sum(r.status == status for r in self.results)


@dataclass
class _Row:
    result: RowResult
    password: str = field(default="", repr=False)


def _parse_admin(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    raise ValueError("is_admin は true / false（または 1 / 0、yes / no）で指定してください")


def _check_header(fieldnames) -> list[str]:
    if not fieldnames:
        raise CsvFormatError("CSVが空です。1行目にヘッダー（email,name,...）が必要です。")
    header = [name.strip().lower() for name in fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise CsvFormatError("必須の列がありません: " + ", ".join(missing))
    unknown = [c for c in header if c not in KNOWN_COLUMNS]
    if unknown:
        raise CsvFormatError("不明な列があります: " + ", ".join(unknown))
    if len(set(header)) != len(header):
        raise CsvFormatError("同じ名前の列が複数あります。")
    return header


def _read_rows(text: str) -> list[tuple[int, dict[str, str]]]:
    reader = csv.reader(io.StringIO(text))
    header = _check_header(next(reader, None))
    rows = []
    for values in reader:
        if not any(v.strip() for v in values):
            continue  # 空行
        if len(values) > len(header):
            rows.append((reader.line_num, {"__too_many__": "1"}))
            continue
        padded = values + [""] * (len(header) - len(values))
        rows.append((reader.line_num, dict(zip(header, (v.strip() for v in padded), strict=True))))
    return rows


def _validate(rows: list[tuple[int, dict[str, str]]]) -> list[_Row]:
    existing = set(
        User.objects.filter(
            email__in=[User.objects.normalize(r.get("email", "")) for _, r in rows]
        ).values_list("email", flat=True)
    )
    seen: set[str] = set()
    checked = []
    for line, row in rows:
        email = User.objects.normalize(row.get("email", ""))
        name = row.get("name", "")
        result = RowResult(line=line, email=email, name=name, is_admin=False, status=CREATE)
        entry = _Row(result)
        checked.append(entry)

        error = _row_error(row, email, name)
        if error is None:
            try:
                result.is_admin = _parse_admin(row.get("is_admin", ""))
            except ValueError as e:
                error = str(e)
        password = row.get("password", "")
        if error is None and password:
            try:
                validate_password(password)
            except ValidationError as e:
                error = "パスワードが要件を満たしていません: " + " ".join(e.messages)
        if error is not None:
            result.status, result.message = ERROR, error
            continue

        if email in existing:
            result.status, result.message = SKIP, "すでに登録されています"
        elif email in seen:
            result.status, result.message = SKIP, "ファイル内で重複しています（最初の行を使います）"
        else:
            entry.password = password
        seen.add(email)
    return checked


def _row_error(row: dict[str, str], email: str, name: str) -> str | None:
    if "__too_many__" in row:
        return "列の数が、ヘッダーより多くなっています"
    try:
        validate_email(email)
    except ValidationError:
        return "メールアドレスの形式が正しくありません"
    if len(email) > MAX_EMAIL_LENGTH:
        return f"メールアドレスが長すぎます（{MAX_EMAIL_LENGTH}文字まで）"
    if not name:
        return "名前が空です"
    if len(name) > MAX_NAME_LENGTH:
        return f"名前が長すぎます（{MAX_NAME_LENGTH}文字まで）"
    return None


def generate_password() -> str:
    while True:
        password = secrets.token_urlsafe(GENERATED_PASSWORD_BYTES)
        try:
            validate_password(password)
            return password
        except ValidationError:
            continue


def import_users(text: str, atomic: bool = False, dry_run: bool = False) -> ImportReport:
    """CSVの内容から、ユーザーを一括で作成する。形式の誤りは CsvFormatError。

    登録済み・ファイル内で重複したメールアドレスは、更新せずスキップする。
    atomic のときは、エラーが1行でもあれば、1件も作成しない。
    """
    checked = _validate(_read_rows(text))
    results = [entry.result for entry in checked]
    if dry_run or (atomic and any(r.status == ERROR for r in results)):
        return ImportReport(results, executed=False)

    with transaction.atomic():
        for entry in checked:
            result = entry.result
            if result.status != CREATE:
                continue
            password = entry.password
            if not password:
                password = result.generated_password = generate_password()
            User.objects.create_user(
                email=result.email, name=result.name, password=password, is_admin=result.is_admin
            )
    return ImportReport(results, executed=True)
