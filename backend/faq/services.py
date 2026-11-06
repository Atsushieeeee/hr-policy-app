from django.db.models import Max

from policies.models import PolicyDocument

from .models import FAQ


def current_policy_snapshot() -> dict:
    """登録時の規程の情報。規程が未登録なら、空。"""
    policy = PolicyDocument.objects.filter(status=PolicyDocument.Status.READY).first()
    return {"policy_id": policy.id, "sha256": policy.sha256} if policy else {}


def next_sort_order() -> int:
    """新しいFAQを、末尾に置くための並び順。"""
    last = FAQ.objects.aggregate(last=Max("sort_order"))["last"]
    return 0 if last is None else last + 1


def mark_published_for_review() -> int:
    """公開中のFAQを、すべて「要確認」にする（規程を置き換えたとき）。変えた件数を返す。"""
    return FAQ.objects.filter(status=FAQ.Status.PUBLISHED).update(status=FAQ.Status.NEEDS_REVIEW)


def publish_reviewed() -> int:
    """「要確認」のFAQを、すべて公開に戻す。変えた件数を返す。"""
    return FAQ.objects.filter(status=FAQ.Status.NEEDS_REVIEW).update(status=FAQ.Status.PUBLISHED)
