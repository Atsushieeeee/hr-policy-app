from policies.radicals import RADICAL_TABLE
from policies.text import build_policy_text, garbled_ratio, normalize_text


class TestNormalizeText:
    def test_kangxi_radical_is_converted(self):
        # 康熙部首（U+2F6C）は、NFKCで通常の漢字になる
        assert normalize_text("⽬的") == "目的"

    def test_radical_supplement_is_converted_by_table(self):
        # 補助部首（U+2EA0）は、NFKCでは直らないため、対応表で置き換える
        assert normalize_text("国⺠") == "国民"

    def test_fullwidth_characters_are_normalized(self):
        assert normalize_text("（１）") == "(1)"

    def test_spaces_between_japanese_characters_are_removed(self):
        assert normalize_text("就 業 規 則") == "就業規則"

    def test_spaces_between_latin_words_are_kept(self):
        assert normalize_text("Hello World") == "Hello World"

    def test_line_breaks_are_kept(self):
        assert normalize_text("第1条\n目的") == "第1条\n目的"

    def test_table_covers_both_radical_blocks(self):
        # 生成し直したときに、対応表が欠けていないことを確認する
        kangxi = [c for c in RADICAL_TABLE if 0x2F00 <= c < 0x2FE0]
        supplement = [c for c in RADICAL_TABLE if 0x2E80 <= c < 0x2F00]
        assert len(kangxi) == 214
        assert len(supplement) > 100


class TestGarbledRatio:
    def test_clean_text_is_zero(self):
        assert garbled_ratio("就業規則の本文です。") == 0

    def test_empty_text_is_zero(self):
        assert garbled_ratio("  \n ") == 0

    def test_detects_cid_markers(self):
        assert garbled_ratio("(cid:12)(cid:34)") == 1

    def test_detects_private_use_characters(self):
        assert garbled_ratio("ab") == 0.5

    def test_detects_replacement_characters(self):
        assert garbled_ratio("�" + "あ" * 9) == 0.1

    def test_ignores_whitespace(self):
        assert garbled_ratio("�\n \t") == 1


def test_build_policy_text_adds_page_markers():
    text = build_policy_text(["一枚目", "二枚目"])

    assert text.startswith("[p.1]\n一枚目")
    assert "[p.2]\n二枚目" in text
