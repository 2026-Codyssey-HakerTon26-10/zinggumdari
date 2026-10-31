"""검수 전 AI 조건표 카드 접기(PR_REQUESTS 51번, #48 댓글).

검수 전 AI 조건표는 프로필이나 다음 단계의 단계 태그와 맞는 것만 카드로 올리고 나머지는 folded에 센다.
손 조건표·검수한 AI 조건표·내가 올린 조건표는 그대로 올린다.
"""

from datetime import date

from backend.engine.cards import build_judge

TODAY = date(2026, 11, 1)


def C(field, op, value, status="auto_verified"):
    return {"field": field, "op": op, "value": value, "evidence": ["doc:l1"], "status": status}


def AI(rid, conds, **kw):
    return {"id": rid, "source": "gov24", "subject": "self", "name": rid, "conditions": conds,
            "review": {"status": "unreviewed"}, "updated": "2026-10-31", "detail_url": "https://x", **kw}


def MANUAL(rid, conds, **kw):
    return {**AI(rid, conds, **kw), "source": "manual", "review": {"status": "reviewed"}}


ME = {"self": {"birth_year": 1999, "marital_status": "미혼", "children_count": 0, "income_self": 270},
      "parents": [], "consents": {"sensitive": True}}

YOUTH = AI("gov24:youth", [C("age", "<=", 34)])                      # 청년 태그 → 프로필과 맞음
NEWLYWED = AI("gov24:newlywed", [C("marriage_years", "<=", 7)])      # 신혼 태그 → 다음 단계와 맞음
MULTI = AI("gov24:multi", [C("children_count", ">=", 2)])            # 다자녀 태그 → 지금도 다음 단계도 아님
PLAIN = AI("gov24:plain", [C("income_self", "<=", 500)])             # 단계 태그 없음
ELDER = AI("gov24:elder", [C("age", ">=", 65)], subject="parent")


def ids(body):
    return [c["rule_id"] for c in body["cards"]]


def folded_ids(body):
    return [f["rule_id"] for f in body["folded"]["items"]]


def test_ai_cards_kept_only_when_tags_match_profile_or_next_step():
    body = build_judge(ME, [YOUTH, NEWLYWED, MULTI, PLAIN], TODAY)
    assert set(ids(body)) == {"gov24:youth", "gov24:newlywed"}
    assert body["folded"]["count"] == 2
    assert set(folded_ids(body)) == {"gov24:multi", "gov24:plain"}


def test_folded_items_have_name_and_verdict():
    item, = build_judge(ME, [PLAIN], TODAY)["folded"]["items"]
    assert set(item) == {"rule_id", "name", "subject", "verdict"}
    assert item["name"] == "gov24:plain" and item["verdict"] in ("eligible", "needs_check", "opens_later")


def test_step_moves_the_tags():
    # 첫째 아이 단계로 넘기면 다음 단계는 다자녀 → 다자녀 AI 조건표가 올라온다
    body = build_judge(ME, [MULTI], TODAY, step="child")
    assert ids(body) == ["gov24:multi"]
    assert body["folded"]["count"] == 0


def test_reviewed_manual_and_upload_always_shown():
    reviewed_ai = {**PLAIN, "id": "gov24:reviewed", "review": {"status": "reviewed"}}
    manual = MANUAL("manual:plain", [C("income_self", "<=", 500, status="reviewed")])
    upload = {**PLAIN, "id": "upload:mine", "source": "upload"}
    body = build_judge(ME, [reviewed_ai, manual, upload], TODAY)
    assert set(ids(body)) == {"gov24:reviewed", "manual:plain", "upload:mine"}
    assert body["folded"] == {"count": 0, "items": []}


def test_parent_ai_cards_follow_parents():
    mom = {**ME, "parents": [{"relation": "모", "birth_year": 1960}]}
    assert ids(build_judge(mom, [ELDER], TODAY)) == ["gov24:elder"]
    assert build_judge(ME, [ELDER], TODAY)["folded"]["count"] == 0   # 부모님이 없으면 원래 카드가 아님


def test_reviewed_cards_come_before_ai_cards():
    manual = MANUAL("manual:check", [C("age", "<=", 34, status="reviewed"),
                                     {"field": "other", "op": "==", "value": None, "evidence": ["doc:l2"],
                                      "status": "reviewed", "text": "순자산 기준 이하"}])
    body = build_judge(ME, [YOUTH, manual], TODAY)
    assert ids(body) == ["manual:check", "gov24:youth"]


def test_ask_ignores_folded_cards():
    # 접힌 카드의 칸은 묻지 않는다: 단계 태그 없는 AI 조건표 여러 개가 모르는 칸으로 갈려도 질문이 없다
    rules = [AI(f"gov24:p{i}", [C("household_size", "<=", i)]) for i in range(1, 9)]
    body = build_judge(ME, rules, TODAY)
    assert body["cards"] == [] and body["folded"]["count"] == 8
    assert body["ask"] is None
