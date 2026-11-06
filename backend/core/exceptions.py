import math

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import exception_handler

# 例外の種類ごとの、エラーコードと利用者向けメッセージ
_DEFINITIONS = [
    (exceptions.NotAuthenticated, "UNAUTHENTICATED", "ログインが必要です"),
    (exceptions.AuthenticationFailed, "TOKEN_INVALID", "認証の有効期限が切れたか、無効です"),
    (exceptions.PermissionDenied, "FORBIDDEN", "この操作を行う権限がありません"),
    (exceptions.NotFound, "NOT_FOUND", "対象が見つかりません"),
    (exceptions.MethodNotAllowed, "METHOD_NOT_ALLOWED", "許可されていない操作です"),
    (exceptions.ParseError, "BAD_REQUEST", "リクエストの形式が正しくありません"),
    (exceptions.ValidationError, "VALIDATION_ERROR", "入力内容が正しくありません"),
]


def format_wait(seconds):
    """待ち時間を、利用者向けの表現にする（例: 「約30秒」「約15分」）。"""
    seconds = max(1, math.ceil(seconds or 1))
    if seconds < 60:
        return f"約{seconds}秒"
    return f"約{math.ceil(seconds / 60)}分"


class CodedAPIException(exceptions.APIException):
    """エラーコードを持つ、アプリ独自の例外の基底クラス。"""

    error_code = "ERROR"


class RateLimited(CodedAPIException):
    """回数の制限を超えた（429）。wait は、再試行できるまでの秒数（Retry-After ヘッダになる）。"""

    status_code = 429

    def __init__(self, code, message, wait):
        super().__init__(detail=message)
        self.error_code = code
        self.wait = wait


def _code_and_message(exc):
    if isinstance(exc, CodedAPIException):
        return exc.error_code, str(exc.detail)
    if isinstance(exc, exceptions.Throttled):
        wait = format_wait(exc.wait)
        return "RATE_LIMITED", f"リクエストが多すぎます。{wait}後にもう一度お試しください"
    for exc_class, code, message in _DEFINITIONS:
        if isinstance(exc, exc_class):
            return code, message
    return str(exc.default_code).upper(), str(exc.detail)


def api_exception_handler(exc, context):
    """すべてのエラーを { "error": { "code", "message" } } の形に統一する。"""
    # get_object_or_404 などが投げる、Django の例外も、同じ形にそろえる
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()
    response = exception_handler(exc, context)
    if response is None:
        return None

    code, message = _code_and_message(exc)

    body = {"code": code, "message": message}
    if isinstance(exc, exceptions.ValidationError):
        body["details"] = response.data
    response.data = {"error": body}
    return response
