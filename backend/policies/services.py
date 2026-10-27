import hashlib
import logging
from contextlib import contextmanager
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from pypdf import PdfReader

from .exceptions import FileTooLarge, InvalidFile, SameFile, UploadInProgress
from .models import PolicyDocument
from .text import build_policy_text, garbled_ratio, normalize_text

logger = logging.getLogger(__name__)

PDF_SIGNATURE = b"%PDF-"


class ProcessingFailure(Exception):
    """取り込みに失敗した（理由は、画面に表示される）。"""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


@contextmanager
def advisory_lock(name):
    """同時に1つの処理だけが入れるようにする（MySQLのロック）。取れなければ、受け付けない。"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 0)", [name])
        if cursor.fetchone()[0] != 1:
            raise UploadInProgress()
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s)", [name])


def delete_files(names):
    """保存済みのファイルを消す。失敗しても、全体の処理は止めない。"""
    storage = PolicyDocument._meta.get_field("file").storage
    for name in names:
        try:
            storage.delete(name)
        except Exception:
            logger.exception("ファイルを削除できませんでした: %s", name)


def current_policy():
    """現行の規程（準備完了のもの）。なければ None。"""
    return PolicyDocument.objects.filter(status=PolicyDocument.Status.READY).first()


def latest_upload():
    """処理中、または直近で失敗した取り込み。なければ None。"""
    expire_stale_processing()
    return (
        PolicyDocument.objects.exclude(status=PolicyDocument.Status.READY).order_by("-id").first()
    )


# ---- 受け付け（APIの中で、すぐに終わる処理）----


def expire_stale_processing():
    """処理中のまま、一定時間を超えたもの（ワーカーが止まったなど）を、失敗にする。"""
    limit = timezone.now() - timedelta(minutes=settings.POLICY_STALE_MINUTES)
    stale = Q(started_at__lt=limit) | Q(started_at__isnull=True, created_at__lt=limit)
    PolicyDocument.objects.filter(status=PolicyDocument.Status.PROCESSING).filter(stale).update(
        status=PolicyDocument.Status.FAILED,
        error_code="PROCESSING_INTERRUPTED",
        error_message="処理が中断されました。もう一度アップロードしてください",
    )


def accept_upload(uploaded_file, user):
    """アップロードを受け付け、「処理中」の規程として保存する。取り込みは、ワーカーが行う。"""
    if uploaded_file.size > settings.POLICY_MAX_UPLOAD_MB * 1024 * 1024:
        raise FileTooLarge(f"ファイルが大きすぎます（上限: {settings.POLICY_MAX_UPLOAD_MB}MB）")

    # 拡張子ではなく、ファイルの先頭の署名で、PDFかどうかを判定する
    if uploaded_file.read(len(PDF_SIGNATURE)) != PDF_SIGNATURE:
        raise InvalidFile("PDFではないファイルです。PDFファイルを指定してください")
    uploaded_file.seek(0)

    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    sha256 = digest.hexdigest()
    uploaded_file.seek(0)

    with advisory_lock("policy_upload"):
        expire_stale_processing()
        if PolicyDocument.objects.filter(status=PolicyDocument.Status.PROCESSING).exists():
            raise UploadInProgress()

        current = current_policy()
        if current is not None and current.sha256 == sha256:
            raise SameFile()

        # 前回、失敗した記録は、ここで片付ける
        failed = list(PolicyDocument.objects.filter(status=PolicyDocument.Status.FAILED))
        failed_files = [p.file.name for p in failed]
        PolicyDocument.objects.filter(id__in=[p.id for p in failed]).delete()
        delete_files(failed_files)

        policy = PolicyDocument(
            title=Path(uploaded_file.name).stem[:255],
            original_filename=uploaded_file.name[:255],
            file_size=uploaded_file.size,
            sha256=sha256,
            uploaded_by=user,
        )
        policy.file.save(uploaded_file.name, uploaded_file, save=False)
        try:
            policy.save()
        except Exception:
            delete_files([policy.file.name])
            raise
    return policy


# ---- 取り込み（ワーカーが行う処理）----


def claim_next():
    """処理待ちの規程を、1件取り出して、処理の開始を記録する。なければ None。"""
    with transaction.atomic():
        policy = (
            PolicyDocument.objects.select_for_update(skip_locked=True)
            .filter(status=PolicyDocument.Status.PROCESSING, started_at__isnull=True)
            .order_by("id")
            .first()
        )
        if policy is not None:
            policy.started_at = timezone.now()
            policy.save(update_fields=["started_at", "updated_at"])
        return policy


def extract_policy_text(data):
    """PDFから、ページの区切りつきのテキストを作る。失敗したら ProcessingFailure。"""
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ProcessingFailure(
                "INVALID_FILE", "パスワードが設定されたPDFには、対応していません"
            )
        page_count = len(reader.pages)
        if page_count > settings.POLICY_MAX_PAGES:
            raise ProcessingFailure(
                "TOO_MANY_PAGES",
                f"ページ数が多すぎます（{page_count}ページ。"
                f"上限: {settings.POLICY_MAX_PAGES}ページ）",
            )
        pages = [normalize_text(page.extract_text() or "") for page in reader.pages]
    except ProcessingFailure:
        raise
    except Exception as e:
        logger.warning("PDFを読み取れませんでした: %s", e)
        raise ProcessingFailure(
            "INVALID_FILE", "PDFを読み取れませんでした。壊れているファイルの可能性があります"
        ) from e

    body = "".join(pages)
    if len(body.strip()) < settings.POLICY_MIN_TEXT_CHARS:
        raise ProcessingFailure(
            "PDF_NO_TEXT",
            "PDFから文字を読み取れませんでした。スキャンした画像のPDFには、対応していません。"
            "文字を含むPDFをアップロードしてください",
        )
    if garbled_ratio(body) > settings.POLICY_GARBLED_RATIO:
        raise ProcessingFailure(
            "PDF_TEXT_GARBLED",
            "文字を正しく読み取れませんでした（文字化け）。別の形式で書き出したPDFをお試しください",
        )

    text = build_policy_text(pages)
    if len(text) > settings.POLICY_MAX_TEXT_CHARS:
        raise ProcessingFailure(
            "POLICY_TOO_LONG",
            f"規程が長すぎます（{len(text):,}文字。上限: {settings.POLICY_MAX_TEXT_CHARS:,}文字）。"
            "質問のたびに規程の全文をAIへ送るため、長すぎると利用枠を超えてしまいます",
        )
    return page_count, text


def process_policy(policy):
    """規程のPDFを取り込む。成功したら現行の規程にして、旧規程を削除する。失敗なら旧規程を残す。"""
    try:
        with policy.file.open("rb") as f:
            data = f.read()
        page_count, text = extract_policy_text(data)
    except ProcessingFailure as failure:
        _mark_failed(policy, failure.code, failure.message)
        return
    except Exception:
        logger.exception("規程の取り込みでエラーが発生しました: id=%s", policy.id)
        _mark_failed(policy, "PROCESSING_ERROR", "処理中にエラーが発生しました")
        return

    with transaction.atomic():
        policy.page_count = page_count
        policy.extracted_text = text
        policy.status = PolicyDocument.Status.READY
        policy.error_code = ""
        policy.error_message = ""
        policy.save()
        # 常に全文置換: 新しい規程が準備できたので、それ以外（旧規程・失敗した記録）を消す
        others = list(
            PolicyDocument.objects.exclude(id=policy.id).exclude(
                status=PolicyDocument.Status.PROCESSING
            )
        )
        old_files = [p.file.name for p in others]
        PolicyDocument.objects.filter(id__in=[p.id for p in others]).delete()
    delete_files(old_files)


def _mark_failed(policy, code, message):
    policy.status = PolicyDocument.Status.FAILED
    policy.error_code = code
    policy.error_message = message
    policy.save(update_fields=["status", "error_code", "error_message", "updated_at"])
