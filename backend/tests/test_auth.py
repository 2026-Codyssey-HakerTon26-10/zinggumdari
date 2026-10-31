"""인증 DB 레이어 + HTTP 엔드포인트 테스트.

비밀번호 해시·검증 테스트: DB 없이 항상 실행.
세션 CRUD + HTTP 엔드포인트: TEST_DATABASE_URL이 없으면 건너뛴다.
"""

from __future__ import annotations

import secrets
from contextlib import contextmanager

import pytest

from backend.data.config import env
from backend.db import sessions

_URL = env("TEST_DATABASE_URL")
_db = pytest.mark.skipif(not _URL, reason="TEST_DATABASE_URL 없음")

if _URL:
    import psycopg

    from backend.db import connect, migrate, profiles


# ── 격리 스키마 (test_db.py와 동일 패턴) ────────────────────────────────────

@contextmanager
def _isolated_schema():
    name = "test_" + secrets.token_hex(6)
    c = connect(_URL)
    try:
        c.execute(f"CREATE SCHEMA {name}")
        c.execute(f"SET search_path TO {name}")
        migrate.run(c)
        yield c, name
    finally:
        c.execute(f"DROP SCHEMA IF EXISTS {name} CASCADE")
        c.close()


@pytest.fixture
def conn():
    with _isolated_schema() as (c, _):
        yield c


def _account(conn, email="auth@example.com"):
    return profiles.create_account(conn, email, sessions.hash_password("pass1234"))


# ── 비밀번호 해시 (DB 불필요, 항상 실행) ─────────────────────────────────────

def test_hash_and_verify_correct_password():
    h = sessions.hash_password("비밀번호1!")
    assert sessions.verify_password("비밀번호1!", h)


def test_wrong_password_fails():
    h = sessions.hash_password("correct")
    assert not sessions.verify_password("wrong", h)


def test_each_hash_is_unique():
    """같은 비밀번호라도 솔트가 달라 해시값이 달라야 한다."""
    assert sessions.hash_password("same") != sessions.hash_password("same")


def test_verify_bad_format_returns_false():
    assert not sessions.verify_password("pw", "notavalidhash")


# ── 세션 CRUD (DB 필요) ───────────────────────────────────────────────────────

@_db
def test_create_and_get_session(conn):
    account_id = _account(conn)
    token = sessions.create_session(conn, account_id)
    sess = sessions.get_session(conn, token)
    assert sess is not None
    assert sess["account_id"] == account_id


@_db
def test_wrong_token_returns_none(conn):
    _account(conn)
    assert sessions.get_session(conn, "invalid_token") is None


@_db
def test_revoke_session(conn):
    account_id = _account(conn)
    token = sessions.create_session(conn, account_id)
    sessions.revoke_session(conn, token)
    assert sessions.get_session(conn, token) is None


@_db
def test_multiple_sessions_per_account(conn):
    account_id = _account(conn)
    t1 = sessions.create_session(conn, account_id)
    t2 = sessions.create_session(conn, account_id)
    assert sessions.get_session(conn, t1) is not None
    assert sessions.get_session(conn, t2) is not None


@_db
def test_revoke_one_does_not_affect_other(conn):
    account_id = _account(conn)
    t1 = sessions.create_session(conn, account_id)
    t2 = sessions.create_session(conn, account_id)
    sessions.revoke_session(conn, t1)
    assert sessions.get_session(conn, t1) is None
    assert sessions.get_session(conn, t2) is not None


# ── HTTP 엔드포인트 (DB 필요) ─────────────────────────────────────────────────

@pytest.fixture
def client(monkeypatch):
    """격리 스키마를 쓰는 TestClient. auth 라우터의 connect를 몽키패치."""
    with _isolated_schema() as (_, name):
        def _connect(url_override=None):
            c = psycopg.connect(url_override or _URL, autocommit=True)
            c.execute(f"SET search_path TO {name}")
            return c

        monkeypatch.setattr("backend.app.routers.auth.connect", _connect)
        from backend.app.routers import auth as auth_router
        monkeypatch.setattr(auth_router, "limiter", auth_router.LoginLimiter())   # 테스트끼리 실패 횟수를 나누지 않게

        from fastapi.testclient import TestClient
        from backend.app.main import app
        yield TestClient(app, raise_server_exceptions=True)


@_db
def test_signup_returns_201(client):
    r = client.post("/auth/signup", json={"email": "new@test.com", "password": "pass1234"})
    assert r.status_code == 201
    assert "account_id" in r.json()
    assert "session" in r.cookies


@_db
def test_signup_duplicate_email_returns_409(client):
    client.post("/auth/signup", json={"email": "dup@test.com", "password": "pass1234"})
    r = client.post("/auth/signup", json={"email": "dup@test.com", "password": "pass1234"})
    assert r.status_code == 409


@_db
def test_login_success(client):
    client.post("/auth/signup", json={"email": "user@test.com", "password": "pass1234"})
    r = client.post("/auth/login", json={"email": "user@test.com", "password": "pass1234"})
    assert r.status_code == 200
    assert "account_id" in r.json()
    assert "session" in r.cookies


@_db
def test_login_wrong_password_returns_401(client):
    client.post("/auth/signup", json={"email": "u@test.com", "password": "real1234"})
    r = client.post("/auth/login", json={"email": "u@test.com", "password": "wrong123"})
    assert r.status_code == 401
    assert r.json()["detail"] == "이메일 또는 비밀번호가 올바르지 않습니다"


@_db
def test_login_unknown_email_returns_401(client):
    r = client.post("/auth/login", json={"email": "nobody@test.com", "password": "x"})
    assert r.status_code == 401
    assert r.json()["detail"] == "이메일 또는 비밀번호가 올바르지 않습니다"


@_db
def test_login_case_insensitive_email(client):
    client.post("/auth/signup", json={"email": "Case@Test.com", "password": "pass1234"})
    r = client.post("/auth/login", json={"email": "case@test.com", "password": "pass1234"})
    assert r.status_code == 200


@_db
def test_me_requires_login(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


@_db
def test_me_returns_account_info(client):
    client.post("/auth/signup", json={"email": "me@test.com", "password": "pass1234"})
    r = client.get("/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "me@test.com"
    assert data["user_id"] is None   # 프로필 아직 없음


@_db
def test_logout_clears_session(client):
    client.post("/auth/signup", json={"email": "lo@test.com", "password": "pass1234"})
    client.post("/auth/logout")
    r = client.get("/auth/me")
    assert r.status_code == 401


@_db
def test_logout_without_session_is_ok(client):
    r = client.post("/auth/logout")
    assert r.status_code == 204


@_db
def test_delete_me_removes_account(client):
    client.post("/auth/signup", json={"email": "bye@test.com", "password": "pass1234"})
    r = client.delete("/auth/me")
    assert r.status_code == 204
    # 삭제 후 같은 이메일로 재가입 가능
    r2 = client.post("/auth/signup", json={"email": "bye@test.com", "password": "pass5678"})
    assert r2.status_code == 201


@_db
def test_delete_me_requires_login(client):
    r = client.delete("/auth/me")
    assert r.status_code == 401


# ── 가입 검증: 비밀번호 8~128자, 이메일 형식 (DB 없이도 422) ─────────────────────

@pytest.mark.parametrize("body", [
    {"email": "ok@test.com", "password": "short7!"},          # 7자
    {"email": "ok@test.com", "password": "x" * 129},          # 129자
    {"email": "not-an-email", "password": "pass1234"},
    {"email": "a@b", "password": "pass1234"},
    {"email": "a b@test.com", "password": "pass1234"},
    {"email": "", "password": "pass1234"},
])
def test_signup_rejects_bad_input(body):
    from fastapi.testclient import TestClient

    from backend.app.main import app
    r = TestClient(app).post("/auth/signup", json=body)
    assert r.status_code == 422
    assert "pass1234" not in r.text and "short7!" not in r.text   # 비밀번호 값을 에러에 되돌려주지 않는다


@_db
@pytest.mark.parametrize("password", ["x" * 8, "x" * 128])
def test_signup_accepts_boundary_lengths(client, password):
    assert client.post("/auth/signup", json={"email": "edge@test.com", "password": password}).status_code == 201


# ── 가입 닉네임·필수 동의 (SPEC §4.1). 지금 화면은 이메일·비밀번호만 보내므로 둘 다 선택 칸 ─────────

@pytest.mark.parametrize("extra", [
    {"nickname": "a"},                                        # 1자
    {"nickname": "가" * 17},                                  # 17자
    {"nickname": "   "},
    {"consents": {"terms": True, "privacy": False}},          # 필수 동의 빠짐
    {"consents": {"terms": True}},
    {"consents": {"terms": "true", "privacy": True}},         # JSON true만
    {"consents": {"terms": True, "privacy": True, "email": True}},   # 선택 동의는 여기서 받지 않는다
])
def test_signup_rejects_bad_nickname_or_consents(extra):
    from fastapi.testclient import TestClient

    from backend.app.main import app
    r = TestClient(app).post("/auth/signup", json={"email": "ok@test.com", "password": "pass1234", **extra})
    assert r.status_code == 422


@_db
def test_signup_saves_nickname_and_consents(client):
    r = client.post("/auth/signup", json={"email": "n@test.com", "password": "pass1234", "nickname": " 지원 ",
                                          "consents": {"terms": True, "privacy": True}})
    assert r.status_code == 201
    me = client.get("/auth/me").json()
    assert me["nickname"] == "지원" and me["consents"]["terms"] and me["consents"]["privacy"]


@_db
def test_signup_without_new_fields_still_works(client):
    assert client.post("/auth/signup", json={"email": "old@test.com", "password": "pass1234"}).status_code == 201
    me = client.get("/auth/me").json()
    assert me["nickname"] is None and me["consents"] == {"terms": None, "privacy": None}


# ── 로그인 반복 요청 제한 ─────────────────────────────────────────────────────

def test_login_limiter_blocks_after_failures():
    from backend.app.routers.auth import LoginLimiter
    now = [0.0]
    lim = LoginLimiter(max_fails=3, window=60, clock=lambda: now[0])
    for _ in range(3):
        assert lim.retry_after("a@x.com", "1.1.1.1") == 0
        lim.failed("a@x.com", "1.1.1.1")
    assert lim.retry_after("A@X.com", "2.2.2.2") > 0          # 이메일은 대소문자 무시, 다른 IP에서도 막힌다
    assert lim.retry_after("b@x.com", "2.2.2.2") == 0         # 다른 계정은 막지 않는다
    now[0] = 61
    assert lim.retry_after("a@x.com", "1.1.1.1") == 0         # 창이 지나면 풀린다


def test_login_limiter_success_clears_email():
    from backend.app.routers.auth import LoginLimiter
    lim = LoginLimiter(max_fails=2, window=60, clock=lambda: 0.0)
    lim.failed("a@x.com", "ip")
    lim.succeeded("a@x.com")
    lim.failed("a@x.com", "ip")
    assert lim.retry_after("a@x.com", "ip") == 0


def test_login_limiter_caps_one_ip_across_emails():
    from backend.app.routers.auth import LoginLimiter
    lim = LoginLimiter(max_fails=100, window=60, ip_max_fails=3, clock=lambda: 0.0)
    for i in range(3):
        lim.failed(f"u{i}@x.com", "9.9.9.9")
    assert lim.retry_after("new@x.com", "9.9.9.9") > 0       # 한 IP가 여러 이메일을 두드리는 것도 막는다


@_db
def test_login_returns_429_with_retry_after(client, monkeypatch):
    from backend.app.routers import auth as auth_router
    monkeypatch.setattr(auth_router, "limiter", auth_router.LoginLimiter(max_fails=2, window=60))
    client.post("/auth/signup", json={"email": "rl@test.com", "password": "pass1234"})
    for _ in range(2):
        assert client.post("/auth/login", json={"email": "rl@test.com", "password": "wrong123"}).status_code == 401
    r = client.post("/auth/login", json={"email": "rl@test.com", "password": "pass1234"})   # 맞는 비밀번호여도
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    assert "rl@test.com" not in r.text


# ── 탈퇴: 프로필 없이 올린 업로드도 계정 기준으로 지운다 ──────────────────────────

@_db
def test_delete_me_deletes_uploads_without_profile(client, monkeypatch):
    import backend.collector.ingest as ing
    seen = []
    monkeypatch.setattr(ing, "delete_uploads", lambda account_id: seen.append(account_id) or 0)
    account_id = client.post("/auth/signup", json={"email": "up@test.com", "password": "pass1234"}).json()["account_id"]
    assert client.get("/auth/me").json()["user_id"] is None
    assert client.delete("/auth/me").status_code == 204
    assert seen == [account_id]
