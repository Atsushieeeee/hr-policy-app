import logging
from collections.abc import Sequence

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from .base import Answer, RagError, Source, Turn
from .prompts import NOT_FOUND_MESSAGE, SYSTEM_PROMPT, build_messages

logger = logging.getLogger(__name__)


class _SourceSchema(BaseModel):
    article: str
    page: int | None = None


class _AnswerSchema(BaseModel):
    found: bool
    answer: str
    sources: list[_SourceSchema] = []


class GeminiClient:
    """規程の全文をプロンプトに含めて回答させる実装（全文コンテキスト方式）。"""

    def __init__(self, api_key: str, model: str, timeout_sec: int):
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_sec * 1000),
        )
        self._model = model

    def answer(self, question: str, policy_text: str, history: Sequence[Turn] = ()) -> Answer:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=[
                    types.Content(role=role, parts=[types.Part(text=text)])
                    for role, text in build_messages(policy_text, question, history)
                ],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=_AnswerSchema,
                    temperature=0.2,
                ),
            )
        except errors.APIError as e:
            logger.error(
                "Gemini API error: code=%s status=%s message=%s", e.code, e.status, e.message
            )
            if e.code == 429:
                raise RagError(
                    "AIの利用が混み合っています。しばらくしてからもう一度お試しください。",
                    code="AI_RATE_LIMITED",
                    status=429,
                ) from e
            raise RagError("AIからの回答の取得に失敗しました。", code="AI_ERROR") from e
        except Exception as e:  # タイムアウト・通信エラーなど
            logger.exception("Gemini connection error")
            raise RagError("AIに接続できませんでした。", code="AI_UNAVAILABLE", status=503) from e

        parsed = response.parsed
        if not isinstance(parsed, _AnswerSchema):
            raise RagError("AIの回答を解析できませんでした。", code="AI_INVALID_RESPONSE")

        if not parsed.found:
            return Answer(text=NOT_FOUND_MESSAGE, sources=[], found=False)
        return Answer(
            text=parsed.answer,
            sources=[Source(article=s.article, page=s.page) for s in parsed.sources],
            found=True,
        )
