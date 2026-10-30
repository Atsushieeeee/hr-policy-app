from rest_framework import exceptions, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.throttling import ChatUserDayThrottle, ChatUserMinuteThrottle, check_ai_budget
from policies.exceptions import PolicyNotRegistered
from policies.services import current_policy
from rag.base import RagError
from rag.factory import get_rag_client

from .models import ChatMessage
from .services import (
    find_session,
    latest_session,
    recent_history,
    recent_messages,
    save_exchange,
    start_session,
)

MAX_QUESTION_LENGTH = 1000


class QuestionSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=MAX_QUESTION_LENGTH, trim_whitespace=True)
    # 省略したときは、新しい会話を始める
    session_id = serializers.IntegerField(required=False, min_value=1)


def error_response(code: str, message: str, http_status: int) -> Response:
    return Response({"error": {"code": code, "message": message}}, status=http_status)


class ChatMessageView(APIView):
    """質問を受け取り、就業規則に基づく回答を返す。ログイン済みなら、管理者権限の有無に関わらず使える。"""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ChatUserMinuteThrottle, ChatUserDayThrottle]

    def post(self, request):
        serializer = QuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                f"質問は1〜{MAX_QUESTION_LENGTH}文字で入力してください。",
                status.HTTP_400_BAD_REQUEST,
            )

        question = serializer.validated_data["question"]
        session = None
        if "session_id" in serializer.validated_data:
            session = find_session(request.user, serializer.validated_data["session_id"])
            if session is None:
                # 他人の会話と、存在しない会話は、区別しない
                raise exceptions.NotFound()

        policy = current_policy()
        if policy is None:
            raise PolicyNotRegistered()  # 規程がないときは、AIを呼ばない（AIの利用枠も使わない）

        history = recent_history(session)

        check_ai_budget(request, self)  # AI側の上限を超える前に、こちらで止める

        try:
            answer = get_rag_client().answer(question, policy.extracted_text, history)
        except RagError as e:
            return error_response(e.code, e.message, e.status)

        # 回答できたときだけ、保存する（エラーのときは、会話も作らない）
        session, reply = save_exchange(request.user, session, question, answer, policy)

        return Response(
            {
                "session_id": session.id,
                "message_id": reply.id,
                "answer": answer.text,
                "found": answer.found,
                "sources": [{"article": s.article, "page": s.page} for s in answer.sources],
            }
        )


def message_data(message):
    """画面に返す、メッセージ1件。found は回答だけに付く（質問では null）。"""
    is_reply = message.role == ChatMessage.Role.ASSISTANT
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "found": (not message.is_no_answer) if is_reply else None,
        "sources": [{"article": s["article"], "page": s["page"]} for s in message.sources],
        "created_at": message.created_at,
    }


class ChatSessionView(APIView):
    """「新しい会話」を始める。直前の会話が空のときは、新しく作らず、その会話を返す。"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        session, created = start_session(request.user)
        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response({"session_id": session.id}, status=http_status)


class ChatCurrentSessionView(APIView):
    """ログインユーザーの最新の会話と、そのメッセージ。画面を開き直しても、会話が続くようにする。"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        session = latest_session(request.user)
        if session is None:
            return Response({"session_id": None, "messages": []})
        return Response(
            {
                "session_id": session.id,
                "messages": [message_data(m) for m in recent_messages(session)],
            }
        )
