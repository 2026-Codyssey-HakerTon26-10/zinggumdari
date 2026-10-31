"""출생 정보는 birth_date(생년월일)가 기준이다(팀 결정). 만 나이는 판정 기준일과 생년월일로 한 값을 계산한다.
birth_year만 있는 옛 데이터(가상 인구 등)는 예전처럼 두 값으로 읽는다."""

from datetime import date

import pytest

from backend.engine import judge
from backend.engine.cards import build_judge
from backend.engine.derive import derive
from backend.engine.stub_data import EXAMPLE_PROFILE
from backend.engine.values import Ask, Values, age_values, resolve

TODAY = date(2026, 11, 1)


def C(field, op, value, **kw):
    return {"field": field, "op": op, "value": value, "evidence": ["doc:l1"], "status": "reviewed", **kw}


def R(conds, rid="manual:t", **kw):
    return {"id": rid, "source": "manual", "subject": "self", "name": rid, "conditions": conds,
            "review": {"status": "reviewed"}, "updated": "2026-10-31", "detail_url": "https://x", **kw}


def P(**me):
    return {"self": me, "parents": [], "consents": {"sensitive": True, "parent": True}}


# 만 나이 ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("born,want", [
    ("1992-11-01", [34]),   # 생일 당일: 한 살 든다
    ("1992-11-02", [33]),   # 생일 하루 전
    ("1992-10-31", [34]),   # 생일 다음 날
    ("1992-01-01", [34]),
    ("1992-12-31", [33]),
])
def test_age_from_birth_date_is_one_value(born, want):
    assert age_values({"birth_date": born}, TODAY) == want


@pytest.mark.parametrize("today,want", [
    (date(2027, 2, 28), 26),   # 평년 2월 28일: 아직 생일 전
    (date(2027, 3, 1), 27),    # 평년엔 3월 1일에 한 살
    (date(2028, 2, 29), 28),   # 윤년은 그날
])
def test_feb_29_birthday(today, want):
    assert age_values({"birth_date": "2000-02-29"}, today) == [want]


def test_birth_year_only_keeps_two_values():
    assert age_values({"birth_year": 1992}, TODAY) == [33, 34]


def test_birth_date_wins_over_birth_year():
    assert age_values({"birth_date": "1992-11-02", "birth_year": 1990}, TODAY) == [33]


def test_missing_birth_asks_birth_date():
    assert resolve({}, C("age", "<=", 34), TODAY, TODAY.year) == Ask("birth_date")
    assert age_values({}, TODAY) is None


def test_bad_birth_date_is_check_not_crash():
    out = resolve({"birth_date": "1992-13-45"}, C("age", "<=", 34), TODAY, TODAY.year)
    assert not isinstance(out, (Values, Ask))   # 비교할 수 없어 확인 필요


# 판정 ------------------------------------------------------------------------------------------

def test_boundary_is_decided_with_birth_date():
    # 출생연도만 알면 만 34·35 둘 다라 확인 필요였던 경계가, 생년월일이면 확정된다
    rule = R([C("age", "<=", 34)])
    assert judge(P(birth_year=1991), [rule], TODAY)["manual:t"]["verdict"] == "needs_check"
    assert judge(P(birth_date="1991-11-02"), [rule], TODAY)["manual:t"]["verdict"] == "eligible"     # 만 34
    assert judge(P(birth_date="1991-11-01"), [rule], TODAY)["manual:t"]["verdict"] == "ineligible"   # 만 35


def test_blocking_field_is_birth_date():
    card = judge(P(marital_status="미혼"), [R([C("age", "<=", 34)])], TODAY)["manual:t"]
    assert card["blocking_fields"] == ["birth_date"]


def test_ask_question_is_birth_date():
    rules = [R([C("age", "<=", 30 + i)], rid=f"manual:a{i}") for i in range(6)]
    ask = build_judge(P(), rules, TODAY)["ask"]
    assert ask["field"] == "birth_date" and "생년월일" in ask["question"]
    assert ask["options"][0]["value"] == "date"


def test_derived_age_is_one_value():
    d = derive(P(birth_date="1992-11-02"), TODAY)
    assert d["age"] == [33] and "youth" in d["tags"]


# 날짜 계산(플래너) -------------------------------------------------------------------------------

def test_closes_at_is_exact_date_with_birth_date():
    rule = R([C("age", "<=", 34)])
    card = build_judge(P(birth_date="1999-04-15"), [rule], TODAY)["cards"][0]
    closes = card["closes_at"]
    assert closes["when"] == "2034-04-15" and closes["year"] == 2034 and closes["from"] == "birth_date"


def test_opens_at_is_exact_date_with_birth_date():
    rule = R([C("age", ">=", 65)], subject="parent")
    mom = {"relation": "모", "birth_date": "1966-07-03"}
    card = build_judge({**P(birth_date="1999-04-15"), "parents": [mom]}, [rule], TODAY)["cards"][0]
    assert card["opens_at"]["when"] == "2031-07-03" and card["opens_at"]["year"] == 2031


# 시연 프리셋 ------------------------------------------------------------------------------------

def test_preset_uses_birth_date():
    me, mom = EXAMPLE_PROFILE["self"], EXAMPLE_PROFILE["parents"][0]
    assert me["birth_date"] == "1999-04-15" and "birth_year" not in me
    assert mom["birth_date"] == "1966-07-03" and "birth_year" not in mom
