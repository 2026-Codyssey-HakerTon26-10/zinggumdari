"""공고 투입 뒤 알림(PR_REQUESTS 22번). 업로드 조건표 알림은 올린 사람에게만 간다. DB 없이 돈다.

collector.ingest → notify.api.rebuild(rule_ids, account_id) → main.py가 연결한 handler → service.rebuild.
"""

from __future__ import annotations

import inspect
from contextlib import contextmanager
from datetime import date

from backend import db
from backend.app import main, sources
from backend.db import notifications as db_notif
from backend.db import profiles as db_profiles
from backend.notify import api as notify_api

TODAY = date(2026, 11, 1)


def C(field, op, value):
    return {"field": field, "op": op, "value": value, "evidence": ["doc:l1"], "status": "reviewed"}


def rule(rid, source):
    return {"id": rid, "source": source, "subject": "self", "name": rid, "conditions": [C("age", "<=", 39)],
            "review": {"status": "unreviewed"}, "updated": "2026-11-01", "detail_url": "https://x"}


PROFILES = {"U1": {"user_id": "U1", "self": {"birth_date": "1999-04-15"}, "parents": [], "consents": {}},
            "U2": {"user_id": "U2", "self": {"birth_date": "1998-01-01"}, "parents": [], "consents": {}}}
OWNERS = {"U1": "A1", "U2": "A2"}


class FakeConn:
    def __init__(self):
        self.sql = []

    def execute(self, sql, params=()):
        self.sql.append((sql, params))
        rows = [(u, a) for u, a in OWNERS.items() if not params or a == params[0]]
        return type("R", (), {"fetchall": lambda _: rows})()


def _wire(monkeypatch, loaded):
    saved, conn = [], FakeConn()

    @contextmanager
    def fake_connect():
        yield conn

    def fake_load_rules(owner=None):
        loaded.append(owner)
        out = [rule("gov24:pub", "gov24")]
        return out + [rule("upload:a1-notice", "upload")] if owner == "A1" else out

    monkeypatch.setattr(db, "connect", fake_connect)
    monkeypatch.setattr(db_profiles, "load", lambda c, uid: dict(PROFILES[uid]))
    monkeypatch.setattr(db_notif, "upsert", lambda c, uid, item: saved.append((uid, item["rule_id"])))
    monkeypatch.setattr(sources, "load_rules", fake_load_rules)
    return saved


def test_handler_is_connected_with_account_scope():
    assert notify_api._handler is not None
    assert "account_id" in inspect.signature(notify_api._handler).parameters


def test_upload_alert_goes_only_to_uploader(monkeypatch):
    loaded = []
    saved = _wire(monkeypatch, loaded)
    out = notify_api.rebuild(rule_ids=["upload:a1-notice"], today=TODAY, account_id="A1")
    assert loaded == ["A1"]                       # 올린 사람의 업로드만 읽는다
    assert saved == [("U1", "upload:a1-notice")]  # 다른 계정(U2)에는 가지 않는다
    assert out["processed_profiles"] == 1


def test_store_failure_does_not_break_ingest(monkeypatch):
    @contextmanager
    def broken():
        raise RuntimeError("DB 없음")
        yield

    monkeypatch.setattr(db, "connect", broken)
    out = notify_api.rebuild(rule_ids=["upload:a1-notice"], today=TODAY, account_id="A1")
    assert out["status"] == "failed" and out["notifications"] == 0
