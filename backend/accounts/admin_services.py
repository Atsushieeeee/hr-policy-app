from django.db import transaction

from .exceptions import CannotRevokeSelf, InvalidTarget, LastAdmin
from .models import User


def _lock_active_admins():
    """有効な管理者の行をロックし、現在の人数の判定と更新を、同時に1つだけにする。"""
    return list(User.objects.select_for_update().filter(is_admin=True, is_active=True))


def _targets(user_ids):
    """対象のユーザー。存在しない・無効なユーザーが含まれていれば、エラーにする。"""
    targets = list(User.objects.filter(id__in=user_ids, is_active=True))
    if len(targets) != len(user_ids):
        raise InvalidTarget()
    return targets


@transaction.atomic
def grant_admin(user_ids):
    """user_ids の全員に管理者権限を付ける（全員成功か、全員失敗）。すでに管理者でもよい。

    実際に権限が変わったユーザーを返す。
    """
    _lock_active_admins()
    targets = _targets(user_ids)
    User.objects.filter(id__in=[u.id for u in targets]).update(is_admin=True)
    return [u for u in targets if not u.is_admin]


@transaction.atomic
def revoke_admin(actor_id, user_ids):
    """user_ids の全員から管理者権限を外す（全員成功か、全員失敗）。管理者でなくてもよい。

    実際に権限が変わったユーザーを返す。
    """
    admins = _lock_active_admins()
    if actor_id in user_ids:
        raise CannotRevokeSelf()
    targets = _targets(user_ids)

    # ロックを取った後の、最新の状態で判定する（同時に、別の管理者が外されていることがある）
    remaining = [a for a in admins if a.id not in {t.id for t in targets}]
    if not remaining:
        raise LastAdmin()
    User.objects.filter(id__in=[t.id for t in targets]).update(is_admin=False)
    return [t for t in targets if t.is_admin]
