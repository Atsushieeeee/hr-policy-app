import re

import pytest
from django.conf import settings as django_settings
from django.core.management import call_command

from policies.services import extract_policy_text
from rag.base import Answer, RagError, Source
from rag.evals.cases import CASES
from rag.evals.scoring import EvalCase, run_eval, score_case, summarize
from rag.fake import FakeClient

SAMPLE_PDF = str(django_settings.BASE_DIR.parent / "samples" / "dummy_policy.pdf")


def case(found=True, article="第7条", page=2, **kwargs):
    return EvalCase(
        id="c", kind="direct", question="q", found=found, article=article, page=page, **kwargs
    )


def answer(found=True, *sources):
    return Answer(text="a", sources=[Source(a, p) for a, p in sources], found=found)


class ScriptedClient:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def answer(self, question, policy_text, history=()):
        self.calls.append((question, policy_text, history))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class TestScoreCase:
    def test_matching_article_and_page_pass(self):
        result = score_case(case(), answer(True, ("第7条", 2)))

        assert result.passed
        assert result.article_ok and result.page_ok

    def test_article_matches_with_title_or_full_width_digits(self):
        for text in ("第7条（年次有給休暇）", "第７条", "第7条第2項"):
            assert score_case(case(), answer(True, (text, 2))).article_ok

    def test_article_does_not_match_a_longer_number(self):
        assert not score_case(case(), answer(True, ("第17条", 2))).article_ok

    def test_any_source_may_match(self):
        result = score_case(case(), answer(True, ("第3条", 1), ("第7条", 2)))

        assert result.passed

    def test_wrong_article_or_page_fails(self):
        wrong_article = score_case(case(), answer(True, ("第8条", 2)))
        wrong_page = score_case(case(), answer(True, ("第7条", 3)))

        assert wrong_article.article_ok is False and not wrong_article.passed
        assert wrong_page.page_ok is False and not wrong_page.passed

    def test_not_found_when_expected_found_fails_all(self):
        result = score_case(case(), answer(False))

        assert not result.found_ok
        assert result.article_ok is False and result.page_ok is False

    def test_no_answer_case_passes_when_not_found(self):
        result = score_case(case(found=False, article=None, page=None), answer(False))

        assert result.passed
        assert result.article_ok is None and result.page_ok is None

    def test_no_answer_case_fails_when_answered(self):
        result = score_case(case(found=False, article=None, page=None), answer(True, ("第7条", 2)))

        assert not result.passed


class TestSummarize:
    def test_ratios_exclude_errors_and_unexpected_fields(self):
        results = [
            score_case(case(), answer(True, ("第7条", 2))),  # 合格
            score_case(case(), answer(True, ("第8条", 2))),  # 条が違う
            score_case(case(found=False, article=None, page=None), answer(False)),  # 合格
            score_case(case(found=False, article=None, page=None), answer(True)),  # 判定が違う
        ]
        results.append(run_eval(ScriptedClient(RagError("x", "AI_BUSY")), "", [case()])[0])

        summary = summarize(results)

        assert (summary.total, summary.errors, summary.passed) == (5, 1, 2)
        assert (summary.found.hit, summary.found.total) == (3, 4)
        assert (summary.article.hit, summary.article.total) == (1, 2)
        assert (summary.page.hit, summary.page.total) == (2, 2)
        assert summary.pass_rate == pytest.approx(0.4)

    def test_empty(self):
        summary = summarize([])

        assert summary.pass_rate == 0.0
        assert str(summary.found) == "―"


class TestRunEval:
    def test_sleeps_between_cases_and_passes_history(self):
        cases = [case(), case(history=("h",))]
        client = ScriptedClient(answer(True, ("第7条", 2)), answer(True, ("第7条", 2)))
        sleeps = []

        results = run_eval(client, "規程", cases, interval=5, sleep=sleeps.append)

        assert [r.passed for r in results] == [True, True]
        assert sleeps == [5]
        assert client.calls[0] == ("q", "規程", ())
        assert client.calls[1][2] == ("h",)

    def test_ai_error_is_recorded_and_the_run_continues(self):
        client = ScriptedClient(RagError("混み合っています", "AI_BUSY"), answer(True, ("第7条", 2)))

        results = run_eval(client, "", [case(), case()], sleep=lambda _: None)

        assert results[0].error == "AI_BUSY: 混み合っています"
        assert not results[0].passed
        assert results[1].passed

    def test_on_result_is_called_for_each_case(self):
        seen = []

        run_eval(FakeClient(), "", [case(), case()], on_result=seen.append, sleep=lambda _: None)

        assert len(seen) == 2

    def test_fake_client_always_answers_article_7_page_2(self):
        results = run_eval(FakeClient(), "", [case(), case(article="第3条", page=1)])

        assert [r.passed for r in results] == [True, False]


class TestCases:
    def test_ids_are_unique_and_kinds_are_covered(self):
        ids = [c.id for c in CASES]

        assert len(ids) == len(set(ids))
        assert {c.kind for c in CASES} == {"direct", "paraphrase", "none", "followup"}
        assert 30 <= len(CASES) <= 50

    def test_expectations_match_the_sample_pdf(self):
        """評価セットが、サンプルのPDFの条とページの対応と食い違っていないか。"""
        with open(SAMPLE_PDF, "rb") as f:
            _, text = extract_policy_text(f.read())
        article_pages = {}
        for page, body in re.findall(r"\[p\.(\d+)\]\n(.*?)(?=\[p\.\d+\]|\Z)", text, re.DOTALL):
            for number in re.findall(r"第(\d+)条\(", body):
                article_pages[f"第{number}条"] = int(page)

        for c in CASES:
            if c.found:
                assert article_pages[c.article] == c.page, c.id
            else:
                assert c.article is None and c.page is None, c.id

    def test_followups_have_history(self):
        assert all(c.history for c in CASES if c.kind == "followup")
        assert not any(c.history for c in CASES if c.kind != "followup")


class TestCommand:
    def test_runs_with_the_fake_client(self, settings, capsys):
        settings.RAG_BACKEND = "fake"

        call_command("eval_rag", "--policy", SAMPLE_PDF, "--limit", "3", "--interval", "0")

        out = capsys.readouterr().out
        assert "3件を実行します" in out
        assert "合格:" in out and "条の一致率:" in out

    def test_fail_under_exits_with_code_1(self, settings):
        settings.RAG_BACKEND = "fake"

        with pytest.raises(SystemExit) as e:
            call_command(
                "eval_rag", "--policy", SAMPLE_PDF, "--interval", "0", "--fail-under", "0.99"
            )

        assert e.value.code == 1

    def test_missing_policy_file_is_an_error(self):
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            call_command("eval_rag", "--policy", "/nonexistent.pdf")
