"""규칙 엔진(backend/engine). 조건표는 테스트용으로 손으로 만든 것이다(eval 정답지를 보지 않는다)."""

import time
from datetime import date

from backend.engine import judge

TODAY = date(2026, 11, 1)


def C(field, op, value, **kw):
    return {"field": field, "op": op, "value": value, "evidence": ["doc:l1"], "status": "reviewed", **kw}


def R(conds, rid="manual:t", **kw):
    return {"id": rid, "source": "manual", "subject": "self", "name": rid, "conditions": conds,
            "review": {"status": "reviewed"}, "updated": "2026-10-31", "detail_url": "https://x", **kw}


def P(consent=True, parents=None, **me):
    return {"self": me, "parents": parents or [], "consents": {"sensitive": consent, "parent": True}}


def one(profile, rule, **kw):
    return judge(profile, [rule], TODAY, **kw)[rule["id"]]


# 나이 -------------------------------------------------------------------------------------------

def test_age_pass():
    card = one(P(birth_year=1999), R([C("age", ">=", 19), C("age", "<=", 34)]))
    assert card["verdict"] == "eligible"


def test_age_boundary_needs_check():
    # 1991년생은 2026년에 만 34세 또는 35세 → 확정하지 않는다
    card = one(P(birth_year=1991), R([C("age", "<=", 34)]))
    assert card["verdict"] == "needs_check"
    assert card["conditions"][0]["why"] == "생일에 따라 달라요"


def test_age_64_opens_later():
    card = one(P(birth_year=1962), R([C("age", ">=", 65)]))  # 만 63 또는 64세
    assert card["verdict"] == "opens_later"


def test_age_over_limit_ineligible():
    assert one(P(birth_year=1980), R([C("age", "<=", 34)]))["verdict"] == "ineligible"


# 혼인 -------------------------------------------------------------------------------------------

def test_marriage_8_years_ineligible():
    card = one(P(marital_status="기혼", marriage_date="2018-06-01"), R([C("marriage_years", "<=", 7)]))
    assert card["verdict"] == "ineligible"


def test_marriage_years_before_registration_fails():
    card = one(P(marital_status="예비부부"), R([C("marriage_years", "<=", 7)]))
    assert card["verdict"] == "ineligible"


def test_newlywed_without_date_asks():
    card = one(P(marital_status="신혼"), R([C("marriage_years", "<=", 7)]))
    assert card["conditions"][0]["ask"] == "marriage_date"


# 소득 -------------------------------------------------------------------------------------------

COUPLE_7500 = C("income_couple", "<=", 7500, income_basis="absolute_annual")


def test_income_over_ineligible():
    card = one(P(marital_status="신혼", income_self=400, income_spouse=300), R([COUPLE_7500]))
    assert card["verdict"] == "ineligible"


def test_income_couple_asks_spouse():
    card = one(P(marital_status="예비부부", income_self=270), R([COUPLE_7500]))
    assert card["conditions"][0]["grade"] == "질문"
    assert card["conditions"][0]["ask"] == "income_spouse"


def test_income_couple_single_uses_self():
    assert one(P(marital_status="미혼", income_self=270), R([COUPLE_7500]))["verdict"] == "eligible"


def test_income_unknown_without_consent_needs_check():
    card = one(P(consent=False, marital_status="미혼"), R([COUPLE_7500]))
    assert card["conditions"][0]["grade"] == "확인 필요"


def test_income_unknown_keeps_other_conditions_confirmed():
    card = one(P(birth_year=1999, marital_status="미혼"), R([C("age", "<=", 34), COUPLE_7500]))
    assert card["verdict"] == "needs_check"
    assert [c["grade"] for c in card["conditions"]] == ["확정", "질문"]


def test_median_pct():
    rule = R([C("income_household", "<=", 100, income_basis="median_pct")])
    assert one(P(household_size=1, income_household=200), rule)["verdict"] == "eligible"     # 약 78%
    assert one(P(household_size=1, income_household=300), rule)["verdict"] == "ineligible"   # 약 117%
    assert one(P(household_size=7, income_household=300), rule)["verdict"] == "needs_check"


def test_urban_and_recognized_need_check():
    urban = R([C("income_household", "<=", 100, income_basis="urban_worker_pct")])
    recog = R([C("income_recognized", "<=", 247, income_basis="recognized")])
    assert one(P(household_size=1, income_household=200), urban)["verdict"] == "needs_check"
    assert one(P(household_size=1, income_household=200), recog)["verdict"] == "needs_check"


# any_of: 결혼 페널티 해소 -----------------------------------------------------------------------

ANY = {"any_of": [
    [C("income_couple", "<=", 7500, income_basis="absolute_annual")],
    [C("marital_status", "in", ["신혼", "기혼"]), C("income_self", "<=", 5000, income_basis="absolute_annual")],
], "evidence": ["doc:l2"], "status": "reviewed"}


def test_any_of_second_branch_passes():
    card = one(P(marital_status="신혼", income_self=300, income_spouse=400), R([ANY]))
    assert card["verdict"] == "eligible"


def test_any_of_all_branches_fail():
    card = one(P(marital_status="신혼", income_self=500, income_spouse=400), R([ANY]))
    assert card["verdict"] == "ineligible"


def test_any_of_one_branch_opens_later():
    # 가지 하나(만 65세 이상)는 시간이 지나면 열리고, 다른 가지(기초연금 수급)는 지금 탈락 → 나중에 열림
    cond = {"any_of": [[C("age", ">=", 65)], [C("basic_pension", "==", "Y")]], "evidence": ["doc:l3"], "status": "reviewed"}
    assert one(P(birth_year=1962, basic_pension="N"), R([cond]))["verdict"] == "opens_later"


# 접수 기간 --------------------------------------------------------------------------------------

def test_apply_closed_ineligible():
    assert one(P(), R([C("apply_date", "<=", "2026-03-31")]))["verdict"] == "ineligible"


def test_apply_not_started_opens_later():
    assert one(P(), R([C("apply_date", ">=", "2027-01-01")]))["verdict"] == "opens_later"


# 조건 상태와 AI 조건표 --------------------------------------------------------------------------

def test_other_and_needs_review_need_check():
    card = one(P(birth_year=1999), R([C("age", "<=", 34), C("other", "==", None, text="순자산 기준 이하"),
                                      C("age", ">=", 19, status="needs_review")]))
    assert card["verdict"] == "needs_check"
    assert [c["grade"] for c in card["conditions"]] == ["확정", "확인 필요", "확인 필요"]


def test_ai_rule_not_eligible_unless_enabled():
    rule = R([C("age", "<=", 34, status="auto_verified")], source="gov24", review={"status": "unreviewed"})
    card = one(P(birth_year=1999), rule, ai_eligible=False)
    assert (card["verdict"], card["verdict_why"], card["ai_extracted"]) == ("needs_check", "ai_unreviewed", True)
    card = one(P(birth_year=1999), rule, ai_eligible=True)
    assert (card["verdict"], card["verdict_why"]) == ("eligible", "ai_unreviewed")   # 열어 줘도 AI 조건표라는 사유는 남긴다


def test_same_as_superseded():
    ai = R([C("age", "<=", 34)], rid="gov24:WII1", source="gov24")
    manual = R([C("age", "<=", 34)], rid="manual:a", same_as=["gov24:WII1"])
    out = judge(P(birth_year=1999), [ai, manual], TODAY)
    assert out["gov24:WII1"]["superseded_by"] == "manual:a"
    assert "superseded_by" not in out["manual:a"]


# 대상자 -----------------------------------------------------------------------------------------

def test_parent_rule_uses_parent_profile():
    rule = R([C("age", ">=", 65)], subject="parent")
    mom = {"relation": "모", "birth_year": 1966}
    card = one(P(birth_year=1999, parents=[mom]), rule)
    assert card["verdict"] == "opens_later"


def test_parent_rule_without_parents():
    card = one(P(birth_year=1999), R([C("age", ">=", 65)], subject="parent"))
    assert card.get("no_subject") is True


# 전체 -------------------------------------------------------------------------------------------

def test_every_rule_in_result_and_deterministic():
    rules = [R([C("age", "<=", 34 + i % 5), COUPLE_7500, ANY], rid=f"manual:{i}") for i in range(500)]
    profile = P(birth_year=1992, marital_status="신혼", marriage_date="2025-05-01", income_self=300, income_spouse=350)
    t = time.perf_counter()
    a = judge(profile, rules, TODAY)
    assert time.perf_counter() - t < 1.0
    assert set(a) == {r["id"] for r in rules}
    assert a == judge(profile, rules, TODAY)


def test_read_as():
    card = one(P(), R([C("marriage_years", "<=", 7, as_of="application_date"), COUPLE_7500]))
    assert card["conditions"][0]["read_as"] == "혼인 기간 7년 이하(신청일 기준)"
    assert card["conditions"][1]["read_as"] == "부부합산 소득 연 7,500만 원 이하"


def test_blocking_fields():
    card = one(P(marital_status="예비부부"), R([C("age", "<=", 34), COUPLE_7500]))
    assert card["blocking_fields"] == ["birth_year", "income_self"]
