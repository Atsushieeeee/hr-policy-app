from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response

from core.pagination import StandardPagination
from core.views import AdminAPIView

from .admin_services import grant_admin, revoke_admin
from .models import User
from .serializers import AdminUserSerializer, UserIdsSerializer


class UserListView(AdminAPIView):
    """ページングつきの一覧（古い登録順）。"""

    def get_queryset(self, request):
        raise NotImplementedError

    def get(self, request):
        paginator = StandardPagination()
        page = paginator.paginate_queryset(self.get_queryset(request), request)
        return paginator.get_paginated_response(AdminUserSerializer(page, many=True).data)


class AdminListView(UserListView):
    """管理者権限を持つ、有効なユーザーの一覧。付与（POST）もここで行う。"""

    def get_queryset(self, request):
        return User.objects.filter(is_admin=True, is_active=True).order_by("created_at", "id")

    def post(self, request):
        serializer = UserIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        grant_admin(serializer.validated_data["user_ids"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminRevokeView(AdminAPIView):
    def post(self, request):
        serializer = UserIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        revoke_admin(request.user.id, serializer.validated_data["user_ids"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CandidateListView(UserListView):
    """管理者権限のない、有効なユーザーの一覧。?q= で、名前・メールを部分一致で検索する。"""

    def get_queryset(self, request):
        users = User.objects.filter(is_admin=False, is_active=True)
        q = request.query_params.get("q", "").strip()
        if q:
            users = users.filter(Q(name__icontains=q) | Q(email__icontains=q))
        return users.order_by("created_at", "id")
