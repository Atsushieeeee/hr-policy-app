from django.conf import settings
from django.db import models


class FAQ(models.Model):
    """よくある質問と回答。公開したものは、AIを呼ばずに、保存した回答を返す。"""

    class Status(models.TextChoices):
        DRAFT = "draft", "下書き"
        PUBLISHED = "published", "公開"
        # 規程を置き換えたため、内容の確認が必要。社員には表示しない
        NEEDS_REVIEW = "needs_review", "要確認"

    question = models.CharField(max_length=1000)
    answer = models.TextField()
    # 根拠: [{"policy_id": 1, "article": "第7条", "page": 2}]（チャットの回答と同じ形）
    sources = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    # 小さい順に表示する
    sort_order = models.PositiveIntegerField(default=0)
    # 元になったチャット（回答）。チャットが消えても、FAQは残す
    source_message = models.ForeignKey(
        "chat.ChatMessage", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # 登録時の規程: {"policy_id": 1, "sha256": "..."}。規程が未登録なら空
    policy_snapshot = models.JSONField(default=dict, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.question} ({self.status})"
