"""ログインの連続失敗によるアカウントのロック。

メールアドレスごとに、連続の失敗回数を数える。未登録のメールアドレスも同じように数えるため、
ロックの有無から、アカウントが存在するかどうかは分からない。
"""

import hashlib
import math
import time

from django.conf import settings
from django.core.cache import cache

from .models import User


def now():
    return time.time()


def _key(kind, email):
    digest = hashlib.sha256(User.objects.normalize(email).encode()).hexdigest()
    return f"login_{kind}:{digest}"


def remaining_lock_seconds(email):
    """ロック中なら、解除までの秒数を返す。ロックされていなければ 0。"""
    until = cache.get(_key("lock", email))
    if until and until > now():
        return math.ceil(until - now())
    return 0


def record_failure(email):
    """失敗を記録する。上限に達してロックした場合は、ロックの秒数を返す。それ以外は 0。"""
    key = _key("fail", email)
    count = (cache.get(key) or 0) + 1
    if count >= settings.LOGIN_MAX_FAILURES:
        lock_seconds = settings.LOGIN_LOCK_SECONDS
        cache.set(_key("lock", email), now() + lock_seconds, lock_seconds)
        cache.delete(key)
        return settings.LOGIN_LOCK_SECONDS
    cache.set(key, count, settings.LOGIN_LOCK_SECONDS)
    return 0


def reset_failures(email):
    cache.delete(_key("fail", email))
