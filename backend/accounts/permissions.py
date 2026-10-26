from rest_framework.permissions import BasePermission


class HasAdminPermission(BasePermission):
    """管理者権限（is_admin）を持つユーザーだけを許可する。

    ユーザーはリクエストのたびにDBから読み直されるため（accounts/authentication.py）、
    権限の変更は、同じトークンのまま次のリクエストから反映される。
    """

    message = "この操作を行う権限がありません"

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin)
