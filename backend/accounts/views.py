from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.exceptions import RateLimited, format_wait
from core.throttling import LoginIpThrottle

from . import lockout
from .exceptions import InvalidCredentials, RefreshInvalid
from .models import User
from .serializers import LoginSerializer, UserSerializer
from .tokens import (
    delete_refresh_cookie,
    parse_refresh_token,
    revoke_all_tokens,
    set_refresh_cookie,
)


def locked_error(wait):
    return RateLimited(
        "LOGIN_LOCKED",
        f"ログインの試行回数が上限に達しました。{format_wait(wait)}後にもう一度お試しください",
        wait,
    )


class LoginView(APIView):
    authentication_classes = []
    throttle_classes = [LoginIpThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            raise InvalidCredentials()
        email = serializer.validated_data["email"]

        # ロック中は、正しいパスワードでもログインできない
        if wait := lockout.remaining_lock_seconds(email):
            raise locked_error(wait)

        user = authenticate(request, username=email, password=serializer.validated_data["password"])
        if user is None:  # パスワード違い・未登録・無効化済みのいずれも同じ扱い
            if locked_for := lockout.record_failure(email):
                raise locked_error(locked_for)
            raise InvalidCredentials()

        lockout.reset_failures(email)
        update_last_login(None, user)
        refresh = RefreshToken.for_user(user)
        response = Response(
            {"access": str(refresh.access_token), "user": UserSerializer(user).data}
        )
        set_refresh_cookie(response, refresh)
        return response


class RefreshView(APIView):
    authentication_classes = []

    def post(self, request):
        old_token = parse_refresh_token(request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME))
        if old_token is None:
            raise RefreshInvalid()

        user = User.objects.filter(id=old_token[settings.SIMPLE_JWT["USER_ID_CLAIM"]]).first()
        if user is None or not user.is_active:
            if user is not None:
                revoke_all_tokens(user.id)
            raise RefreshInvalid()

        # リフレッシュトークンは使い捨て。使ったものは無効にし、新しいものに入れ替える
        new_token = RefreshToken.for_user(user)
        old_token.blacklist()
        response = Response({"access": str(new_token.access_token)})
        set_refresh_cookie(response, new_token)
        return response


class LogoutView(APIView):
    authentication_classes = []

    def post(self, request):
        raw_token = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        if raw_token:
            try:
                RefreshToken(raw_token).blacklist()
            except TokenError:
                pass  # すでに無効なトークンは、そのままCookieだけ削除する
        response = Response(status=status.HTTP_204_NO_CONTENT)
        delete_refresh_cookie(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
