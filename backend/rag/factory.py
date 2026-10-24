from django.conf import settings

from .base import RagClient
from .fake import FakeClient


def get_rag_client() -> RagClient:
    backend = settings.RAG_BACKEND
    if backend == "fake":
        return FakeClient()
    if backend == "gemini":
        from .gemini import GeminiClient

        return GeminiClient(
            api_key=settings.GEMINI_API_KEY,
            model=settings.GEMINI_MODEL,
            timeout_sec=settings.GEMINI_TIMEOUT_SEC,
        )
    raise ValueError(f"未対応のRAG_BACKENDです: {backend}")
