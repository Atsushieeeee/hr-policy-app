from unittest.mock import patch

import pytest

from rag.base import RagError

URL = "/api/v1/chat/messages"


@pytest.fixture(autouse=True)
def use_fake_rag(settings):
    # テストではAIを呼ばず、固定の回答を返す実装を使う
    settings.RAG_BACKEND = "fake"


def post(client, body):
    return client.post(URL, data=body, content_type="application/json")


def test_returns_answer_with_sources(client):
    response = post(client, {"question": "有給休暇は何日ですか？"})

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert "有給休暇は何日ですか？" in body["answer"]
    assert body["sources"] == [{"article": "第7条", "page": 2}]


@pytest.mark.parametrize("question", ["", "   ", "あ" * 1001])
def test_rejects_invalid_question(client, question):
    response = post(client, {"question": question})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_rejects_missing_question(client):
    response = post(client, {})

    assert response.status_code == 400


def test_accepts_question_of_max_length(client):
    response = post(client, {"question": "あ" * 1000})

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("status", "code"),
    [(429, "AI_RATE_LIMITED"), (503, "AI_UNAVAILABLE"), (502, "AI_ERROR")],
)
def test_returns_ai_error_with_matching_status(client, status, code):
    error = RagError("AIでエラー", code=code, status=status)
    with patch("chat.views.get_rag_client") as get_client:
        get_client.return_value.answer.side_effect = error
        response = post(client, {"question": "質問"})

    assert response.status_code == status
    assert response.json() == {"error": {"code": code, "message": "AIでエラー"}}
