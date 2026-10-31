"""main.py 알림·통계 라우터 연결 테스트 (#41). DB 없이 돈다.

DB 모듈은 monkeypatch로 바꿔 끼운다. main.py가 메서드 안에서 import하므로
모듈 속성을 바꾸면 그대로 쓰인다.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend import db
from backend.app import main
from backend.db import notifications as db_notif
from backend.db import profiles as db_profiles

client = TestClient(main.app)


# ── 등록·인증 ────────────────────────────────────────────────────────────────

def test_routes_registered():
    paths = main.app.openapi()["paths"]
    for p in ("/notifications", "/notifications/{notification_id}/read", "/notify/test-email",
              "/trigger/rebuild", "/stats/coverage", "/stats/explore"):
        assert p in paths


def test_notifications_need_login():
    assert client.get("/notifications").status_code == 401
    assert client.post("/notify/test-email").status_code == 401


def test_rebuild_forbidden_without_admin_token_setting(monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(main, "env", lambda k: None)
    assert client.post("/trigger/rebuild", headers={"X-Admin-Token": "x"}).status_code == 403


def test_rebuild_forbidden_with_wrong_token(monkeypatch):
    monkeypatch.setattr(main, "env", lambda k: "right" if k == "ADMIN_TOKEN" else None)
    assert client.post("/trigger/rebuild", headers={"X-Admin-Token": "wrong"}).status_code == 403
    assert client.post("/trigger/rebuild").status_code == 403


# ── 저장소 오류는 숨기지 않는다 ──────────────────────────────────────────────

@contextmanager
def _fake_conn():
    yield object()


def _broken(*a, **k):
    raise RuntimeError("db down")


def test_list_db_error_is_503_not_empty(monkeypatch):
    monkeypatch.setattr(db, "connect", _broken)
    with pytest.raises(HTTPException) as e:
        main._NotifyStore().list("u1")
    assert e.value.status_code == 503


def test_mark_read_db_error_is_503_not_404(monkeypatch):
    monkeypatch.setattr(db, "connect", _broken)
    with pytest.raises(HTTPException) as e:
        main._NotifyStore().mark_read("u1", "n1")
    assert e.value.status_code == 503


def test_rebuild_db_error_is_503_not_200(monkeypatch):
    monkeypatch.setattr(db, "connect", _broken)
    with pytest.raises(HTTPException) as e:
        main._NotifyStore().rebuild(None)
    assert e.value.status_code == 503


# ── 테스트 메일 ──────────────────────────────────────────────────────────────

def _email_setup(monkeypatch, alert_self):
    monkeypatch.setattr(db, "connect", lambda *a, **k: _fake_conn())
    monkeypatch.setattr(db_profiles, "load",
                        lambda conn, uid: {"user_id": uid, "self": alert_self, "parents": []})
    monkeypatch.setattr(db_notif, "list_for_user",
                        lambda conn, uid: [{"id": "n1", "title": "새 제도", "emailed_at": None}])


@pytest.mark.parametrize("cats", [None, []])
def test_test_email_without_categories_is_not_500(monkeypatch, cats):
    _email_setup(monkeypatch, {"alert_channel": "이메일", "alert_categories": cats, "email": "a@b.c"})
    out = main._NotifyStore().test_email("u1")
    assert out["sent"] is False


def test_test_email_without_smtp_setting_is_503(monkeypatch):
    _email_setup(monkeypatch, {"alert_channel": "이메일", "alert_categories": ["주거"], "email": "a@b.c"})
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("MAIL_FROM", raising=False)
    with pytest.raises(HTTPException) as e:
        main._NotifyStore().test_email("u1")
    assert e.value.status_code == 503
