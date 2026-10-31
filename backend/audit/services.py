import ipaddress
import logging

from django.db import transaction
from rest_framework.throttling import BaseThrottle

from .models import AuditLog

logger = logging.getLogger(__name__)


def client_ip(request) -> str | None:
    """接続元のIPアドレス。プロキシの段数の設定（TRUSTED_PROXY_COUNT）は、レート制限と同じ扱い。"""
    ident = BaseThrottle().get_ident(request)
    try:
        return str(ipaddress.ip_address(ident))
    except ValueError:
        return None


def record(
    action: str,
    *,
    actor=None,
    actor_email: str = "",
    request=None,
    target_type: str = "",
    target_id=None,
    detail: dict | None = None,
) -> None:
    """操作を記録する。記録に失敗しても、本来の操作は失敗させない（ログに残すだけ）。

    detail には、操作ごとに決めた項目だけを入れる（リクエストの中身を、そのまま入れない）。
    パスワードやトークンなどの秘密は、入れてはいけない。
    """
    try:
        # 取引の中で呼ばれても、記録の失敗が、本体の取引を壊さないよう、入れ子の取引にする
        with transaction.atomic():
            AuditLog.objects.create(
                action=action,
                actor=actor,
                actor_email=actor_email or (actor.email if actor is not None else ""),
                target_type=target_type,
                target_id="" if target_id is None else str(target_id),
                detail=detail or {},
                ip=client_ip(request) if request is not None else None,
            )
    except Exception:
        logger.exception("監査ログを記録できませんでした: action=%s", action)
