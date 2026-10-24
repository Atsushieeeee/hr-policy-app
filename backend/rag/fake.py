from .base import Answer, Source


class FakeClient:
    """テスト・AIを使わない動作確認用の実装。固定の回答を返す。"""

    def answer(self, question: str) -> Answer:
        return Answer(
            text=f"（ダミー回答）「{question}」への回答です。",
            sources=[Source(article="第7条", page=2)],
            found=True,
        )
