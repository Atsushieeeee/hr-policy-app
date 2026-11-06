from django.conf import settings
from django.db import models


class AppendOnlyError(Exception):
    """監査ログは、追記専用のため、更新・削除はできない。"""


class AuditLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise AppendOnlyError("監査ログは更新できません。")

    def delete(self):
        raise AppendOnlyError("監査ログは削除できません。")


class AuditLog(models.Model):
    """重要な操作の記録。追記専用（更新・削除はできない）。

    アプリの中での保護で、DBの権限による保護ではない。
    """

    class Action(models.TextChoices):
        LOGIN_SUCCESS = "login.success", "ログイン成功"
        LOGIN_FAILURE = "login.failure", "ログイン失敗"
        POLICY_REPLACE = "policy.replace", "規程の置き換え"
        ADMIN_GRANT = "admin.grant", "管理者権限の付与"
        ADMIN_REVOKE = "admin.revoke", "管理者権限の解除"
        USERS_IMPORT = "users.import", "ユーザーのCSV取込"
        FAQ_CREATE = "faq.create", "FAQの登録"
        FAQ_PUBLISH = "faq.publish", "FAQの公開"
        FAQ_DELETE = "faq.delete", "FAQの削除"
        FAQ_NEEDS_REVIEW = "faq.needs_review", "FAQを要確認にした"

    # 操作したユーザー。ログイン失敗や、コマンドの実行では空
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # 操作者のメールアドレス（その時点のもの。ログイン失敗では、入力されたメールアドレス）
    actor_email = models.CharField(max_length=254, blank=True)
    action = models.CharField(max_length=50, choices=Action.choices, db_index=True)
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    # 画面からの操作だけ。ワーカーやコマンドの操作では空
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AppendOnlyError("監査ログは更新できません。")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError("監査ログは削除できません。")

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {self.action} {self.actor_email}"
