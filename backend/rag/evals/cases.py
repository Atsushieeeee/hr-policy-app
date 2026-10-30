"""評価セット。samples/dummy_policy.pdf（全13条）に基づく。

ページは、サンプルの条とページの対応（1ページ目: 第1〜4条、2ページ目: 第5〜8条、
3ページ目: 第9〜13条）による。PDFと食い違っていないかは、テストで確認している。
"""

from rag.base import Turn

from .scoring import EvalCase


def _case(id, kind, question, article, page, history=()):
    return EvalCase(
        id=id,
        kind=kind,
        question=question,
        found=article is not None,
        article=article,
        page=page,
        history=tuple(history),
    )


def _direct(id, question, article, page):
    return _case(id, "direct", question, article, page)


def _paraphrase(id, question, article, page):
    return _case(id, "paraphrase", question, article, page)


def _none(id, question):
    return _case(id, "none", question, None, None)


def _followup(id, history, question, article, page):
    return _case(id, "followup", question, article, page, history=[Turn(*history)])


CASES = [
    # 直接の質問
    _direct("direct-01", "年次有給休暇は何日もらえますか？", "第7条", 2),
    _direct("direct-02", "所定労働時間は何時間ですか？", "第3条", 1),
    _direct("direct-03", "休憩時間は何時から何時までですか？", "第3条", 1),
    _direct("direct-04", "給料の支払日はいつですか？", "第10条", 3),
    _direct("direct-05", "結婚するときの慶弔休暇は何日ですか？", "第8条", 2),
    _direct("direct-06", "通勤手当の上限はいくらですか？", "第11条", 3),
    _direct("direct-07", "定年は何歳ですか？", "第13条", 3),
    _direct("direct-08", "退職するときは、いつまでに申し出ればよいですか？", "第12条", 3),
    _direct("direct-09", "時間外労働をするときに必要な手続きは？", "第5条", 2),
    _direct("direct-10", "夏季休暇は何日ありますか？", "第4条", 1),
    _direct("direct-11", "年末年始の休みは、いつからいつまでですか？", "第4条", 1),
    _direct("direct-12", "契約社員にも、この規則は適用されますか？", "第2条", 1),
    _direct("direct-13", "病気で休職できる期間は？", "第9条", 3),
    _direct("direct-14", "深夜に働いた場合の手当は？", "第6条", 2),
    _direct("direct-15", "配偶者が出産したときの休暇は何日ですか？", "第8条", 2),
    _direct("direct-16", "休職中の賃金は支払われますか？", "第9条", 3),
    # 言い換え
    _paraphrase("paraphrase-01", "有給って、半日だけでも使えますか？", "第7条", 2),
    _paraphrase("paraphrase-02", "有給の権利は、いつまで残りますか？", "第7条", 2),
    _paraphrase("paraphrase-03", "始業は何時ですか？", "第3条", 1),
    _paraphrase("paraphrase-04", "毎週の休みは何曜日ですか？", "第4条", 1),
    _paraphrase("paraphrase-05", "定期代は、いくらまで会社が出してくれますか？", "第11条", 3),
    _paraphrase("paraphrase-06", "会社を辞めたいときの手続きを教えてください", "第12条", 3),
    _paraphrase("paraphrase-07", "60歳になったあとも、働き続けられますか？", "第13条", 3),
    _paraphrase("paraphrase-08", "親が亡くなったとき、何日休めますか？", "第8条", 2),
    _paraphrase("paraphrase-09", "祖父母が亡くなったときの休みは？", "第8条", 2),
    _paraphrase("paraphrase-10", "残業するには、誰の許可が要りますか？", "第5条", 2),
    _paraphrase("paraphrase-11", "祝日は休みですか？", "第4条", 1),
    _paraphrase("paraphrase-12", "入社してから、どれくらいで有給がもらえますか？", "第7条", 2),
    # 規程に記載がない質問（該当なしを期待する）
    _none("none-01", "副業は認められていますか？"),
    _none("none-02", "育児休業は取得できますか？"),
    _none("none-03", "賞与（ボーナス）はいつ支給されますか？"),
    _none("none-04", "退職金はいくらもらえますか？"),
    _none("none-05", "在宅勤務はできますか？"),
    _none("none-06", "昇給は年に何回ありますか？"),
    _none("none-07", "介護休業は何日取れますか？"),
    _none("none-08", "今日の東京の天気を教えてください"),
    # 追質問（直前の往復を前提にした質問）
    _followup(
        "followup-01",
        ("年次有給休暇は何日もらえますか？", "入社後6か月継続勤務した場合は、10日です。"),
        "それは、半日単位でも取れますか？",
        "第7条",
        2,
    ),
    _followup(
        "followup-02",
        ("定年は何歳ですか？", "満60歳です。"),
        "その後も働き続けることはできますか？",
        "第13条",
        3,
    ),
    _followup(
        "followup-03",
        ("病気で休職できる期間は？", "勤続1年以上5年未満は6か月、5年以上は1年です。"),
        "その間の給料は出ますか？",
        "第9条",
        3,
    ),
    _followup(
        "followup-04",
        ("退職するときの手続きは？", "退職希望日の1か月前までに、退職願を提出します。"),
        "それは誰に出せばいいですか？",
        "第12条",
        3,
    ),
    _followup(
        "followup-05",
        ("通勤手当は出ますか？", "認めた経路の実費が支給されます。"),
        "上限はありますか？",
        "第11条",
        3,
    ),
    _followup(
        "followup-06",
        ("結婚するときの慶弔休暇は何日ですか？", "5日です。"),
        "配偶者が出産した場合は？",
        "第8条",
        2,
    ),
    _followup(
        "followup-07",
        ("育児休業は取得できますか？", "就業規則に該当する記載が見つかりませんでした。"),
        "それは男性でも取れますか？",
        None,
        None,
    ),
]
