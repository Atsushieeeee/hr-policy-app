from django.urls import include, path

urlpatterns = [
    # 死活監視用（インフラ向け）
    path("", include("core.urls")),
    # フロントエンドから同一オリジンの /api/v1/* として呼ばれる
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("chat.urls")),
    path("api/v1/", include("accounts.urls")),
]
