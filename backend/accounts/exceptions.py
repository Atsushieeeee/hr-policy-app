from rest_framework import status

from core.exceptions import CodedAPIException


class InvalidCredentials(CodedAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "INVALID_CREDENTIALS"
    # ID・パスワードのどちらが違うか、無効なユーザーかどうかを区別しない
    default_detail = "メールアドレスまたはパスワードが正しくありません"


class RefreshInvalid(CodedAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "REFRESH_INVALID"
    default_detail = "ログインの有効期限が切れました。もう一度ログインしてください"
