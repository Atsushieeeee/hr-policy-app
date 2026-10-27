from rest_framework import exceptions, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from core.throttling import PolicyUploadThrottle
from core.views import AdminAPIView

from .serializers import UploadSerializer
from .services import accept_upload


class PolicyView(AdminAPIView):
    """現行の規程を、アップロードしたPDFで置き換える（常に全文置換）。"""

    parser_classes = [MultiPartParser]
    throttle_classes = [PolicyUploadThrottle]

    def put(self, request):
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            raise exceptions.ValidationError({"file": ["ファイルを指定してください"]})

        policy = accept_upload(uploaded_file, request.user)
        # 取り込みは、ワーカーが行う。ここでは、受け付けたことだけを返す
        return Response(UploadSerializer(policy).data, status=status.HTTP_202_ACCEPTED)
