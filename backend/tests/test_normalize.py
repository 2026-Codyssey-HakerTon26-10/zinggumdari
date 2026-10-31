"""한국어 수·날짜 정규화(SPEC §9.3 값·비교어·단위·같은 절·경계 쌍 검사의 바탕)."""

import pytest

from backend.compiler.normalize import Quantity, clause_at, clause_spans, convert, find_quantities


def one(text: str) -> Quantity:
    qs = find_quantities(text)
    assert len(qs) == 1, qs
    return qs[0]


# 금액(만원)

@pytest.mark.parametrize("text, value", [
    ("7천 5백만 원", 7500),
    ("7,500만원", 7500),
    ("1억 2천만원", 12000),
    ("3억 4,500만 원", 34500),
    ("2억원", 20000),
    ("천만원", 1000),
    ("250만원", 250),
    ("300,000원", 30),
    ("1.5억원", 15000),
    ("백만원", 100),
])
def test_money(text, value):
    q = one(text)
    assert q.kind == "money" and q.value == value and q.comparator is None


def test_money_won_digits():
    q = one("6,458,330원")
    assert q.kind == "money" and q.value == pytest.approx(645.833)


def test_money_span_is_number_and_unit():
    text = "연소득 7천 5백만 원 이하"
    q = one(text)
    assert text[q.start:q.end] == q.raw == "7천 5백만 원"


def test_money_le():
    q = one("5천만 원 이하")
    assert (q.kind, q.value, q.comparator) == ("money", 5000, "<=")


def test_money_monthly_prefix():
    q = one("월 300만원 이하")
    assert (q.kind, q.value, q.comparator) == ("money", 300, "<=")


def test_money_not_inside_word():
    assert find_quantities("인천원도심 재생") == []


def test_money_comma_list():
    assert [q.value for q in find_quantities("5천만원,7천만원")] == [5000, 7000]


# 퍼센트

def test_percent():
    q = one("기준중위소득 150%")
    assert (q.kind, q.value) == ("percent", 150)


def test_percent_fraction():
    q = one("기준 중위소득 100분의 120 이하")
    assert (q.kind, q.value, q.comparator) == ("percent", 120, "<=")
    assert q.raw == "100분의 120"


def test_percent_word():
    q = one("도시근로자 월평균소득의 120퍼센트")
    assert (q.kind, q.value) == ("percent", 120)


# 나이·범위

def test_age_range_words():
    a, b = find_quantities("만 19세 이상 34세 이하")
    assert (a.kind, a.value, a.comparator) == ("age", 19, ">=")
    assert (b.kind, b.value, b.comparator) == ("age", 34, "<=")
    assert a.range_id is not None and a.range_id == b.range_id


def test_age_range_tilde_bare_left():
    a, b = find_quantities("19~34세")
    assert (a.kind, a.value, a.comparator) == ("age", 19, ">=")
    assert (b.kind, b.value, b.comparator) == ("age", 34, "<=")
    assert a.range_id == b.range_id is not None


def test_age_range_tilde_full():
    a, b = find_quantities("만19세~만34세")
    assert (a.value, a.comparator, b.value, b.comparator) == (19, ">=", 34, "<=")
    assert a.range_id == b.range_id is not None


def test_age_range_tilde_with_words():
    a, b = find_quantities("만 19세 이상 ~ 만 34세 이하")
    assert (a.comparator, b.comparator) == (">=", "<=") and a.range_id == b.range_id is not None


def test_age_le():
    q = one("39세 이하")
    assert (q.kind, q.value, q.comparator, q.range_id) == ("age", 39, "<=", None)


def test_age_not_generation():
    assert find_quantities("3세대 동거") == []


def test_two_ranges_get_different_ids():
    qs = find_quantities("19~34세, 100~120%")
    assert [q.kind for q in qs] == ["age", "age", "percent", "percent"]
    assert qs[0].range_id == qs[1].range_id != qs[2].range_id == qs[3].range_id


def test_unrelated_bounds_not_paired():
    a, b = find_quantities("100% 이상인 경우 150% 이하")
    assert a.range_id is None and b.range_id is None


def test_money_range_tilde():
    a, b = find_quantities("5천만~7천만원")
    assert (a.value, a.comparator, b.value, b.comparator) == (5000, ">=", 7000, "<=")


def test_money_range_ambiguous_left_skipped():
    assert [q.value for q in find_quantities("5~7천만원")] == [7000]


# 기간

def test_months():
    q = one("청약통장 가입 6개월 이상")
    assert (q.kind, q.value, q.comparator) == ("months", 6, ">=")


def test_years():
    q = one("2년 이상")
    assert (q.kind, q.value, q.comparator) == ("years", 2, ">=")


def test_year_and_months_compound():
    q = one("1년 6개월")
    assert (q.kind, q.value, q.raw) == ("months", 18, "1년 6개월")


def test_years_within():
    q = one("혼인기간 7년 이내")
    assert (q.kind, q.value, q.comparator) == ("years", 7, "<=")


# 개수

@pytest.mark.parametrize("text, value, cmp", [
    ("2명 이상", 2, ">="),
    ("3인 가구", 3, None),
    ("24회 이상", 24, ">="),
    ("3자녀 이상", 3, ">="),
])
def test_count(text, value, cmp):
    q = one(text)
    assert (q.kind, q.value, q.comparator) == ("count", value, cmp)


# 날짜

@pytest.mark.parametrize("text, value, cmp", [
    ("2026. 3. 30.까지", "2026-03-30", "<="),
    ("2026.03.30", "2026-03-30", None),
    ("2026년 3월 30일부터", "2026-03-30", ">="),
    ("2026-03-30", "2026-03-30", None),
    ("2026/03/30", "2026-03-30", None),
    ("2026년 3월", "2026-03", None),
    ("2026. 3.", "2026-03", None),
    ("2026. 3. 1. 이후", "2026-03-01", ">="),
    ("2026. 3. 30. 이전", "2026-03-30", "<"),
    ("2026. 3. 30.(월) 18:00 전까지", "2026-03-30", "<"),
    ("2026년 3월 30일(월)까지", "2026-03-30", "<="),
])
def test_date(text, value, cmp):
    q = one(text)
    assert (q.kind, q.value, q.comparator) == ("date", value, cmp)


def test_date_invalid_month():
    assert find_quantities("2026. 13. 1.") == []


def test_date_range():
    a, b = find_quantities("2026년 3월 1일부터 2026년 3월 31일까지")
    assert (a.value, a.comparator, b.value, b.comparator) == ("2026-03-01", ">=", "2026-03-31", "<=")
    assert a.range_id == b.range_id is not None


def test_date_range_tilde():
    a, b = find_quantities("2026. 3. 1. ~ 2026. 3. 30.")
    assert (a.value, a.comparator, b.value, b.comparator) == ("2026-03-01", ">=", "2026-03-30", "<=")
    assert a.range_id == b.range_id is not None


# 비교어

@pytest.mark.parametrize("text, cmp", [
    ("7천만원을 초과하지 않는", "<="),
    ("7천만원을 초과하지 아니하는", "<="),
    ("120%를 넘지 않는", "<="),
    ("7천만원을 초과하는", ">"),
    ("7천만원 초과", ">"),
    ("300만원 미만", "<"),
    ("300만원 이하", "<="),
    ("300만원 이상", ">="),
    ("2명까지", "<="),
    ("6개월 이내", "<="),
    ("19세부터", ">="),
    ("300만원", None),
    ("300만원(맞벌이 이하)", None),
])
def test_comparator(text, cmp):
    assert find_quantities(text)[0].comparator == cmp


# 수가 아닌 것

@pytest.mark.parametrize("text", [
    "제41조", "「주택공급에 관한 규칙」 제41조 제2항", "1.", "2)", "가.", "02-123-4567", "문의 1588-1234",
    "010-1234-5678", "2026년 기준", "2026년도", "제2회 공고", "총 3", "30일 이내",
])
def test_not_quantities(text):
    assert find_quantities(text) == []


def test_list_numbering_ignored_but_quantity_kept():
    assert [(q.kind, q.value) for q in find_quantities("1. 만 19세 이상")] == [("age", 19)]
    assert [(q.kind, q.value) for q in find_quantities("2) 무주택 세대원 2명")] == [("count", 2)]


def test_year_alone_inside_sentence():
    q = one("2026년도 기준중위소득 150% 이하")
    assert (q.kind, q.value) == ("percent", 150)


def test_quantities_sorted():
    qs = find_quantities("보증금 1억원 이하 및 월세 70만원 이하, 2026. 3. 30.까지")
    assert [q.kind for q in qs] == ["money", "money", "date"]
    assert [q.start for q in qs] == sorted(q.start for q in qs)


# 절

LINE = "만 19세 이상 34세 이하, 연소득 5천만 원 이하(맞벌이 7천만 원 이하)"


def test_clause_example():
    qs = find_quantities(LINE)
    by_val = {q.value: q for q in qs}
    c5, c7 = clause_at(LINE, by_val[5000].start), clause_at(LINE, by_val[7000].start)
    assert c5 == "연소득 5천만 원 이하"
    assert c7 == "맞벌이 7천만 원 이하"
    assert c5 != c7
    assert clause_at(LINE, by_val[19].start) == clause_at(LINE, by_val[34].start) == "만 19세 이상 34세 이하"


def test_clause_spans_example():
    assert [LINE[s:e] for s, e in clause_spans(LINE)] == ["만 19세 이상 34세 이하", "연소득 5천만 원 이하", "맞벌이 7천만 원 이하"]


def test_each_quantity_in_exactly_one_clause():
    text = "연소득 7,500만원 이하 또는 6,458,330원/월; 신청일(2026/03/30) 현재 [자산 3억 4,500만 원 이하]"
    spans = clause_spans(text)
    for q in find_quantities(text):
        assert sum(s <= q.start and q.end <= e for s, e in spans) == 1, q


@pytest.mark.parametrize("text, parts", [
    ("보증금 1억원 이하 및 월세 70만원 이하", ["보증금 1억원 이하", "월세 70만원 이하"]),
    ("무주택자 또는 1주택자", ["무주택자", "1주택자"]),
    ("소득·자산 기준", ["소득", "자산 기준"]),
    ("소득ㆍ자산", ["소득", "자산"]),
    ("○ 무주택 ○ 소득 100% 이하 - 자산 3억원 이하", ["무주택", "소득 100% 이하", "자산 3억원 이하"]),
    ("※ 맞벌이 ① 7천만원 ② 5천만원", ["맞벌이", "7천만원", "5천만원"]),
    ("A; B [C]", ["A", "B", "C"]),
    ("총 1,000 세대", ["총 1,000 세대"]),
])
def test_clause_split(text, parts):
    assert [text[s:e] for s, e in clause_spans(text)] == parts


def test_clause_at_separator_is_empty():
    assert clause_at("가, 나", 1) == ""


# 단위 바꾸기

def test_convert():
    years = Quantity("years", 2.0, 0, 2, ">=", "2년")
    months18 = Quantity("months", 18.0, 0, 4, None, "18개월")
    months24 = Quantity("months", 24.0, 0, 4, None, "24개월")
    age = Quantity("age", 19.0, 0, 3, ">=", "19세")
    money = Quantity("money", 5000.0, 0, 4, "<=", "5천만원")
    date_ = Quantity("date", "2026-03-30", 0, 10, "<=", "2026-03-30")
    assert convert(years, "years") == 2
    assert convert(years, "months") == 24
    assert convert(months24, "years") == 2
    assert convert(months18, "years") is None
    assert convert(months18, "months") == 18
    assert convert(age, "age") == 19
    assert convert(money, "money") == 5000
    assert convert(money, "percent") is None
    assert convert(age, "months") is None
    assert convert(date_, "date") == "2026-03-30"


def test_convert_from_text():
    assert convert(one("1년 6개월 이상"), "months") == 18
    assert convert(one("2년 이상"), "months") == 24


# 검토 지적 재현

def test_inverted_bounds_not_linked():
    qs = find_quantities("만 19세 이상, 만 6세 이하 자녀가 있는 가구")
    assert [q.range_id for q in qs] == [None, None]
    qs = find_quantities("34~19세")
    assert all(q.range_id is None for q in qs)


def test_weekday_and_time_before_tilde():
    qs = find_quantities("접수기간: 2026. 3. 1.(일) 10:00 ~ 2026. 3. 30.(월) 18:00까지")
    assert [(q.value, q.comparator) for q in qs] == [("2026-03-01", ">="), ("2026-03-30", "<=")]
    assert qs[0].range_id == qs[1].range_id is not None


def test_comparator_after_parenthetical():
    qs = find_quantities("월평균소득 120%(맞벌이 130%) 이하")
    assert (qs[0].value, qs[0].comparator) == (120, "<=")
    assert find_quantities("자녀 2명(태아 포함) 이상")[0].comparator == ">="
    assert find_quantities("만 6세(2019.1.1. 이후 출생) 자녀")[0].comparator is None  # 괄호 안에 비교어가 있으면 건너뛰지 않는다


@pytest.mark.parametrize("text, op", [
    ("청약통장 가입 후 12개월이 지나고", ">="), ("가입 후 6개월이 지난 자", ">="), ("24개월 경과", ">="),
    ("가입 후 12개월이 지나지 않은 자", "<"),
])
def test_elapsed_words(text, op):
    assert one(text).comparator == op


@pytest.mark.parametrize("text, op", [
    ("본인 연소득이 5천만원을 초과하는 자는 신청할 수 없습니다", "<="),
    ("만 19세 미만인 자는 신청 대상에서 제외", ">="),
    ("소득 100% 초과자 제외", "<="),
])
def test_exclusion_inverts(text, op):
    q = find_quantities(text)[0]
    assert (q.comparator, q.inverted) == (op, True)


def test_conjunctive_endings_split_before_quantity():
    text = "혼인기간 5년 이내이고 무주택기간 5년 이상인 자"
    assert [text[s:e] for s, e in clause_spans(text)] == ["혼인기간 5년 이내이", "무주택기간 5년 이상인 자"]
    text = "연소득 5천만원 이하이고 무주택 세대주인 자"  # 뒤에 수가 없으면 나누지 않는다
    assert [text[s:e] for s, e in clause_spans(text)] == [text]
    assert len(clause_spans("전입신고 후 6개월 이상 거주")) == 1  # "신고"는 이어 주는 끝이 아니다


def test_clause_at_parentheses_transparent():
    text = "전년도 도시근로자 월평균소득(태아 포함)의 120% 이하"
    assert clause_at(text, find_quantities(text)[0].start) == "전년도 도시근로자 월평균소득 태아 포함 의 120% 이하"
    text = "연소득 5천만 원 이하(맞벌이 7천만 원 이하)인 무주택 세대주"
    by_val = {q.value: q for q in find_quantities(text)}
    assert clause_at(text, by_val[5000].start) == "연소득 5천만 원 이하 인 무주택 세대주"
    assert clause_at(text, by_val[7000].start) == "맞벌이 7천만 원 이하"
