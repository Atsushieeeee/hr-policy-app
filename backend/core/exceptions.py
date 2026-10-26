from rest_framework import exceptions
from rest_framework.views import exception_handler

# 例外の種類ごとの、エラーコードと利用者向けメッセージ
_DEFINITIONS = [
    (exceptions.NotAuthenticated, "UNAUTHENTICATED", "ログインが必要です"),
    (exceptions.AuthenticationFailed, "TOKEN_INVALID", "認証の有効期限が切れたか、無効です"),
    (exceptions.PermissionDenied, "FORBIDDEN", "この操作を行う権限がありません"),
    (exceptions.NotFound, "NOT_FOUND", "対象が見つかりません"),
    (exceptions.MethodNotAllowed, "METHOD_NOT_ALLOWED", "許可されていない操作です"),
    (exceptions.Throttled, "RATE_LIMITED", "リクエストが多すぎます。しばらくお待ちください"),
    (exceptions.ParseError, "BAD_REQUEST", "リクエストの形式が正しくありません"),
    (exceptions.ValidationError, "VALIDATION_ERROR", "入力内容が正しくありません"),
]


class CodedAPIException(exceptions.APIException):
    """エラーコードを持つ、アプリ独自の例外の基底クラス。"""

    error_code = "ERROR"


def _code_and_message(exc):
    if isinstance(exc, CodedAPIException):
        return exc.error_code, str(exc.detail)
    for exc_class, code, message in _DEFINITIONS:
        if isinstance(exc, exc_class):
            return code, message
    return str(exc.default_code).upper(), str(exc.detail)


def api_exception_handler(exc, context):
    """すべてのエラーを { "error": { "code", "message" } } の形に統一する。"""
    response = exception_handler(exc, context)
    if response is None:
        return None

    code, message = _code_and_message(exc)

    body = {"code": code, "message": message}
    if isinstance(exc, exceptions.ValidationError):
        body["details"] = response.data
    response.data = {"error": body}
    return response
