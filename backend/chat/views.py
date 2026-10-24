from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from rag.base import RagError
from rag.factory import get_rag_client

MAX_QUESTION_LENGTH = 1000


class QuestionSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=MAX_QUESTION_LENGTH, trim_whitespace=True)


def error_response(code: str, message: str, http_status: int) -> Response:
    return Response({"error": {"code": code, "message": message}}, status=http_status)


class ChatMessageView(APIView):
    """質問を受け取り、就業規則に基づく回答を返す。"""

    def post(self, request):
        serializer = QuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                f"質問は1〜{MAX_QUESTION_LENGTH}文字で入力してください。",
                status.HTTP_400_BAD_REQUEST,
            )

        try:
            answer = get_rag_client().answer(serializer.validated_data["question"])
        except RagError as e:
            return error_response(e.code, e.message, e.status)

        return Response(
            {
                "answer": answer.text,
                "found": answer.found,
                "sources": [{"article": s.article, "page": s.page} for s in answer.sources],
            }
        )
