"""PDFから抽出したテキストの正規化と、品質の確認。"""

import re
import unicodedata

from .radicals import RADICAL_TABLE

_RADICALS = str.maketrans(RADICAL_TABLE)

# 日本語（かな・漢字・記号）の文字どうしの間に、PDFの抽出で入り込む空白を取り除く
_CJK = "　-〿぀-ヿ㐀-䶿一-鿿＀-￯"
_SPACE_BETWEEN_CJK = re.compile(rf"(?<=[{_CJK}])[ \t]+(?=[{_CJK}])")

# 文字化けの目印: 「(cid:123)」、私用領域の文字、置換文字
_GARBLED = re.compile(r"\(cid:\d+\)|[-�]")


def normalize_text(text):
    """見た目は同じでも別の文字コードの文字（部首用の文字など）を、通常の文字に直す。"""
    text = text.translate(_RADICALS)  # NFKCでは直らない部首の補助文字を、先に置き換える
    text = unicodedata.normalize("NFKC", text)
    return _SPACE_BETWEEN_CJK.sub("", text)


def garbled_ratio(text):
    """文字（空白を除く）のうち、文字化けの目印が占める割合。"""
    body = re.sub(r"\s+", "", text)
    if not body:
        return 0.0
    garbled = sum(len(m.group()) for m in _GARBLED.finditer(body))
    return garbled / len(body)


def build_policy_text(pages):
    """ページごとのテキストを、ページの区切り（[p.N]）つきの1つのテキストにする。"""
    parts = (f"[p.{number}]\n{text.strip()}\n" for number, text in enumerate(pages, start=1))
    return "\n".join(parts)
