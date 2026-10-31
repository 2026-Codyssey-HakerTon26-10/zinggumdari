"""검증기(SPEC §9.3): 검사마다 통과·실패 사례."""

import copy

import pytest

from backend.compiler.verify import CHECKS, check_condition, verify

DOC = "demo"
L14 = "만 19세 이상 34세 이하, 연소득 5천만 원 이하(맞벌이 7천만 원 이하)인 무주택 세대주"


def line(lid: str, text: str, **kw) -> dict:
    return {"id": lid, "page": None, "bbox": None, "text": text, "mark": True, **kw}


def cond(field: str, op: str, value, ev=("l14",), **kw) -> dict:
    return {"field": field, "op": op, "value": value, "evidence": [f"{DOC}:{e}" for e in ev], **kw}


def rule(*conds, **kw) -> dict:
    return {"id": "upload:demo:x", "source": "upload", "conditions": list(conds), **kw}


def run(lines, *conds, **kw) -> list[dict]:
    return verify(rule(*conds, **kw), lines)["conditions"]


LINES = [line("l14", L14)]
FULL = [
    cond("age", ">=", 19),
    cond("age", "<=", 34),
    cond("income_self", "<=", 5000, income_basis="absolute_annual"),
    cond("income_couple", "<=", 7000, income_basis="absolute_annual"),
    cond("is_homeless", "==", "Y"),
    cond("is_householder", "==", "세대주"),
]


def ok_except(checks: dict, **expected) -> None:
    assert checks == {k: expected.get(k, "ok") for k in CHECKS}


# 전부 맞게 뽑은 줄

def test_full_extraction_all_auto_verified():
    out = run(LINES, *FULL)
    assert [c["status"] for c in out] == ["auto_verified"] * 6
    for c in out[:4]:
        ok_except(c["checks"])
    for c in out[4:]:  # 범주 조건은 값(근거에 그 말)과 비교어(제외 문장이 아님)를 본다
        ok_except(c["checks"], unit="na", pair="na")


def test_returns_copy():
    r = rule(*copy.deepcopy(FULL))
    before = copy.deepcopy(r)
    assert verify(r, LINES) is not r
    assert r == before


# 단위·같은 절: age <= 5000이 값·비교어만으로 통과하면 안 된다

def test_age_from_income_number_fails_unit_and_clause():
    (c,) = run(LINES, cond("age", "<=", 5000))
    assert c["status"] == "needs_review"
    ok_except(c["checks"], unit="fail:unit_mismatch", keyword="fail:keyword_not_in_clause")


def test_value_not_in_evidence():
    (c,) = run(LINES, cond("age", "<=", 39))
    assert c["checks"]["value"] == "fail:not_in_evidence"
    assert c["checks"]["unit"] == "fail:no_value"
    assert c["status"] == "needs_review"


def test_income_number_from_other_clause_fails_keyword():
    # 7천만 원은 "맞벌이" 절이라 본인 소득 신호어("소득")가 같은 절에 없다
    (c,) = run(LINES, cond("income_self", "<=", 7000, income_basis="absolute_annual"))
    assert c["checks"]["keyword"] == "fail:keyword_not_in_clause"


# 경계 쌍

def test_missing_upper_bound():
    (c,) = run(LINES, cond("age", ">=", 19))
    assert c["checks"]["pair"] == "fail:missing_bound:34"
    assert c["status"] == "needs_review"


def test_tilde_range_both_bounds():
    lines = [line("l1", "연령 19~34세")]
    out = run(lines, cond("age", ">=", 19, ev=("l1",)), cond("age", "<=", 34, ev=("l1",)))
    assert [c["status"] for c in out] == ["auto_verified"] * 2


def test_bound_with_other_field_does_not_count():
    out = run(LINES, cond("age", ">=", 19), cond("youngest_child_age", "<=", 34))
    assert out[0]["checks"]["pair"] == "fail:missing_bound:34"


# 비교어

def test_wrong_op():
    (c,) = run(LINES, cond("age", ">", 19), cond("age", "<=", 34))[:1]
    assert c["checks"]["comparator"] == "fail:op_mismatch"
    assert c["status"] == "needs_review"


def test_no_comparator():
    lines = [line("l1", "청약통장 가입기간 24개월(납입 인정)")]
    (c,) = run(lines, cond("subscription_months", ">=", 24, ev=("l1",)))
    assert c["checks"]["comparator"] == "fail:no_comparator"


def test_eq_accepts_no_comparator():
    lines = [line("l1", "자녀 2명")]
    (c,) = run(lines, cond("children_count", "==", 2, ev=("l1",)))
    assert c["status"] == "auto_verified"


def test_eq_rejects_inequality_word():
    lines = [line("l1", "자녀 2명 이상")]
    (c,) = run(lines, cond("children_count", "==", 2, ev=("l1",)))
    assert c["checks"]["comparator"] == "fail:op_mismatch"


# 단위 바꾸기·소득 기준

def test_years_to_months():
    lines = [line("l1", "청약통장 가입기간 2년 이상")]
    (c,) = run(lines, cond("subscription_months", ">=", 24, ev=("l1",)))
    assert c["status"] == "auto_verified"
    ok_except(c["checks"])


def test_period_value_in_wrong_unit():
    lines = [line("l1", "청약통장 가입기간 2년 이상")]
    (c,) = run(lines, cond("subscription_months", ">=", 2, ev=("l1",)))
    assert c["checks"]["value"] == "fail:not_in_evidence"


def test_percent_needs_percent_basis():
    lines = [line("l1", "가구 소득이 기준중위소득 150% 이하")]
    good, bad = run(lines,
                    cond("income_household", "<=", 150, ev=("l1",), income_basis="median_pct"),
                    cond("income_household", "<=", 150, ev=("l1",), income_basis="absolute_annual"))
    assert good["status"] == "auto_verified"
    assert bad["checks"]["unit"] == "fail:unit_mismatch"
    assert bad["status"] == "needs_review"


def test_money_needs_money_basis():
    (c,) = run(LINES, cond("income_self", "<=", 5000, income_basis="median_pct"))
    assert c["checks"]["unit"] == "fail:unit_mismatch"


def test_money_tolerance():
    lines = [line("l1", "월평균소득 6,458,330원 이하")]
    (c,) = run(lines, cond("income_household", "<=", 645.83, ev=("l1",), income_basis="absolute_monthly"))
    assert c["status"] == "auto_verified"


def test_date_condition():
    lines = [line("l1", "신청기간: 2026. 3. 30.까지 접수")]
    (c,) = run(lines, cond("apply_date", "<=", "2026-03-30", ev=("l1",)))
    assert c["status"] == "auto_verified"


# 글자 층

def test_ocr_evidence_fails_layer():
    lines = [line("p2-l5", L14, page=2, src="ocr")]
    out = run(lines, *[{**c, "evidence": [f"{DOC}:p2-l5"]} for c in FULL])
    assert all(c["checks"]["layer"] == "fail:ocr" for c in out)
    assert all(c["status"] == "needs_review" for c in out)


# 근거

@pytest.mark.parametrize("evidence, reason", [
    (["demo:l99"], "fail:unknown_line:demo:l99"),
    (["demo:l14", "demo:l99"], "fail:unknown_line:demo:l99"),
    (["l14"], "fail:bad_id:l14"),
    ([], "fail:no_evidence"),
])
def test_bad_evidence(evidence, reason):
    (c,) = run(LINES, {**cond("is_homeless", "==", "Y"), "evidence": evidence})
    assert c["checks"]["evidence"] == reason
    assert c["status"] == "needs_review"


def test_evidence_with_colon_in_line_lookup_keys():
    c = cond("is_homeless", "==", "Y")
    checks = check_condition(c, rule(c), {"demo:l14": LINES[0]})
    assert checks["evidence"] == "ok" and checks["keyword"] == "ok"


def test_keyword_missing_non_numeric():
    lines = [line("l1", "신청일 현재 세대주")]
    (c,) = run(lines, cond("is_homeless", "==", "Y", ev=("l1",)))
    assert c["checks"]["keyword"] == "fail:keyword_not_in_evidence"


# 스키마

@pytest.mark.parametrize("c, reason", [
    (cond("foo", "==", 1), "fail:unknown_field:foo"),
    (cond("age", "~", 19), "fail:unknown_op:~"),
    (cond("age", ">=", 19, as_of="yesterday"), "fail:unknown_as_of:yesterday"),
    (cond("income_self", "<=", 5000), "fail:missing_income_basis"),
    (cond("income_self", "<=", 5000, income_basis="yearly"), "fail:unknown_income_basis:yearly"),
    (cond("marital_status", "in", "신혼"), "fail:value_not_list"),
    (cond("age", "<=", "34"), "fail:value_not_number"),
    (cond("is_homeless", "==", None), "fail:value_not_scalar"),
    ({"field": "other", "text": " ", "evidence": ["demo:l14"]}, "fail:other_without_text"),
])
def test_schema_fail(c, reason):
    (out,) = run(LINES, c)
    assert out["checks"]["schema"] == reason
    assert out["status"] == "needs_review"


def test_unknown_field_only_schema_fails():
    (c,) = run(LINES, cond("foo", "<=", 34))
    ok_except(c["checks"], schema="fail:unknown_field:foo", value="na", comparator="na", unit="na",
              keyword="na", pair="na")


def test_other_is_always_needs_review():
    (c,) = run(LINES, {"field": "other", "text": "순자산 기준 이하", "evidence": ["demo:l14"]})
    assert c["status"] == "needs_review"
    assert c["checks"] == {**{k: "na" for k in CHECKS}, "schema": "ok", "evidence": "ok"}


# reviewed(손 조건표)

def test_reviewed_untouched_and_logged():
    bad = {**cond("age", "<=", 5000), "status": "reviewed", "quote": "…"}
    good = {**cond("is_homeless", "==", "Y"), "status": "reviewed"}
    r = rule(bad, good, id="manual:x", source="manual")
    log: list = []
    out = verify(r, LINES, log=log)
    assert out["conditions"] == [bad, good]
    assert [(e["rule_id"], e["index"]) for e in log] == [("manual:x", 0)]
    assert log[0]["checks"]["unit"] == "fail:unit_mismatch"


def test_failing_ai_condition_logged():
    log: list = []
    verify(rule(*FULL, cond("age", "<=", 5000)), LINES, log=log)
    assert [e["index"] for e in log] == [6]


# any_of

ANY_LINES = [line("l18", "부부합산 연소득 7,500만 원 이하"),
             line("l19", "또는 기혼자로 본인 소득 5천만 원 이하")]


def any_of(*branches) -> dict:
    return {"any_of": [list(b) for b in branches], "evidence": ["demo:l18", "demo:l19"]}


def test_any_of_passes():
    g = any_of([{"field": "income_couple", "op": "<=", "value": 7500, "income_basis": "absolute_annual"}],
               [{"field": "marital_status", "op": "in", "value": ["신혼", "기혼"]},
                {"field": "income_self", "op": "<=", "value": 5000, "income_basis": "absolute_annual"}])
    (c,) = run(ANY_LINES, g)
    assert c["status"] == "auto_verified"
    ok_except(c["checks"])


def test_any_of_merges_branch_fail():
    g = any_of([{"field": "income_couple", "op": "<=", "value": 7500, "income_basis": "absolute_annual"}],
               [{"field": "marital_status", "op": "in", "value": ["신혼", "기혼"]},
                {"field": "income_self", "op": "<", "value": 5000, "income_basis": "absolute_annual"}])
    (c,) = run(ANY_LINES, g)
    assert c["checks"]["comparator"] == "fail:b1.1:op_mismatch"
    assert c["checks"]["value"] == "ok"
    assert c["status"] == "needs_review"
    assert "checks" not in c["any_of"][1][1]


def test_any_of_all_non_numeric_is_na():
    g = any_of([{"field": "marital_status", "op": "in", "value": ["기혼"]}])
    (c,) = run(ANY_LINES, g)
    assert c["checks"]["unit"] == c["checks"]["pair"] == "na" and c["checks"]["value"] == "ok"
    assert c["status"] == "auto_verified"


@pytest.mark.parametrize("branches, reason", [
    ([], "fail:empty_any_of"),
    ([[]], "fail:empty_branch"),
    ([[{"any_of": [[{"field": "age", "op": ">=", "value": 19}]]}]], "fail:nested_any_of"),
])
def test_any_of_shape(branches, reason):
    (c,) = run(ANY_LINES, {"any_of": branches, "evidence": ["demo:l18"]})
    assert c["checks"]["schema"] == reason and c["status"] == "needs_review"


def test_any_of_with_other_needs_review():
    g = any_of([{"field": "other", "text": "기혼자"}])
    (c,) = run(ANY_LINES, g)
    assert c["status"] == "needs_review"


# 서류명

def test_documents_filtered():
    lines = [line("l30", "제출서류: 주민등록 등본, 혼인관계증명서")]
    docs = ["주민등록등본", "혼인관계 증명서", "가족관계증명서"]
    out = verify(rule(documents=docs), lines)
    assert out["documents"] == ["주민등록등본", "혼인관계 증명서"]
    assert out["documents_dropped"] == ["가족관계증명서"]


def test_documents_manual_kept():
    out = verify(rule(documents=["가족관계증명서"], source="manual"), [line("l1", "무관한 줄")])
    assert out["documents"] == ["가족관계증명서"] and "documents_dropped" not in out


# --- 검토 지적 재현(틀린 조건이 auto_verified가 되면 안 된다, 맞는 조건은 통과) ---

def status(text: str, c: dict) -> dict:
    (out,) = run([line("l1", text)], {**c, "evidence": [f"{DOC}:l1"]})
    return out


@pytest.mark.parametrize("text, c", [
    # 범주 값이 근거와 다르다
    ("공고일 현재 무주택세대구성원", cond("is_homeless", "==", "N")),
    ("무주택 세대주", cond("is_householder", "==", "세대원")),
    ("공고일 현재 서울특별시에 거주하는 자", cond("sido", "==", "부산광역시")),
    ("혼인기간 7년 이내인 신혼부부", cond("marital_status", "in", ["미혼"])),
    ("○ 만 19세 이상 39세 이하 미혼 청년", cond("marital_status", "in", ["기혼"])),
    ("주택 소유 여부는 공고일 현재를 기준으로 판단", cond("gender", "==", "여")),
    # 어휘 밖 값(api.md §1): true는 "Y"가 아니고, 세대주 칸은 세대주|세대원, 신혼부부는 신혼
    ("○ 무주택 세대주", cond("is_homeless", "==", True)),
    ("○ 무주택 세대주", cond("is_householder", "==", "Y")),
    ("○ 혼인기간 7년 이내인 신혼부부", cond("marital_status", "in", ["신혼부부"])),
    # 제외 문장의 범주 값을 == 로
    ("주거급여 수급자는 제외", cond("livelihood_status", "in", ["주거"])),
])
def test_categorical_value_must_match_evidence(text, c):
    assert status(text, c)["status"] == "needs_review"


@pytest.mark.parametrize("text, c", [
    ("공고일 현재 서울특별시에 거주하는 자", cond("sido", "==", "서울")),
    ("공고일 현재 서울시에 거주하는 자", cond("sido", "==", "서울특별시")),
    ("세대구성원 전원이 주택을 소유하고 있지 아니할 것", cond("is_homeless", "==", "Y")),
    ("주거급여 수급자는 제외", cond("livelihood_status", "not_in", ["주거"])),
    ("기초생활수급자", cond("livelihood_status", "in", ["생계", "의료", "주거", "교육"])),
])
def test_categorical_value_found(text, c):
    assert status(text, c)["status"] == "auto_verified", status(text, c)["checks"]


@pytest.mark.parametrize("text, c", [
    # 비교어가 괄호 뒤에 있으면 == 가 아니다
    ("연소득 5천만원(맞벌이 부부 7천만원) 이하", cond("income_self", "==", 5000, income_basis="absolute_annual")),
    ("자녀 2명(태아 포함) 이상인 무주택 세대주", cond("children_count", "==", 2)),
    ("월평균소득 120%(맞벌이 130%) 이하", cond("income_household", "==", 120, income_basis="urban_worker_pct")),
    ("연소득 5천만원, 맞벌이 7천만원 이하", cond("income_self", "==", 5000, income_basis="absolute_annual")),
])
def test_eq_needs_no_comparator_later(text, c):
    assert status(text, c)["checks"]["comparator"] == "fail:op_mismatch"


def test_exclusion_sentence_inverts_comparator():
    text = "본인 연소득이 5천만원을 초과하는 자는 신청할 수 없습니다"
    assert status(text, cond("income_self", ">", 5000, income_basis="absolute_annual"))["status"] == "needs_review"
    assert status(text, cond("income_self", "<=", 5000, income_basis="absolute_annual"))["status"] == "auto_verified"
    text = "만 19세 미만인 자는 신청 대상에서 제외"
    assert status(text, cond("age", "<", 19))["checks"]["comparator"] == "fail:op_mismatch"
    assert status(text, cond("age", ">=", 19))["status"] == "auto_verified"


def test_exclusion_elsewhere_in_clause_fails():
    c = status("연소득 5천만원 이하인 자 중 주거급여 수급자는 제외", cond("income_self", "<=", 5000, income_basis="absolute_annual"))
    assert c["checks"]["comparator"] == "fail:negated_context"
    # 괄호 안의 제외는 그 수와 다른 절이다
    assert status("만 19세 이상(대학생 제외)", cond("age", ">=", 19))["status"] == "auto_verified"


@pytest.mark.parametrize("text, field, value, basis", [
    ("해당 세대의 월평균소득 500만원 이하", "income_household", 500, "absolute_annual"),
    ("본인 연소득 5천만원 이하", "income_self", 5000, "absolute_monthly"),
    ("전년도 도시근로자 가구원수별 가구당 월평균소득의 120% 이하", "income_household", 120, "median_pct"),
    ("○ 가구 소득이 기준 중위소득 150% 이하인 자", "income_household", 150, "urban_worker_pct"),
    ("○ 가구 월평균소득 300만 원 이하", "income_household", 300, "absolute_annual"),
])
def test_income_basis_must_match_text(text, field, value, basis):
    c = status(text, cond(field, "<=", value, income_basis=basis))
    assert c["checks"]["unit"] == "fail:basis_mismatch" and c["status"] == "needs_review"


@pytest.mark.parametrize("text, c", [
    ("만 6세 이하(2019.1.1. 이후 출생) 자녀가 있는 무주택 세대주", cond("age", "<=", 6)),
    ("만 65세 이상의 직계존속을 3년 이상 계속하여 부양하고 있는 무주택 세대주", cond("age", ">=", 65)),
    ("무주택세대구성원이 3명 이상인 세대", cond("children_count", ">=", 3)),
    ("무주택세대구성원 전원의 보유 총자산가액 합계 3억 4,500만원 이하",
     cond("income_household", "<=", 34500, income_basis="absolute_annual")),
    ("전년도 도시근로자 가구원수별 가구당 월평균소득의 120% 이하", cond("income_self", "<=", 120, income_basis="urban_worker_pct")),
    ("○ 부부합산 연소득 7천 5백만 원 이하", cond("income_household", "<=", 7500, income_basis="absolute_annual")),
    ("○ 부부합산 연소득 7천 5백만 원 이하", cond("income_self", "<=", 7500, income_basis="absolute_annual")),
    ("본인 연소득 5천만원 이하", cond("income_couple", "<=", 5000, income_basis="absolute_annual")),
])
def test_keyword_tells_fields_apart(text, c):
    assert status(text, c)["checks"]["keyword"].startswith("fail:")


@pytest.mark.parametrize("text, c", [
    ("만 6세 이하(2019.1.1. 이후 출생) 자녀가 있는 무주택 세대주", cond("youngest_child_age", "<=", 6)),
    ("○ 부부합산 연소득 7천 5백만 원 이하", cond("income_couple", "<=", 7500, income_basis="absolute_annual")),
    ("본인 또는 배우자 연소득 5,000만 원 이하", cond("income_spouse", "<=", 5000, income_basis="absolute_annual")),
    ("본인 또는 배우자 연소득 5,000만 원 이하", cond("income_self", "<=", 5000, income_basis="absolute_annual")),
    ("전년도 도시근로자 가구원수별 가구당 월평균소득의 120% 이하",
     cond("income_household", "<=", 120, income_basis="urban_worker_pct")),
])
def test_keyword_right_field_passes(text, c):
    assert status(text, c)["status"] == "auto_verified", status(text, c)["checks"]


@pytest.mark.parametrize("text, c", [
    ("혼인기간 5년 이내이고 무주택기간 5년 이상인 자", cond("marriage_years", ">=", 5)),
    ("혼인기간 5년 이내이고 무주택기간 5년 이상인 자", cond("homeless_years", "<=", 5)),
    ("해당 지역에 6개월 이상 거주하고 청약통장 가입 후 24개월 이상 경과한 자", cond("residence_months", ">=", 24)),
])
def test_conjunctive_clauses_do_not_borrow(text, c):
    assert status(text, c)["status"] == "needs_review"


def test_lease_period_is_not_apply_window():
    lines = [line("l1", "임대차 계약기간: 2026. 5. 1.부터 2028. 4. 30.까지")]
    out = run(lines, cond("apply_date", ">=", "2026-05-01", ev=("l1",)), cond("apply_date", "<=", "2028-04-30", ev=("l1",)))
    assert all(c["status"] == "needs_review" for c in out)


@pytest.mark.parametrize("text, c", [
    ("전년도 도시근로자 월평균소득(태아 포함)의 120% 이하", cond("income_household", "<=", 120, income_basis="urban_worker_pct")),
    ("월평균소득 120%(맞벌이 130%) 이하", cond("income_household", "<=", 120, income_basis="urban_worker_pct")),
    ("연소득(부부합산) 7천만원 이하", cond("income_couple", "<=", 7000, income_basis="absolute_annual")),
    ("연소득 5천만원(세전) 이하", cond("income_self", "<=", 5000, income_basis="absolute_annual")),
    ("자녀 2명(태아 포함) 이상", cond("children_count", ">=", 2)),
    ("○ 청약통장 가입 후 12개월이 지나고 납입 횟수 12회 이상", cond("subscription_months", ">=", 12)),
])
def test_parenthetical_and_elapsed_phrasing_pass(text, c):
    assert status(text, c)["status"] == "auto_verified", status(text, c)["checks"]


@pytest.mark.parametrize("text, start, end", [
    ("접수기간: 2026. 3. 1.(일) ~ 2026. 3. 30.(월) 18:00까지", "2026-03-01", "2026-03-30"),
    ("3. 신청기간: 2026. 12. 1.(화) ~ 2026. 12. 31.(목)", "2026-12-01", "2026-12-31"),
])
def test_weekday_date_range(text, start, end):
    lines = [line("l1", text)]
    out = run(lines, cond("apply_date", ">=", start, ev=("l1",)), cond("apply_date", "<=", end, ev=("l1",)))
    assert [c["status"] for c in out] == ["auto_verified"] * 2, [c["checks"] for c in out]


def test_inverted_bounds_are_not_a_pair():
    lines = [line("l1", "만 19세 이상, 만 6세 이하 자녀가 있는 가구")]
    out = run(lines, cond("age", ">=", 19, ev=("l1",)), cond("youngest_child_age", "<=", 6, ev=("l1",)))
    assert [c["checks"]["pair"] for c in out] == ["ok", "ok"]


# 신호어를 바로 위 제목에만 쓴 목록 줄, 시도 값

HEADED = [line("l1", "3. 신청기간"), line("l2", "○ 2026. 11. 3.(화) ~ 2026. 11. 27.(금) 18:00까지")]


def test_keyword_from_heading_above():
    out = run(HEADED, cond("apply_date", ">=", "2026-11-03", ev=("l2",)), cond("apply_date", "<=", "2026-11-27", ev=("l2",)))
    for c in out:
        assert c["checks"]["keyword"] == "ok"


def test_heading_without_keyword_still_fails():
    lines = [line("l1", "5. 계약 일정"), HEADED[1]]
    out = run(lines, cond("apply_date", ">=", "2026-11-03", ev=("l2",)), cond("apply_date", "<=", "2026-11-27", ev=("l2",)))
    assert out[0]["checks"]["keyword"] == "fail:keyword_not_in_clause"


def test_sido_value_must_be_a_sido():
    out = run([line("l1", "공고일 현재 ○○시에 거주하는 무주택자")], cond("sido", "==", "○○시", ev=("l1",)))
    assert out[0]["checks"]["schema"] == "fail:value_not_in_vocab:○○시"
    assert out[0]["status"] == "needs_review"


@pytest.mark.parametrize("field", ["qual_code", "history"])
def test_code_fields_never_auto_verified(field):
    out = run([line("l1", "신청자는 만 19세 이상이어야 합니다.")], cond(field, "in", ["가공의자격"], ev=("l1",)))
    assert out[0]["checks"]["value"] == "fail:unverifiable"
    assert out[0]["status"] == "needs_review"
