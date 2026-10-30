from rest_framework import exceptions, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.throttling import ChatUserDayThrottle, ChatUserMinuteThrottle, check_ai_budget
from policies.exceptions import PolicyNotRegistered
from policies.services import current_policy
from rag.base import RagError
from rag.factory import get_rag_client

from .services import find_session, save_exchange

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

        check_ai_budget(request, self)  # AI側の上限を超える前に、こちらで止める

        try:
            answer = get_rag_client().answer(question, policy.extracted_text)
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
