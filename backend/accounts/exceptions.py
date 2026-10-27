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


class InvalidTarget(CodedAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "INVALID_TARGET"
    default_detail = "存在しない、または無効なユーザーが含まれています"


class CannotRevokeSelf(CodedAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "CANNOT_REVOKE_SELF"
    default_detail = "自分自身の管理者権限は、外せません"


class LastAdmin(CodedAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "LAST_ADMIN"
    default_detail = "管理者が0人になるため、外せません"
