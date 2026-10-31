"""/judge의 비슷한 가구(api.md §3 similar). 가상 인구 캐시 대신 가짜 similar_for를 끼운다."""

from datetime import date

from fastapi.testclient import TestClient

from backend.app import sources
from backend.app.main import app
from backend.app.routers import judge
from backend.engine import similar
from backend.engine.cards import build_judge

TODAY = date(2026, 11, 1)
OK = {"id": "manual:ok", "source": "manual", "subject": "self", "name": "ok", "review": {"status": "reviewed"},
      "conditions": [{"field": "age", "op": "<=", "value": 34, "evidence": ["doc:l1"], "status": "reviewed"}],
      "updated": "2026-10-31", "detail_url": "https://x"}
ME = {"user_id": "Utest", "self": {"birth_date": "1999-04-15", "marital_status": "미혼"}, "parents": [],
      "consents": {"sensitive": True}}
SIMILAR = {"method": "knn", "k": 50, "neighbors": 50, "basis": "가상 인구", "label": "청년", "label_share": 0.6,
           "known_fields": 3, "assignment": "full", "items": []}


def test_similar_gets_profile_and_verdicts():
    seen = {}

    def fake(profile, verdicts):
        seen.update(profile=profile, verdicts=verdicts)
        return SIMILAR

    body = build_judge(ME, [OK], TODAY, similar=fake)
    assert body["similar"] == SIMILAR
    assert seen["profile"]["user_id"] == "Utest" and seen["verdicts"]["manual:ok"]["verdict"] == "eligible"


def test_similar_failure_keeps_cards():
    def broken(profile, verdicts):
        raise ValueError("캐시가 깨짐")

    body = build_judge(ME, [OK], TODAY, similar=broken)
    assert body["similar"] is None and [c["rule_id"] for c in body["cards"]] == ["manual:ok"]


def test_without_similar_is_null():
    assert build_judge(ME, [OK], TODAY)["similar"] is None


def test_router_wires_similar_for(monkeypatch):
    calls = []

    def fake(profile, verdicts, rules, today=None, k=similar.K):
        calls.append(([r["id"] for r in rules], today))
        return SIMILAR

    monkeypatch.setattr(sources, "load_rules", lambda owner=None: [OK])
    monkeypatch.setattr(similar, "similar_for", fake)
    app.dependency_overrides[judge.own_profile] = lambda: {"account_id": "acct", "profile": ME}
    try:
        body = TestClient(app).post("/judge?today=2026-11-01", json={}).json()
    finally:
        app.dependency_overrides.pop(judge.own_profile, None)
    assert body["similar"] == SIMILAR
    assert calls == [(["manual:ok"], TODAY)]
