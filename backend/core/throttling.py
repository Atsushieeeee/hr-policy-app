from rest_framework.throttling import SimpleRateThrottle

from .exceptions import RateLimited, format_wait


class LoginIpThrottle(SimpleRateThrottle):
    """ログインの試行回数を、IPアドレスごとに制限する。"""

    scope = "login_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class _ChatUserThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None  # 未認証は、認証の段階で拒否されるため、ここでは数えない
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class ChatUserMinuteThrottle(_ChatUserThrottle):
    scope = "chat_minute"


class ChatUserDayThrottle(_ChatUserThrottle):
    scope = "chat_day"


class _AiGlobalThrottle(SimpleRateThrottle):
    """AI呼び出し全体（全ユーザー合計）の制限。AI側の上限を超える前に、こちらで止める。"""

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": "all"}


class AiGlobalMinuteThrottle(_AiGlobalThrottle):
    scope = "ai_global_minute"


class AiGlobalDayThrottle(_AiGlobalThrottle):
    scope = "ai_global_day"


def check_ai_budget(request, view):
    """AIを呼ぶ直前に、全体の上限を確認する。超えていたら、429（AI_BUSY）にする。"""
    for throttle_class in (AiGlobalMinuteThrottle, AiGlobalDayThrottle):
        throttle = throttle_class()
        if not throttle.allow_request(request, view):
            wait = throttle.wait()
            raise RateLimited(
                "AI_BUSY",
                f"AIが混み合っています。{format_wait(wait)}後にもう一度お試しください",
                wait,
            )
