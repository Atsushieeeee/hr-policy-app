import hashlib
import re
import unicodedata

from django.db import transaction

from .models import ChatMessage, ChatSession

# 質問の末尾の、疑問符・句点と空白（「有給は何日？」と「有給は何日」を同じ質問として数える）
_TRAILING = re.compile(r"[？?。.\s]+$")
_WHITESPACE = re.compile(r"\s+")


def normalize_question(text):
    """同じ質問を、完全一致で集計できるように、表記のゆれをそろえる。"""
    text = unicodedata.normalize("NFKC", text)
    text = _WHITESPACE.sub(" ", text.strip()).lower()
    return _TRAILING.sub("", text)


def hash_question(normalized):
    """正規化した質問の、集計用の値。空の質問は、集計の対象にしない（空文字）。"""
    return hashlib.sha256(normalized.encode()).hexdigest() if normalized else ""


def find_session(user, session_id):
    """ユーザー自身の会話を返す。他人の会話、存在しない会話は None。"""
    return ChatSession.objects.filter(id=session_id, user=user).first()


@transaction.atomic
def save_exchange(user, session, question, answer, policy):
    """質問と回答を、1つのトランザクションで保存する。session が None なら、新しい会話を作る。

    返り値は、(会話, 回答のメッセージ)。
    """
    if session is None:
        session = ChatSession.objects.create(user=user)
    normalized = normalize_question(question)
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.USER,
        content=question,
        normalized_question=normalized,
        question_hash=hash_question(normalized),
    )
    reply = ChatMessage.objects.create(
        session=session,
        role=ChatMessage.Role.ASSISTANT,
        content=answer.text,
        sources=[
            {"policy_id": policy.id, "article": s.article, "page": s.page} for s in answer.sources
        ],
        is_no_answer=not answer.found,
    )
    return session, reply
