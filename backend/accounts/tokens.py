from django.conf import settings
from rest_framework_simplejwt.exceptions import TokenBackendError, TokenError
from rest_framework_simplejwt.state import token_backend
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken


def set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        str(refresh_token),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="Lax",
        path=settings.AUTH_REFRESH_COOKIE_PATH,
    )


def delete_refresh_cookie(response):
    response.delete_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        samesite="Lax",
    )


def revoke_all_tokens(user_id):
    """ユーザーの発行済みリフレッシュトークンを、すべて無効にする。"""
    for outstanding in OutstandingToken.objects.filter(user_id=user_id):
        BlacklistedToken.objects.get_or_create(token=outstanding)


def revoke_if_reused(raw_token):
    """無効化済みのリフレッシュトークンが再度使われた場合、盗用の可能性があるため、
    そのユーザーのトークンをすべて無効にする。

    署名と有効期限が正しいトークンで、かつ無効化済みの場合だけが対象。
    """
    try:
        payload = token_backend.decode(raw_token, verify=True)
    except TokenBackendError:
        return
    if BlacklistedToken.objects.filter(token__jti=payload.get("jti")).exists():
        revoke_all_tokens(payload.get(settings.SIMPLE_JWT["USER_ID_CLAIM"]))


def parse_refresh_token(raw_token):
    """有効なリフレッシュトークンなら RefreshToken を返す。無効なら None（再利用の検知も行う）。"""
    if not raw_token:
        return None
    try:
        return RefreshToken(raw_token)
    except TokenError:
        revoke_if_reused(raw_token)
        return None
