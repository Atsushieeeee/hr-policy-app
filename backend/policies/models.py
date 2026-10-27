import uuid

from django.conf import settings
from django.db import models


def policy_upload_path(instance, filename):
    # 保存するファイル名は、ランダムにする（元のファイル名は、別の項目に保存する）
    return f"policies/{uuid.uuid4().hex}.pdf"


class PolicyDocument(models.Model):
    """アップロードされた就業規則。現行の規程は、状態が「準備完了」の1件だけ。"""

    class Status(models.TextChoices):
        PROCESSING = "processing", "処理中"
        READY = "ready", "準備完了"
        FAILED = "failed", "失敗"

    title = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=policy_upload_path)
    file_size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROCESSING, db_index=True
    )
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    # AIに渡すテキスト（正規化済み。ページの区切り [p.N] つき）
    extracted_text = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    # ワーカーが処理を始めた日時
    started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.title} ({self.status})"
