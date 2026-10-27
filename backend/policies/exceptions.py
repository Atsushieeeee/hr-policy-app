from rest_framework import status

from core.exceptions import CodedAPIException


class InvalidFile(CodedAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "INVALID_FILE"
    default_detail = "PDFファイルを指定してください"


class FileTooLarge(CodedAPIException):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    error_code = "FILE_TOO_LARGE"
    default_detail = "ファイルが大きすぎます"


class SameFile(CodedAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "SAME_FILE"
    default_detail = "現在登録されている規程と、同じファイルです"


class UploadInProgress(CodedAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "UPLOAD_IN_PROGRESS"
    default_detail = "別のファイルを処理中です。完了してから、もう一度アップロードしてください"


class PolicyNotRegistered(CodedAPIException):
    status_code = status.HTTP_409_CONFLICT
    error_code = "POLICY_NOT_REGISTERED"
    default_detail = "就業規則がまだ登録されていません。管理者に登録を依頼してください"


class PolicyNotFound(CodedAPIException):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "POLICY_NOT_FOUND"
    default_detail = "規程が登録されていません"
