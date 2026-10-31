"""/profiles·/judge가 세션의 본인 프로필(DB)만 쓰는지 (docs/api.md 「인증·소유권 계약」).

- DB 없이: 미인증 401, 판정 라우터의 소유권 분기(로더를 바꿔 끼움), 업로드 owner 전달.
- DB 있으면(TEST_DATABASE_URL): 가입 → 프리셋 → 판정까지 실제 저장소로.
"""

from __future__ import annotations

import secrets

import pytest
from fastapi.testclient import TestClient

from backend.app import sources
from backend.app.main import app
from backend.app.routers import judge
from backend.data.config import env

ME = {"user_id": "Uown", "stages_done": ["signup"], "consents": {"sensitive": True, "parent": False},
      "self": {"birth_year": 1999, "marital_status": "미혼", "income_self": 270}, "parents": []}
OK = {"id": "manual:ok", "source": "manual", "subject": "self", "name": "ok", "updated": "2026-10-31",
      "detail_url": "https://x", "review": {"status": "reviewed"},
      "conditions": [{"field": "age", "op": "<=", "value": 34, "evidence": ["doc:l1"], "status": "reviewed"}]}


# ── DB 없이 ──────────────────────────────────────────────────────────────────

def test_profiles_and_judge_need_login(monkeypatch):
    monkeypatch.delenv("DEV_STUB_API", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    client = TestClient(app)
    assert client.post("/profiles", json={"self": {}}).status_code == 401
    assert client.get("/profiles/U7f3a").status_code == 401
    assert client.post("/profiles/presets/jiwon").status_code == 401
    assert client.post("/judge", json={}).status_code == 401


def test_dev_stub_does_not_open_judge(monkeypatch):
    # 개발 모드를 켜도 운영 경로가 user_id만으로 남의 판정을 보여주지 않는다
    monkeypatch.setenv("DEV_STUB_API", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert TestClient(app).post("/judge", json={"user_id": "U7f3a"}).status_code == 401


def test_presets_list_is_public():
    assert TestClient(app).get("/profiles/presets").json()[0]["id"] == "jiwon"


@pytest.fixture
def as_owner(monkeypatch):
    seen = {}

    def rules(owner=None):
        seen["rules_owner"] = owner
        return [OK]

    def evidence(ids, owner=None):
        seen["evidence_owner"] = owner
        return [{"id": i, "page": None, "bbox": None, "text": None} for i in ids]

    monkeypatch.setattr(sources, "load_rules", rules)
    monkeypatch.setattr(sources, "evidence", evidence)
    app.dependency_overrides[judge.own_profile] = lambda: {"account_id": "acct-1", "profile": ME}
    yield TestClient(app), seen
    app.dependency_overrides.pop(judge.own_profile, None)


def test_judge_uses_own_profile_and_owner(as_owner):
    client, seen = as_owner
    body = client.post("/judge?today=2026-11-01", json={}).json()
    assert body["user_id"] == "Uown" and [c["rule_id"] for c in body["cards"]] == ["manual:ok"]
    assert seen == {"rules_owner": "acct-1", "evidence_owner": "acct-1"}   # 업로드는 올린 본인 것만


def test_judge_same_user_id_ok_other_403(as_owner):
    client, _ = as_owner
    assert client.post("/judge", json={"user_id": "Uown"}).status_code == 200
    assert client.post("/judge", json={"user_id": "Uother"}).status_code == 403


def test_judge_stub_fallback_keeps_own_id(as_owner, monkeypatch):
    client, _ = as_owner
    monkeypatch.setattr(sources, "load_rules", lambda owner=None: [])
    assert client.post("/judge", json={}).json()["user_id"] == "Uown"


# ── DB 있으면 ────────────────────────────────────────────────────────────────

_URL = env("TEST_DATABASE_URL")
_db = pytest.mark.skipif(not _URL, reason="TEST_DATABASE_URL 없음")


@pytest.fixture
def db_client(monkeypatch):
    import psycopg

    from backend.db import migrate

    name = "test_" + secrets.token_hex(6)

    def _connect(url=None):
        c = psycopg.connect(url or _URL, autocommit=True)
        c.execute(f"SET search_path TO {name}")
        return c

    admin = psycopg.connect(_URL, autocommit=True)
    admin.execute(f"CREATE SCHEMA {name}")
    admin.execute(f"SET search_path TO {name}")
    migrate.run(admin)
    monkeypatch.setattr("backend.db.connect", _connect)
    monkeypatch.setattr("backend.app.routers.auth.connect", _connect)
    monkeypatch.setattr(sources, "load_rules", lambda owner=None: [OK])
    try:
        yield lambda: TestClient(app)
    finally:
        admin.execute(f"DROP SCHEMA IF EXISTS {name} CASCADE")
        admin.close()


def _signup(client, email):
    assert client.post("/auth/signup", json={"email": email, "password": "pass1234"}).status_code == 201


@_db
def test_preset_to_judge_end_to_end(db_client):
    me = db_client()
    _signup(me, "a@test.com")
    assert me.post("/judge", json={}).status_code == 404            # 프로필 전

    user_id = me.post("/profiles/presets/jiwon").json()["user_id"]
    assert me.get("/auth/me").json()["user_id"] == user_id          # 검색 배지가 쓰는 세션 프로필과 같다
    p = me.get(f"/profiles/{user_id}?today=2026-11-01").json()
    assert p["self"]["birth_year"] == 1999 and p["parents"][0]["birth_year"] == 1966
    assert p["derived"]["tags"] == ["youth", "marriage_planned", "homeless"]

    body = me.post("/judge?today=2026-11-01", json={}).json()
    assert body["user_id"] == user_id and [c["rule_id"] for c in body["cards"]] == ["manual:ok"]
    assert me.post("/profiles/presets/jiwon").status_code == 409    # 계정당 하나


@_db
def test_other_account_cannot_see(db_client):
    a, b = db_client(), db_client()
    _signup(a, "a@test.com")
    _signup(b, "b@test.com")
    a_id = a.post("/profiles", json={"self": {"birth_year": 1996}}).json()["user_id"]
    b.post("/profiles", json={"self": {"birth_year": 1990}})
    assert b.get(f"/profiles/{a_id}").status_code == 404             # 남의 것은 없는 것과 같다
    assert b.patch(f"/profiles/{a_id}", json={"self": {"sido": "서울"}}).status_code == 404
    assert b.delete(f"/profiles/{a_id}").status_code == 404
    assert b.post("/judge", json={"user_id": a_id}).status_code == 403
    assert a.get(f"/profiles/{a_id}").json()["self"]["birth_year"] == 1996
