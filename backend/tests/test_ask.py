"""공고별 확인 질문(SPEC §6, api.md §3 ask). 조건표는 테스트용으로 손으로 만든 것이다."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.app import sources
from backend.app.main import app
from backend.app.routers import judge as judge_router
from backend.engine import judge
from backend.engine.cards import build_judge

TODAY = date(2026, 11, 1)


def C(field, op, value, **kw):
    return {"field": field, "op": op, "value": value, "evidence": ["doc:l1"], "status": "reviewed", **kw}


def R(rid, conds, **kw):
    return {"id": rid, "source": "manual", "subject": "self", "name": rid, "conditions": conds,
            "review": {"status": "reviewed"}, "updated": "2026-10-31", "detail_url": "https://x", **kw}


INCOME = C("income_self", "<=", 400)
MOVE = C("residence_months", ">=", 6)
ME = {"user_id": "U1", "consents": {"sensitive": True, "parent": False},
      "self": {"birth_year": 1999, "marital_status": "미혼"}, "parents": []}


def six():
    """후보 6개: 4개는 본인 소득, 2개는 전입일이 비어 있어 판정이 안 된다."""
    return [R(f"manual:i{i}", [INCOME]) for i in range(4)] + [R(f"manual:m{i}", [MOVE]) for i in range(2)]


def test_picks_field_splitting_most_candidates():
    ask = build_judge(ME, six(), TODAY)["ask"]
    assert ask["field"] == "income_self" and ask["subject"] == "self"
    assert ask["why"] == "후보 6개 중 4개가 이 칸으로 갈려요"
    assert ask["question"] and ask["options"]


def test_no_ask_when_five_or_fewer_candidates():
    assert build_judge(ME, six()[:5], TODAY)["ask"] is None


def test_no_ask_without_blocking_fields():
    rules = [R(f"manual:o{i}", [C("other", "==", None, text="순자산")]) for i in range(6)]
    assert build_judge(ME, rules, TODAY)["ask"] is None


def test_focus_card_asks_its_field_even_with_few_candidates():
    ask = build_judge(ME, six()[4:], TODAY, focus="manual:m0")["ask"]   # 후보 2개뿐이어도 카드를 열면 묻는다
    assert ask["field"] == "move_in_date" and ask["rule_id"] == "manual:m0"
    assert ask["why"] == "이 제도는 이 칸을 알아야 판정돼요"


def test_marriage_date_question_matches_api_example():
    rules = [R(f"manual:n{i}", [C("marriage_years", "<=", 7)]) for i in range(6)]
    me = {**ME, "self": {**ME["self"], "marital_status": "신혼"}}
    ask = build_judge(me, rules, TODAY)["ask"]
    assert ask["field"] == "marriage_date"
    assert ask["question"] == "혼인신고를 하셨나요? 했다면 언제인가요?"
    assert ask["options"] == [{"label": "안 함", "value": None, "set": {"marital_status": "예비부부"}},
                              {"label": "날짜 입력", "value": "date"}]


def test_sensitive_field_not_asked_without_consent():
    me = {**ME, "consents": {"sensitive": False, "parent": False}}
    assert build_judge(me, six(), TODAY)["ask"]["field"] == "move_in_date"


def test_parent_field_has_parent_subject():
    rules = [R(f"manual:p{i}", [C("care_wanted", "==", "Y")], subject="parent") for i in range(6)]
    me = {**ME, "parents": [{"relation": "모", "birth_year": 1966}]}
    ask = build_judge(me, rules, TODAY)["ask"]
    assert (ask["subject"], ask["field"]) == ("parent", "care_wanted")


def test_tie_break_is_deterministic():
    rules = [R(f"manual:a{i}", [INCOME]) for i in range(3)] + [R(f"manual:b{i}", [MOVE]) for i in range(3)]
    # 표가 같으면 폼 순서(engine/ask.py ORDER)가 앞인 칸. 전입일이 소득(민감정보)보다 먼저다
    assert {build_judge(ME, rules, TODAY)["ask"]["field"] for _ in range(5)} == {"move_in_date"}


# 자격 코드: 하나씩 예/아니오로 묻고, 아니오도 한 줄로 저장한다 -----------------------------------------

def test_qual_code_asked_one_code_at_a_time():
    rules = [R(f"manual:q{i}", [C("qual_code", "in", ["한부모", "차상위계층"])]) for i in range(6)]
    ask = build_judge({**ME, "self": {**ME["self"], "qualifications": []}}, rules, TODAY)["ask"]
    assert ask["field"] == "qual_code" and ask["qual_code"] == "한부모"
    assert ask["question"] == "‘한부모’에 해당하시나요?"
    assert [o["value"] for o in ask["options"]] == ["Y", "N"]
    assert ask["options"][1]["add_qualification"] == {"qual_code": "한부모", "target": "본인", "verified": "자기신고", "has": "N"}


def test_qual_code_answered_no_is_known():
    no = [{"qual_code": "한부모", "target": "본인", "verified": "자기신고", "has": "N"}]
    me = {**ME, "self": {**ME["self"], "qualifications": no}}
    rule_in = R("manual:in", [C("qual_code", "in", ["한부모"])])
    rule_not = R("manual:not", [C("qual_code", "not_in", ["한부모"])])
    out = judge(me, [rule_in, rule_not], TODAY)
    assert out["manual:in"]["verdict"] == "ineligible"
    assert out["manual:not"]["verdict"] == "eligible"


def test_sensitive_qual_code_not_asked_without_consent():
    rules = [R(f"manual:q{i}", [C("qual_code", "in", ["기초생활수급자"])]) for i in range(6)]
    me = {**ME, "consents": {"sensitive": False, "parent": False}}
    assert build_judge(me, rules, TODAY)["ask"] is None


# 라우터 -----------------------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(sources, "load_rules", lambda owner=None: six()[4:])
    app.dependency_overrides[judge_router.own_profile] = lambda: {"account_id": "acct",
                                                                   "profile": {**ME, "user_id": "Uask"}}
    yield TestClient(app)
    app.dependency_overrides.pop(judge_router.own_profile, None)


def test_router_focus(client):
    body = client.post("/judge?today=2026-11-01", json={"user_id": "Uask", "rule_id": "manual:m1"}).json()
    assert body["ask"]["field"] == "move_in_date" and body["ask"]["rule_id"] == "manual:m1"
