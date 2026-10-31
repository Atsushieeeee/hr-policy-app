from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    # 操作者の現在の名前。操作者がいない記録（ログイン失敗など）では空
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "created_at",
            "action",
            "action_label",
            "actor_email",
            "actor_name",
            "target_type",
            "target_id",
            "detail",
            "ip",
        ]
        read_only_fields = fields

    def get_actor_name(self, log):
        return log.actor.name if log.actor else ""
