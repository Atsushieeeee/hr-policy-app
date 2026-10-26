from django.urls import include, path

from core.views import AdminPingView

# /api/v1/admin/ 配下の管理者用API。ここに登録したものは、権限のテストが自動で検証する
admin_urlpatterns = [
    path("ping", AdminPingView.as_view(), name="admin-ping"),
]

urlpatterns = [
    # 死活監視用（インフラ向け）
    path("", include("core.urls")),
    # フロントエンドから同一オリジンの /api/v1/* として呼ばれる
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("chat.urls")),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/admin/", include(admin_urlpatterns)),
]
