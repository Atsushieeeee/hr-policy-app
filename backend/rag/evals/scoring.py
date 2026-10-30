import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import sleep as real_sleep

from rag.base import Answer, RagClient, RagError, Turn

ARTICLE_PATTERN = re.compile(r"第(\d+)条")


@dataclass(frozen=True)
class EvalCase:
    """評価の1件。期待する結果は、規程に記載がある場合は article と page も持つ。"""

    id: str
    kind: str  # direct（直接）/ paraphrase（言い換え）/ none（記載なし）/ followup（追質問）
    question: str
    found: bool
    article: str | None = None
    page: int | None = None
    history: tuple[Turn, ...] = ()


@dataclass(frozen=True)
class CaseResult:
    case: EvalCase
    answer: Answer | None = None
    error: str | None = None
    # 期待がない（記載なしの質問）は None
    article_ok: bool | None = None
    page_ok: bool | None = None

    @property
    def found_ok(self) -> bool:
        return self.answer is not None and self.answer.found == self.case.found

    @property
    def passed(self) -> bool:
        return (
            self.error is None
            and self.found_ok
            and self.article_ok is not False
            and self.page_ok is not False
        )


@dataclass(frozen=True)
class Ratio:
    hit: int
    total: int

    @property
    def value(self) -> float | None:
        return self.hit / self.total if self.total else None

    def __str__(self) -> str:
        if not self.total:
            return "―"
        return f"{self.value:.0%} ({self.hit}/{self.total})"


@dataclass(frozen=True)
class Summary:
    total: int
    errors: int
    passed: int
    found: Ratio
    article: Ratio
    page: Ratio

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def article_numbers(text: str) -> set[str]:
    """「第7条」「第７条（年次有給休暇）」などから、条の番号を取り出す。"""
    return set(ARTICLE_PATTERN.findall(unicodedata.normalize("NFKC", text)))


def score_case(case: EvalCase, answer: Answer) -> CaseResult:
    """回答を採点する。条とページは、根拠（sources）のどれかが期待と合っていれば一致とする。"""
    article_ok = page_ok = None
    if case.found:
        if case.article is not None:
            expected = article_numbers(case.article)
            article_ok = any(article_numbers(s.article) & expected for s in answer.sources)
        if case.page is not None:
            page_ok = any(s.page == case.page for s in answer.sources)
    return CaseResult(case=case, answer=answer, article_ok=article_ok, page_ok=page_ok)


def summarize(results: Sequence[CaseResult]) -> Summary:
    """全体の集計。エラーの件は、一致率の計算から除き、件数だけ数える。"""
    done = [r for r in results if r.error is None]
    with_article = [r for r in done if r.article_ok is not None]
    with_page = [r for r in done if r.page_ok is not None]
    return Summary(
        total=len(results),
        errors=len(results) - len(done),
        passed=sum(r.passed for r in results),
        found=Ratio(sum(r.found_ok for r in done), len(done)),
        article=Ratio(sum(bool(r.article_ok) for r in with_article), len(with_article)),
        page=Ratio(sum(bool(r.page_ok) for r in with_page), len(with_page)),
    )


def run_eval(
    client: RagClient,
    policy_text: str,
    cases: Sequence[EvalCase],
    interval: float = 0,
    on_result: Callable[[CaseResult], None] | None = None,
    sleep: Callable[[float], None] = real_sleep,
) -> list[CaseResult]:
    """評価セットを順に実行する。AIの呼び出し回数の上限に収めるため、件の間隔を空ける。"""
    results = []
    for index, case in enumerate(cases):
        if index:
            sleep(interval)
        try:
            answer = client.answer(case.question, policy_text, case.history)
            result = score_case(case, answer)
        except RagError as e:
            result = CaseResult(case=case, error=f"{e.code}: {e.message}")
        results.append(result)
        if on_result is not None:
            on_result(result)
    return results
