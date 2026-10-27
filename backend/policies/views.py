from django.http import FileResponse
from rest_framework import exceptions, status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.throttling import PolicyUploadThrottle
from core.views import AdminAPIView

from .exceptions import PolicyNotFound
from .serializers import CurrentPolicySerializer, LatestUploadSerializer, UploadSerializer
from .services import accept_upload, current_policy, latest_upload


class PolicyView(AdminAPIView):
    """現行の規程を、アップロードしたPDFで置き換える（常に全文置換）。"""

    parser_classes = [MultiPartParser]
    throttle_classes = [PolicyUploadThrottle]

    def get(self, request):
        """現行の規程と、取り込みの状況。規程が未登録でも 200 で返す。"""
        policy = current_policy()
        upload = latest_upload()
        return Response(
            {
                "current": CurrentPolicySerializer(policy).data if policy else None,
                "upload": LatestUploadSerializer(upload).data if upload else None,
            }
        )

    def put(self, request):
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            raise exceptions.ValidationError({"file": ["ファイルを指定してください"]})

        policy = accept_upload(uploaded_file, request.user)
        # 取り込みは、ワーカーが行う。ここでは、受け付けたことだけを返す
        return Response(UploadSerializer(policy).data, status=status.HTTP_202_ACCEPTED)


class PolicyStatusView(APIView):
    """規程が登録されているか。ログイン済みなら、誰でも確認できる。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"registered": current_policy() is not None})


class PolicyFileView(AdminAPIView):
    """現行の規程のPDF。ブラウザ内で表示できる形で返す。"""

    def get(self, request):
        policy = current_policy()
        if policy is None:
            raise PolicyNotFound()
        return FileResponse(
            policy.file.open("rb"),
            content_type="application/pdf",
            as_attachment=False,
            filename=policy.original_filename,
        )
