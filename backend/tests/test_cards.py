"""/judge 응답 조립(backend/engine/cards.py)과 라우터 연결."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.app import sources
from backend.app.main import app
from backend.app.routers import profiles
from backend.engine.cards import DISCLAIMER, build_judge

TODAY = date(2026, 11, 1)


def C(field, op, value, ev="doc:l1", **kw):
    return {"field": field, "op": op, "value": value, "evidence": [ev], "status": "reviewed", **kw}


def R(rid, conds, **kw):
    return {"id": rid, "source": "manual", "subject": "self", "name": rid.split(":")[1], "conditions": conds,
            "review": {"status": "reviewed"}, "updated": "2026-10-31", "detail_url": "https://x", **kw}


ME = {"self": {"birth_year": 1999, "marital_status": "미혼", "income_self": 270}, "parents": [],
      "consents": {"sensitive": True}}

OK = R("manual:ok", [C("age", "<=", 34)])
CHECK = R("manual:check", [C("age", "<=", 34), C("other", "==", None, text="순자산 기준 이하")])
NO = R("manual:no", [C("age", "<=", 20)])   # 나이가 줄진 않으니 시간이 지나도 안 열림
LATER = R("manual:later", [C("apply_date", ">=", "2027-01-01")])
MOM = R("manual:mom", [C("age", ">=", 65)], subject="parent")


def ids(body):
    return [c["rule_id"] for c in body["cards"]]


def test_shape():
    body = build_judge(ME, [OK], TODAY)
    assert set(body) >= {"user_id", "ask", "cards", "timeline", "similar", "disclaimer"}
    assert body["disclaimer"] == DISCLAIMER
    card = body["cards"][0]
    assert card["detail_url"] and card["updated"]
    assert set(card) >= {"rule_id", "verdict", "conditions", "exclusive_with", "documents", "explain",
                         "opens_at", "closes_at", "apply_from", "prerequisites"}


def test_ineligible_hidden_and_order():
    body = build_judge(ME, [LATER, NO, CHECK, OK], TODAY)
    assert ids(body) == ["manual:ok", "manual:check", "manual:later"]


def test_parent_cards_only_with_parents():
    assert "manual:mom" not in ids(build_judge(ME, [MOM], TODAY))
    with_mom = {**ME, "parents": [{"relation": "모", "birth_year": 1966}]}
    assert ids(build_judge(with_mom, [MOM], TODAY)) == ["manual:mom"]


def test_superseded_hidden():
    ai = R("gov24:a", [C("age", "<=", 34)], source="gov24")
    manual = R("manual:a", [C("age", "<=", 34)], same_as=["gov24:a"])
    assert ids(build_judge(ME, [ai, manual], TODAY)) == ["manual:a"]


def test_evidence_filled():
    def fake(evs):
        return [{"id": e, "page": 3, "bbox": [1, 2, 3, 4], "text": "만 34세 이하"} for e in evs]
    card = build_judge(ME, [OK], TODAY, evidence=fake)["cards"][0]
    assert card["conditions"][0]["evidence"] == [{"id": "doc:l1", "page": 3, "bbox": [1, 2, 3, 4], "text": "만 34세 이하"}]


def test_exclusive_with_names():
    a = R("manual:a", [C("age", "<=", 34)], exclusive_with=["manual:b"], name="청년 버팀목")
    b = R("manual:b", [C("age", "<=", 34)], exclusive_with=["manual:a"], name="신혼 전세")
    card = build_judge(ME, [a, b], TODAY)["cards"][0]
    assert card["exclusive_with"] == [{"rule_id": "manual:b", "name": "신혼 전세", "both_eligible": True}]


def test_documents_without_dictionary():
    rule = {**OK, "documents": ["임대차계약서"], "documents_official": ["주민등록등본"]}
    docs = build_judge(ME, [rule], TODAY)["cards"][0]["documents"]
    assert docs == [{"name": "임대차계약서", "doc_id": None, "who_provides": "applicant", "status": "unknown"},
                    {"name": "주민등록등본", "doc_id": None, "who_provides": "official", "status": "unknown"}]


# 라우터 -----------------------------------------------------------------------------------------

client = TestClient(app)


@pytest.fixture(autouse=True)
def dev(monkeypatch):
    monkeypatch.setenv("DEV_STUB_API", "1")


def test_router_uses_engine_when_rules_exist(monkeypatch):
    monkeypatch.setattr(sources, "load_rules", lambda: [OK, NO])
    profiles._store["Utest"] = {"user_id": "Utest", **ME}
    body = client.post("/judge?today=2026-11-01", json={"user_id": "Utest"}).json()
    assert body["user_id"] == "Utest" and ids(body) == ["manual:ok"]


def test_router_unknown_user_404(monkeypatch):
    monkeypatch.setattr(sources, "load_rules", lambda: [OK])
    assert client.post("/judge", json={"user_id": "Unope"}).status_code == 404


def test_router_falls_back_to_stub_without_rules(monkeypatch):
    monkeypatch.setattr(sources, "load_rules", lambda: [])
    body = client.post("/judge", json={"user_id": "U7f3a"}).json()
    assert body["cards"][0]["rule_id"] == "manual:hug-newlywed-jeonse"


# 업로드 소유권(요청 41) · 근거 줄(요청 40) --------------------------------------------------------

def test_uploads_are_not_read(tmp_path, monkeypatch):
    import json

    from backend.data import config
    dirs = {name: tmp_path / name for name in ("manual", "compiled", "uploads")}
    for d in dirs.values():
        d.mkdir()
    (dirs["manual"] / "ok.json").write_text(json.dumps(OK), encoding="utf-8")
    (dirs["uploads"] / "a.json").write_text(json.dumps(R("upload:a-secret", [C("age", "<=", 34)], source="upload")), encoding="utf-8")
    monkeypatch.setattr(config, "RULES_DIRS", (dirs["manual"], dirs["compiled"]))
    monkeypatch.setattr(config, "UPLOAD_RULES_DIR", dirs["uploads"])
    assert [r["id"] for r in sources.load_rules()] == ["manual:ok"]   # owner 없이는 업로드를 읽지 않는다


def test_manual_rules_have_evidence_text():
    """커밋된 손 조건표의 근거 줄은 전부 data/notices에 원문이 있어야 한다(SPEC §8)."""
    missing = []
    for rule in sources.load_rules():
        if rule.get("source") != "manual":
            continue
        groups = rule.get("conditions") or []
        ids = [e for c in groups for e in c.get("evidence") or []]
        missing += [e["id"] for e in sources.evidence(ids) if e["text"] is None]
    assert missing == []


def test_missing_evidence_is_logged(caplog):
    with caplog.at_level("WARNING"):
        build_judge(ME, [OK], TODAY)
    assert "doc:l1" in caplog.text


def test_owner_sees_only_own_uploads(tmp_path, monkeypatch):
    """로그인이 붙으면 owner를 넘긴다: 그 계정이 올린 업로드만 더해진다(backend.data.rules, #20)."""
    import inspect

    from backend.data import rules as loader
    assert "owner" in inspect.signature(loader.load_rules).parameters
    seen = {}
    monkeypatch.setattr(loader, "load_rules", lambda dirs=None, owner=None: seen.setdefault("owner", owner) and [])
    monkeypatch.setattr(sources, "_load", loader.load_rules)
    sources.load_rules(owner="acct-a")
    assert seen["owner"] == "acct-a"
