"""플래너(backend/planner): 단계 넘기기, 해둘 일, 날짜, 부모님 줄, 단계 태그. 조건표는 테스트용으로 손으로 만든 것이다."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.app import sources
from backend.app.main import app
from backend.app.routers import profiles
from backend.engine.cards import build_judge
from backend.planner import apply_step, stage_tags

TODAY = date(2026, 11, 1)


def C(field, op, value, ev="doc:l1", **kw):
    return {"field": field, "op": op, "value": value, "evidence": [ev], "status": "reviewed", **kw}


def R(rid, conds, **kw):
    return {"id": rid, "source": "manual", "subject": "self", "name": rid.split(":")[1], "conditions": conds,
            "review": {"status": "reviewed"}, "updated": "2026-10-31", "detail_url": "https://x", **kw}


YOUTH = R("manual:youth", [C("age", "<=", 34, ev="y:l1"), C("marital_status", "in", ["미혼", "예비부부"], ev="y:l2")])
NEWLYWED = R("manual:newlywed", [C("marital_status", "in", ["신혼", "기혼"], ev="n:l1"),
                                 C("marriage_years", "<=", 7, ev="n:l2", as_of="application_date"),
                                 C("subscription_months", ">=", 6, ev="n:l3")])
NEWBORN = R("manual:newborn", [C("children_count", ">=", 1, ev="b:l1"), C("youngest_child_age", "<=", 2, ev="b:l2")])
MULTI = R("manual:multi", [C("children_count", ">=", 2, ev="m:l1")])
LATER = R("manual:later", [C("apply_date", ">=", "2027-01-01", ev="l:l1")])
CLOSING = R("manual:closing", [C("apply_date", "<=", "2026-12-31", ev="c:l1")])
LTC = R("manual:ltc", [C("ltc_grade", "in", ["1등급", "2등급", "3등급", "4등급", "5등급"], ev="ltc:l1")], subject="parent")
PENSION = R("manual:pension", [C("age", ">=", 65, ev="bp:l1")], subject="parent",
            apply_window={"anchor": "age65", "offset_months": -1, "evidence": ["bp:l9"]})

RULES = [YOUTH, NEWLYWED, NEWBORN, MULTI]

JIWON = {"user_id": "U1", "consents": {"sensitive": True, "parent": True},
         "self": {"birth_year": 1999, "marital_status": "예비부부", "children_count": 0,
                  "has_account": "Y", "joined_date": "2021-03-01"},
         "parents": []}
MOM = {"relation": "모", "birth_year": 1966, "ltc_grade": "없음", "care_wanted": "Y"}


def card(body, rid):
    return next(c for c in body["cards"] if c["rule_id"] == rid)


# 단계 넘기기 ------------------------------------------------------------------------------------

def test_apply_step():
    me = apply_step(JIWON, "newlywed", TODAY)["self"]
    assert (me["marital_status"], me["marriage_date"]) == ("신혼", "2026-11-01")
    me = apply_step(JIWON, "child", TODAY)["self"]   # 앞 단계(신혼)까지 같이 적용
    assert (me["marital_status"], me["children_count"], me["youngest_child_age"]) == ("신혼", 1, 0)
    assert apply_step(JIWON, "multi_child", TODAY)["self"]["children_count"] == 2
    assert JIWON["self"]["marital_status"] == "예비부부"   # 원본은 그대로


def test_timeline_opens_and_closes():
    steps = build_judge(JIWON, RULES, TODAY)["timeline"]["self"]
    assert [s["step"] for s in steps] == ["newlywed", "child", "multi_child"]
    assert steps[0]["opens"] == ["manual:newlywed"] and steps[0]["closes"] == ["manual:youth"]
    assert steps[1]["opens"] == ["manual:newborn"]
    assert steps[2]["opens"] == ["manual:multi"]
    assert steps[0]["assume"] == {"marital_status": "신혼", "marriage_date": "2026-11-01"}


def test_timeline_skips_reached_steps():
    married = {**JIWON, "self": {**JIWON["self"], "marital_status": "신혼", "marriage_date": "2026-01-01", "children_count": 1}}
    assert [s["step"] for s in build_judge(married, RULES, TODAY)["timeline"]["self"]] == ["multi_child"]


def test_todo_from_conditions():
    todo = build_judge(JIWON, RULES, TODAY)["timeline"]["self"][0]["todo"]
    sub = next(t for t in todo if t["action"] == "subscription_account")
    assert (sub["min_months"], sub["have_months"], sub["status"]) == (6, 68, "met")
    assert sub["evidence"] == ["n:l3"]
    assert {t["action"] for t in todo} == {"subscription_account", "marriage_registration"}
    assert all(t["evidence"] for t in todo)


def test_step_param_rejudges():
    body = build_judge(JIWON, RULES, TODAY, step="newlywed")
    assert card(body, "manual:newlywed")["verdict"] == "eligible"
    assert "manual:youth" not in [c["rule_id"] for c in body["cards"]]
    assert [s["step"] for s in body["timeline"]["self"]] == ["child", "multi_child"]


# 카드의 날짜 ------------------------------------------------------------------------------------

def test_card_opens_at_step():
    assert card(build_judge(JIWON, [YOUTH, NEWLYWED, LATER], TODAY), "manual:youth")["opens_at"] is None
    # 다음 단계에서 열리는 제도는 카드로 올리고 언제 열리는지 단다(요청 34)
    c = card(build_judge(JIWON, [NEWLYWED], TODAY), "manual:newlywed")
    assert (c["verdict"], c["verdict_why"], c["opens_at"]) == ("opens_later", "next_step", {"step": "newlywed"})


def test_card_opens_at_date():
    c = card(build_judge(JIWON, [LATER], TODAY), "manual:later")
    assert c["verdict"] == "opens_later"
    assert c["opens_at"] == {"field": "apply_date", "when": "2027-01-01"}


def test_closes_at_and_deadline():
    c = card(build_judge(JIWON, [CLOSING], TODAY), "manual:closing")
    assert c["closes_at"] == {"field": "apply_date", "when": "2026-12-31"}
    assert c["deadline"] == "2026-12-31"
    newly = card(build_judge(JIWON, [NEWLYWED], TODAY, step="newlywed"), "manual:newlywed")
    assert newly["closes_at"] == {"field": "marriage_years", "from": "marriage_date", "plus_years": 7, "when": "2033-11-01"}
    youth = card(build_judge(JIWON, [YOUTH], TODAY), "manual:youth")
    assert youth["closes_at"] == {"field": "age", "from": "birth_year", "max_age": 34, "year": 2034}


def test_no_dates_from_unverified_conditions():
    rule = R("manual:ai", [C("apply_date", "<=", "2026-12-31", status="needs_review")])
    c = card(build_judge(JIWON, [rule], TODAY), "manual:ai")
    assert c["closes_at"] is None and c["deadline"] is None


def test_prerequisites_on_card():
    c = card(build_judge(JIWON, [NEWLYWED], TODAY, step="newlywed"), "manual:newlywed")
    assert {t["action"] for t in c["prerequisites"]} == {"marriage_registration", "subscription_account"}


# 부모님 줄 --------------------------------------------------------------------------------------

def test_parent_line():
    body = build_judge({**JIWON, "parents": [MOM]}, RULES + [LTC, PENSION], TODAY)
    ltc, age65 = body["timeline"]["parent"]
    assert ltc["step"] == "ltc_apply" and ltc["now"] is True and ltc["opens"] == ["manual:ltc"]
    assert ltc["todo"] == [{"action": "ltc_grade_apply", "evidence": ["ltc:l1"]}]
    assert age65["step"] == "age65" and age65["year"] == 2031 and age65["opens"] == ["manual:pension"]
    assert age65["apply_from"].startswith("2031년 생일이 속한 달의 1개월 전부터")
    assert card(body, "manual:pension")["apply_from"] == age65["apply_from"]


def test_no_parent_line_without_parents():
    assert build_judge(JIWON, RULES + [LTC, PENSION], TODAY)["timeline"]["parent"] == []


def test_dated():
    dated = build_judge({**JIWON, "parents": [MOM]}, RULES + [PENSION], TODAY)["timeline"]["dated"]
    youth = {"what": "청년 나이 상한(만 34세) 지남", "year": 2034, "from": "birth_year", "note": "만 35세 생일부터 해당 안 됨"}
    assert youth in dated
    # 카드의 닫히는 해와 같은 해를 쓴다
    closes = card(build_judge(JIWON, [YOUTH], TODAY), "manual:youth")["closes_at"]["year"]
    assert closes == youth["year"]
    assert {"what": "어머니 만 65세", "year": 2031, "from": "parents.birth_year"} in dated


# 단계 태그 --------------------------------------------------------------------------------------

def test_stage_tags():
    assert stage_tags(YOUTH) == ["youth", "marriage_planned"]
    assert stage_tags(NEWLYWED) == ["newlywed"]
    assert stage_tags(NEWBORN) == ["child"]
    assert stage_tags(MULTI) == ["multi_child"]
    assert stage_tags(LTC) == ["parent"]


# 라우터 -----------------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DEV_STUB_API", "1")
    monkeypatch.setattr(sources, "load_rules", lambda: RULES)
    profiles._store["Uplan"] = JIWON
    return TestClient(app)


def test_router_step(client):
    body = client.post("/judge?today=2026-11-01", json={"user_id": "Uplan", "step": "newlywed"}).json()
    assert "manual:newlywed" in [c["rule_id"] for c in body["cards"]]


def test_router_bad_step(client):
    assert client.post("/judge", json={"user_id": "Uplan", "step": "retire"}).status_code == 422



# 리뷰 반영 -------------------------------------------------------------------------------------

def test_parent_age_from_condition():
    # 조건이 만 70세면 70세가 되는 해에 연다(요청 25). 65세 줄과 따로 묶는다
    care = R("manual:care70", [C("age", ">=", 70, ev="c70:l1")], subject="parent")
    steps = build_judge({**JIWON, "parents": [MOM]}, [PENSION, care], TODAY)["timeline"]["parent"]
    by_step = {s["step"]: s for s in steps}
    assert by_step["age65"]["year"] == 2031 and by_step["age65"]["opens"] == ["manual:pension"]
    assert by_step["age70"]["year"] == 2036 and by_step["age70"]["opens"] == ["manual:care70"]
    assert "apply_from" not in by_step["age70"] or by_step["age70"]["apply_from"] is None


@pytest.mark.parametrize("op,when", [("<=", "2027-01-01"), ("<", "2027-01-01")])
def test_period_closes_at_boundary(op, when):
    # 기간 경계는 혼인일 + 7년(요청 26). 엔진도 같은 날을 경계로 쓴다
    rule = R("manual:n", [C("marriage_years", op, 7)])
    me = {**JIWON, "self": {**JIWON["self"], "marital_status": "기혼", "marriage_date": "2020-01-01"}}
    assert card(build_judge(me, [rule], TODAY), "manual:n")["closes_at"]["when"] == when


def test_month_end_opens_at_matches_engine():
    rule = R("manual:sub", [C("subscription_months", ">=", 6)])
    me = {**JIWON, "self": {**JIWON["self"], "joined_date": "2026-08-31"}}
    c = card(build_judge(me, [rule], date(2026, 11, 1)), "manual:sub")
    assert c["opens_at"]["when"] == "2027-02-28"
    assert card(build_judge(me, [rule], date(2027, 2, 28)), "manual:sub")["verdict"] == "eligible"


def test_parent_card_uses_same_parent():
    # 판정과 날짜가 같은 부모 기준(요청 35)
    rule = R("manual:alone65", [C("age", ">=", 65), C("lives_alone", "==", "Y")], subject="parent")
    dad = {"relation": "부", "birth_year": 1963, "lives_alone": "Y"}
    mom = {**MOM, "lives_alone": "N"}
    body = build_judge({**JIWON, "parents": [mom, dad]}, [rule], TODAY)
    c = card(body, "manual:alone65")
    assert c["relation"] == "부" and c["opens_at"]["year"] == 2028
    opened = [(s["relation"], s["step"]) for s in body["timeline"]["parent"] if "manual:alone65" in s.get("opens", [])]
    assert opened == [("부", "age65")]


def test_todo_status_from_current_profile():
    # 해둘 일 상태는 지금 프로필로(요청 36): 예비부부라 혼인신고는 아직 안 함
    todo = build_judge(JIWON, RULES, TODAY)["timeline"]["self"][0]["todo"]
    assert {t["status"] for t in todo if t["action"] == "marriage_registration"} == {"unmet"}


def test_stage_tags_respect_op():
    # 요청 38
    assert stage_tags(R("manual:x", [C("marital_status", "not_in", ["신혼", "기혼"])])) == []
    assert stage_tags(R("manual:x", [C("marital_status", "!=", "예비부부")])) == []
    assert stage_tags(R("manual:x", [C("age", "<", 40)])) == ["youth"]
    assert stage_tags(R("manual:x", [C("children_count", ">", 1)])) == ["multi_child"]
    assert stage_tags(R("manual:x", [C("children_count", ">", 0)])) == ["child"]


def test_action_opens_at():
    # 장기요양등급이 없으면 신청하면 열린다(요청 33)
    body = build_judge({**JIWON, "parents": [MOM]}, [LTC], TODAY)
    assert card(body, "manual:ltc")["opens_at"] == {"action": "ltc_grade_apply"}


def test_any_of_age_is_not_a_required_age():
    # "65세 이상 또는 노인성 질병"의 65세는 필수가 아니므로 나이 줄에 올리지 않는다
    rule = R("manual:ltc2", [{"any_of": [[C("age", ">=", 65)], [C("other", "==", None, text="노인성 질병")]],
                              "evidence": ["l:l3"], "status": "reviewed"},
                             C("ltc_grade", "in", ["1등급", "2등급"])], subject="parent")
    steps = build_judge({**JIWON, "parents": [MOM]}, [rule], TODAY)["timeline"]["parent"]
    assert [s["step"] for s in steps if "manual:ltc2" in s["opens"]] == ["ltc_apply"]
