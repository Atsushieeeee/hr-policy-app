import logging
from pathlib import Path

from django.conf import settings
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from .base import Answer, RagError, Source
from .prompts import NOT_FOUND_MESSAGE, SYSTEM_PROMPT, build_user_content

logger = logging.getLogger(__name__)

DUMMY_POLICY_PATH = Path(__file__).parent / "data" / "dummy_policy.txt"


class _SourceSchema(BaseModel):
    article: str
    page: int | None = None


class _AnswerSchema(BaseModel):
    found: bool
    answer: str
    sources: list[_SourceSchema] = []


class GeminiClient:
    """規程の全文をプロンプトに含めて回答させる実装（全文コンテキスト方式）。

    フェーズ0では、固定のダミー規程を使う。規程のアップロード機能（フェーズ2）で、DBの抽出テキストに置き換える。
    """

    def __init__(self, api_key: str, model: str, timeout_sec: int):
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_sec * 1000),
        )
        self._model = model
        self._policy_text = DUMMY_POLICY_PATH.read_text(encoding="utf-8")

    def answer(self, question: str) -> Answer:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=build_user_content(self._policy_text, question),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=_AnswerSchema,
                    temperature=0.2,
                ),
            )
        except errors.APIError as e:
            logger.error("Gemini API error: code=%s status=%s message=%s", e.code, e.status, e.message)
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
