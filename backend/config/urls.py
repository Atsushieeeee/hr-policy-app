from django.urls import include, path

from accounts.admin_views import AdminListView, AdminRevokeView, CandidateListView
from audit.views import AuditLogListView
from core.views import AdminPingView
from policies.views import PolicyFileForUsersView, PolicyFileView, PolicyStatusView, PolicyView

# /api/v1/admin/ 配下の管理者用API。ここに登録したものは、権限のテストが自動で検証する
admin_urlpatterns = [
    path("ping", AdminPingView.as_view(), name="admin-ping"),
    path("admins", AdminListView.as_view(), name="admin-admins"),
    path("admins/revoke", AdminRevokeView.as_view(), name="admin-admins-revoke"),
    path("users", CandidateListView.as_view(), name="admin-users"),
    path("policy", PolicyView.as_view(), name="admin-policy"),
    path("policy/file", PolicyFileView.as_view(), name="admin-policy-file"),
    path("audit-logs", AuditLogListView.as_view(), name="admin-audit-logs"),
]

urlpatterns = [
    # 死活監視用（インフラ向け）
    path("", include("core.urls")),
    # フロントエンドから同一オリジンの /api/v1/* として呼ばれる
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("chat.urls")),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/policy/status", PolicyStatusView.as_view(), name="policy-status"),
    path("api/v1/policy/file", PolicyFileForUsersView.as_view(), name="policy-file"),
    path("api/v1/admin/", include(admin_urlpatterns)),
]
