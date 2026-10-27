from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Source:
    """回答の根拠となった規程の箇所"""

    article: str
    page: int | None


@dataclass(frozen=True)
class Answer:
    text: str
    sources: list[Source] = field(default_factory=list)
    # 規程に該当する記載が見つかったか（見つからない場合は定型文で回答する）
    found: bool = True


class RagError(Exception):
    """AI側の呼び出しに失敗した場合の例外"""

    def __init__(self, message: str, code: str = "AI_ERROR", status: int = 502):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


class RagClient(Protocol):
    """就業規則に基づく回答を返すクライアントの共通インターフェース。

    実装を差し替えられるようにしている（Gemini → さくらのAI Engine）。
    規程のテキスト（現行の規程の全文）は、質問のたびに渡す。
    """

    def answer(self, question: str, policy_text: str) -> Answer: ...
