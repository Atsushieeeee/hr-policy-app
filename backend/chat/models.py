from django.conf import settings
from django.db import models


class ChatSession(models.Model):
    """ユーザーの、連続した質問と回答のまとまり（会話）。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="chat_sessions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"session {self.id} (user {self.user_id})"


class ChatMessage(models.Model):
    """会話の中の、1つの発言（質問または回答）。"""

    class Role(models.TextChoices):
        USER = "user", "質問"
        ASSISTANT = "assistant", "回答"

    class Feedback(models.TextChoices):
        GOOD = "good", "役に立った"
        BAD = "bad", "役に立たなかった"

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    # 質問だけに入る、完全一致で集計するための正規化した文字列（回答では空）
    normalized_question = models.CharField(max_length=1000, blank=True)
    # normalized_question の SHA-256。集計（GROUP BY）と検索の索引に使う。
    # 長い文字列は、MySQL の索引の上限（3072バイト）を超えるため、文字列そのものには索引を付けない
    question_hash = models.CharField(max_length=64, blank=True, db_index=True)
    # 回答だけに入る、根拠: [{"policy_id": 1, "article": "第7条", "page": 2}]
    # 規程は置き換えると削除されるため、policy_id は参照（外部キー）にせず、値として残す
    sources = models.JSONField(default=list, blank=True)
    # 回答だけに入る。規程に該当する記載が見つからなかった回答か
    is_no_answer = models.BooleanField(default=False)
    # 回答だけに入る、利用者の評価
    feedback = models.CharField(max_length=10, choices=Feedback.choices, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["session", "created_at"])]

    def __str__(self):
        return f"{self.role} {self.id} (session {self.session_id})"
