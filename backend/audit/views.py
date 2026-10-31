from rest_framework import serializers

from core.pagination import StandardPagination
from core.views import AdminAPIView

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogPagination(StandardPagination):
    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        # 画面の絞り込みの選択肢。操作の種類の定義元をバックエンドに一本化する
        response.data["actions"] = [
            {"value": value, "label": label} for value, label in AuditLog.Action.choices
        ]
        return response


class AuditLogListView(AdminAPIView):
    """監査ログの一覧（新しい順）。?action= で操作の種類を絞り込む。読み取り専用。"""

    def get(self, request):
        logs = AuditLog.objects.select_related("actor")
        action = request.query_params.get("action", "")
        if action:
            if action not in AuditLog.Action.values:
                raise serializers.ValidationError({"action": "操作の種類が正しくありません。"})
            logs = logs.filter(action=action)
        paginator = AuditLogPagination()
        page = paginator.paginate_queryset(logs, request)
        return paginator.get_paginated_response(AuditLogSerializer(page, many=True).data)
