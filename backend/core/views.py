from django.db import connection
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import HasAdminPermission


class HealthzView(APIView):
    """死活監視用。DBへの接続可否も確認する。"""

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            return Response(
                {"status": "error", "db": "error"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"status": "ok", "db": "ok"})


class AdminAPIView(APIView):
    """管理者用APIの基底クラス。ログイン済みで、かつ管理者権限を持つユーザーだけが使える。

    /api/v1/admin/ 配下のAPIは、必ずこのクラスを継承する（権限の付け忘れを防ぐ）。
    """

    permission_classes = [IsAuthenticated, HasAdminPermission]


class AdminPingView(AdminAPIView):
    """管理者用APIの動作確認用。管理者権限の判定が効いているかを確認できる。"""

    def get(self, request):
        return Response({"status": "ok"})
