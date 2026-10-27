"""部首の対応表（policies/radicals.py）を、Unicodeの公式データから生成する。

使い方（コンテナの中で）:
    python -m policies.tools.generate_radicals

PDFから抽出したテキストには、見た目は同じでも、部首用の文字（康熙部首・CJK部首補助）が混ざることがある。
次の2つの公式データから、部首用の文字と、対応する通常の漢字（CJK統合漢字）の対応表を作る。

- CJKRadicals.txt: 康熙部首（214文字）と、補助部首の一部
- NamesList.txt: 補助部首（U+2E80〜U+2EFF）ごとの、対応する漢字の記載
  （例: 「2EA0 CJK RADICAL CIVILIAN / x 6C11」）
"""

import re
import urllib.request
from pathlib import Path

BASE_URL = "https://www.unicode.org/Public/UCD/latest/ucd/"
OUTPUT = Path(__file__).resolve().parent.parent / "radicals.py"

SUPPLEMENT_RANGE = range(0x2E80, 0x2F00)
IDEOGRAPH_RANGES = (range(0x3400, 0x4DC0), range(0x4E00, 0xA000), range(0x20000, 0x32000))


def is_ideograph(code):
    return any(code in r for r in IDEOGRAPH_RANGES)


def fetch(name):
    with urllib.request.urlopen(BASE_URL + name, timeout=60) as response:
        return response.read().decode("utf-8")


def parse_radicals(text):
    """CJKRadicals.txt: 「部首番号; 部首の文字; 対応する漢字」の行を読む。"""
    version = ""
    mapping = {}
    for line in text.splitlines():
        if line.startswith("# CJKRadicals-"):
            version = line.removeprefix("# ").removesuffix(".txt").strip()
        if not line.strip() or line.startswith("#"):
            continue
        _, radical, ideograph = (field.strip() for field in line.split(";"))
        if radical and ideograph and radical != ideograph:
            mapping[int(radical, 16)] = int(ideograph, 16)
    return version, mapping


def parse_names_list(text):
    """NamesList.txt: 補助部首の項目に続く「x 6C11」（対応する漢字）の行を読む。

    複数ある場合は、最初の漢字を採用する。
    """
    mapping = {}
    current = None
    for line in text.splitlines():
        head = re.match(r"^([0-9A-F]{4,6})\t", line)
        if head:
            code = int(head.group(1), 16)
            current = code if code in SUPPLEMENT_RANGE else None
            continue
        ref = re.match(r"^\tx ([0-9A-F]{4,6})$", line)
        if current is not None and ref and current not in mapping:
            target = int(ref.group(1), 16)
            if is_ideograph(target):
                mapping[current] = target
    return mapping


def main():
    version, mapping = parse_radicals(fetch("CJKRadicals.txt"))
    for code, target in parse_names_list(fetch("NamesList.txt")).items():
        mapping.setdefault(code, target)  # CJKRadicals.txt の記載を優先する

    lines = [
        f"    0x{code:04X}: 0x{target:04X},  # {chr(code)} → {chr(target)}"
        for code, target in sorted(mapping.items())
    ]
    OUTPUT.write_text(
        '"""部首用の文字 → 通常の漢字の対応表。\n\n'
        f"Unicodeの公式データ（{version}、NamesList.txt。{BASE_URL}）から、\n"
        "policies/tools/generate_radicals.py で生成した。手で編集しない。\n"
        '"""\n\n'
        "RADICAL_TABLE = {\n" + "\n".join(lines) + "\n}\n",
        encoding="utf-8",
    )
    print(f"{len(mapping)}件を書き出しました: {OUTPUT}")


if __name__ == "__main__":
    main()
