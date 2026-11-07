from django.db.models import Count, Exists, Max, OuterRef, Q, Subquery

from chat.models import ChatMessage
from chat.services import hash_question, normalize_question
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


def _reply_id_of_question():
    """質問のメッセージに対する、回答のメッセージ（同じ会話で、直後の回答）のID。"""
    return Subquery(
        ChatMessage.objects.filter(
            session=OuterRef("session"), id__gt=OuterRef("id"), role=ChatMessage.Role.ASSISTANT
        )
        .order_by("id")
        .values("id")[:1]
    )


def _questions_with_reply():
    """質問のメッセージ（集計の対象）に、回答のIDと、根拠つきの回答か、を付ける。"""
    useful_reply = ChatMessage.objects.filter(id=OuterRef("reply_id"), is_no_answer=False).exclude(
        sources=[]
    )
    return (
        ChatMessage.objects.filter(role=ChatMessage.Role.USER)
        .exclude(question_hash="")
        .annotate(reply_id=_reply_id_of_question())
        .annotate(has_useful_reply=Exists(useful_reply))
    )


def registered_hashes() -> set[str]:
    """登録済みのFAQに対応する、質問の集計用の値（question_hash）。

    管理者が質問文を直しても判定できるよう、元になったチャットの質問と、FAQの質問文の両方を使う。
    """
    faqs = FAQ.objects.all()
    hashes = {hash_question(normalize_question(faq.question)) for faq in faqs}
    source_ids = [faq.source_message_id for faq in faqs if faq.source_message_id]
    sources = ChatMessage.objects.filter(id__in=source_ids)
    for message in sources:
        asked = (
            ChatMessage.objects.filter(
                session_id=message.session_id, id__lt=message.id, role=ChatMessage.Role.USER
            )
            .order_by("-id")
            .first()
        )
        if asked is not None:
            hashes.add(asked.question_hash)
    hashes.discard("")
    return hashes


def candidate_groups(include_registered: bool):
    """質問を、正規化した質問ごとにまとめた一覧（聞かれた回数の多い順）。

    根拠つきの回答が1回もない質問（「該当なし」や根拠なしだけ）は、含めない。
    """
    groups = (
        _questions_with_reply()
        .values("question_hash")
        .annotate(
            ask_count=Count("id"),
            user_count=Count("session__user", distinct=True),
            last_asked_at=Max("created_at"),
            last_id=Max("id"),
            useful_question_id=Max("id", filter=Q(has_useful_reply=True)),
        )
        .filter(useful_question_id__isnull=False)
        .order_by("-ask_count", "-last_id")
    )
    if not include_registered:
        groups = groups.exclude(question_hash__in=registered_hashes())
    return groups


def candidate_details(groups: list[dict]) -> list[dict]:
    """まとめた質問に、最新の根拠つきの回答と、登録済みかを付ける（質問者の情報は含めない）。"""
    questions = {
        q.id: q
        for q in _questions_with_reply().filter(id__in=[g["useful_question_id"] for g in groups])
    }
    replies = ChatMessage.objects.in_bulk([q.reply_id for q in questions.values()])
    registered = registered_hashes()
    details = []
    for group in groups:
        question = questions[group["useful_question_id"]]
        reply = replies[question.reply_id]
        details.append(
            {
                "question": question.content,
                "ask_count": group["ask_count"],
                "user_count": group["user_count"],
                "last_asked_at": group["last_asked_at"],
                "answer": reply.content,
                "sources": reply.sources,
                "source_message_id": reply.id,
                "registered": group["question_hash"] in registered,
            }
        )
    return details
