from rest_framework_simplejwt.authentication import JWTAuthentication


class AccessTokenAuthentication(JWTAuthentication):
    """X-Access-Token ヘッダのアクセストークンで認証する。

    公開時にBasic認証を前段に置くと Authorization ヘッダが使えなくなるため、別のヘッダで送る。
    ユーザーはリクエストのたびにDBから読み直す。無効化（is_active=false）や権限の変更は、
    次のリクエストから反映される。
    """

    header_name = "HTTP_X_ACCESS_TOKEN"

    def authenticate(self, request):
        raw_token = request.META.get(self.header_name)
        if not raw_token:
            return None
        validated_token = self.get_validated_token(raw_token.encode())
        return self.get_user(validated_token), validated_token

    def authenticate_header(self, request):
        # 認証が必要なAPIで、403ではなく401を返すために必要
        return "AccessToken"
