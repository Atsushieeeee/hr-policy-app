import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = env_bool("DJANGO_DEBUG", False)
# JWTの署名にも使うため、本番では十分に長いキーを必須にする
if not DEBUG and len(SECRET_KEY) < 32:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY は32文字以上にしてください。")
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "accounts",
    "core",
    "chat",
    "policies",
    "rag",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ["MYSQL_DATABASE"],
        "USER": os.environ["MYSQL_USER"],
        "PASSWORD": os.environ["MYSQL_PASSWORD"],
        "HOST": os.environ.get("MYSQL_HOST", "db"),
        "PORT": os.environ.get("MYSQL_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["accounts.authentication.AccessTokenAuthentication"],
    # 権限（IsAuthenticated など）は、APIごとに指定する
    "DEFAULT_PERMISSION_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
}

# JWT（アクセストークンは X-Access-Token ヘッダ、リフレッシュトークンは HttpOnly Cookie）
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "USER_ID_CLAIM": "user_id",
}
AUTH_REFRESH_COOKIE_NAME = "refresh_token"
# リフレッシュトークンは、認証APIにだけ送られるようにする
AUTH_REFRESH_COOKIE_PATH = "/api/v1/auth"
# HTTPSで公開する環境（DEBUG=false）では Secure を付ける。ローカル（http）では付けない
AUTH_COOKIE_SECURE = env_bool("AUTH_COOKIE_SECURE", not DEBUG)

LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# AI（RAG）
RAG_BACKEND = os.environ.get("RAG_BACKEND", "gemini")  # gemini / fake
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_TIMEOUT_SEC = int(os.environ.get("GEMINI_TIMEOUT_SEC", "30"))
# 追質問のために、AIへ渡す、会話の直近の往復数
CHAT_CONTEXT_TURNS = int(os.environ.get("CHAT_CONTEXT_TURNS", "5"))

# レート制限の記録は、DBキャッシュに保存する（テーブルは、migrate で作られる）
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache_table",
        # 制限の記録が、途中で消されないよう、十分な件数を確保する
        "OPTIONS": {"MAX_ENTRIES": 100000, "CULL_FREQUENCY": 3},
    }
}

# レート制限（値は環境変数で変更できる）。
# AI全体の上限は、AI側の上限（無料枠: 15回/分・500回/日）に余裕を持たせた値。
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "login_ip": os.environ.get("THROTTLE_LOGIN_IP", "10/min"),
    "chat_minute": os.environ.get("THROTTLE_CHAT_USER_MINUTE", "10/min"),
    "chat_day": os.environ.get("THROTTLE_CHAT_USER_DAY", "200/day"),
    "ai_global_minute": os.environ.get("THROTTLE_AI_GLOBAL_MINUTE", "12/min"),
    "ai_global_day": os.environ.get("THROTTLE_AI_GLOBAL_DAY", "450/day"),
    "policy_upload": os.environ.get("THROTTLE_POLICY_UPLOAD", "10/hour"),
}
# 前段のプロキシ（Caddyなど）の段数。0 のときは X-Forwarded-For を信用せず、接続元のIPを使う
REST_FRAMEWORK["NUM_PROXIES"] = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))

# ログインの連続失敗によるロック
LOGIN_MAX_FAILURES = int(os.environ.get("LOGIN_MAX_FAILURES", "5"))
LOGIN_LOCK_SECONDS = int(os.environ.get("LOGIN_LOCK_SECONDS", "900"))

# デモ用ユーザーの共通パスワード（seed_demo で使用）
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "")

# アップロードされた規程のPDFの保存先（URLでは公開しない。MEDIA_URL は設定しない）
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media"))

# 規程のアップロードと取り込みの上限（環境変数で変更できる）
POLICY_MAX_UPLOAD_MB = int(os.environ.get("POLICY_MAX_UPLOAD_MB", "20"))
POLICY_MAX_PAGES = int(os.environ.get("POLICY_MAX_PAGES", "500"))
# 質問のたびに規程の全文をAIへ送るため、長すぎると、AIの利用枠（トークン数/分）を超える
POLICY_MAX_TEXT_CHARS = int(os.environ.get("POLICY_MAX_TEXT_CHARS", "200000"))
POLICY_MIN_TEXT_CHARS = 100  # これ未満は「文字を読み取れない」（画像だけのPDFなど）
POLICY_GARBLED_RATIO = 0.05  # 文字化けの目印が、これを超えて含まれたら失敗にする
# 処理中のまま、この時間（分）を超えたら、失敗として扱う（ワーカーが止まった場合など）
POLICY_STALE_MINUTES = int(os.environ.get("POLICY_STALE_MINUTES", "10"))
POLICY_WORKER_POLL_SECONDS = int(os.environ.get("POLICY_WORKER_POLL_SECONDS", "2"))
