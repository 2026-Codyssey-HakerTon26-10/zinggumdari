from datetime import date
from unittest.mock import MagicMock
import smtplib
import pytest

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.notify.service import notification, rebuild
from backend.notify.email import send_email, DeliveryRecordError
from backend.notify.router import create_router

TODAY = date(2026, 10, 31)
RULE = dict(id="r", name="가상 제도", subject="self", review={"status": "unreviewed"},
            conditions=[dict(status="needs_review", evidence=["d:l1"])])


def test_notification_safety_and_deduplication():
    assert notification("u", RULE, {"verdict": "ineligible"}, today=TODAY) is None
    assert notification("u", RULE, {"verdict": "eligible", "deadline": "2026-01-01"}, today=TODAY) is None
    a = notification("u", RULE, {"verdict": "eligible"}, today=TODAY)
    assert "신청할 수" not in a["title"]
    assert a == notification("u", RULE, {"verdict": "eligible"}, today=TODAY)
    event = dict(kind="closing", due="2026-10-31", title="기한 안내", evidence=["d:l1"])
    assert notification("u", RULE, {"verdict": "needs_check"}, today=TODAY, event=event) is None
    trusted = {**RULE, "conditions": [dict(status="auto_verified", evidence=["d:l1"])]}
    assert notification("u", trusted, {"verdict": "needs_check"}, today=TODAY, event=event)


def test_email_opt_in_and_record_only_after_delivery(monkeypatch):
    profile = dict(user_id="u", self=dict(email="demo@example.invalid", alert_channel="이메일", alert_categories=["주거"]))
    item = dict(id="n", title="조건 확인")
    factory, record = MagicMock(), MagicMock()
    assert not send_email(profile, item, category="돌봄", record_sent=record, smtp_factory=factory)
    factory.assert_not_called()
    monkeypatch.setenv("SMTP_HOST", "smtp.example.invalid")
    monkeypatch.setenv("MAIL_FROM", "demo@example.invalid")
    factory.return_value.__enter__.return_value.send_message.return_value = {}
    assert send_email(profile, item, category="주거", record_sent=record, smtp_factory=factory)
    record.assert_called_once()
    record.reset_mock()
    factory.return_value.__enter__.return_value.send_message.side_effect = smtplib.SMTPException("delivery failed")
    with pytest.raises(smtplib.SMTPException):
        send_email(profile, item, category="주거", record_sent=record, smtp_factory=factory)
    record.assert_not_called()


def test_routes_require_session_and_pass_owner_to_store():
    store = MagicMock()
    def unauthorized():
        raise HTTPException(401)
    app = FastAPI()
    app.include_router(create_router(store, unauthorized, unauthorized))
    client = TestClient(app)
    assert client.get("/notifications?user_id=other").status_code == 401
    assert client.post("/trigger/rebuild").status_code == 401
    store.list.assert_not_called()
    app.dependency_overrides[unauthorized] = lambda: "owner"
    store.list.return_value = []
    assert client.get("/notifications?user_id=other").json() == []
    store.list.assert_called_once_with("owner")


def test_rebuild_forwards_date_and_skips_irrelevant_cards():
    future = date(2031, 1, 15)
    judge = MagicMock(return_value={"r": {"verdict": "needs_check", "no_subject": True}})
    save = MagicMock()
    rebuild([{"user_id": "u"}], [RULE], judge, save, today=future)
    judge.assert_called_once_with({"user_id": "u"}, [RULE], today=future)
    save.assert_not_called()
    judge.return_value = {"r": {"verdict": "needs_check", "superseded_by": "manual:r"}}
    rebuild([{"user_id": "u"}], [RULE], judge, save, today=future)
    save.assert_not_called()
    judge.return_value = {"r": {"verdict": "needs_check"}}
    rebuild([{"user_id": "u"}], [RULE], judge, save, today=future, rule_ids=[])
    save.assert_not_called()


def test_future_open_date_uses_planner_window():
    trusted = {**RULE, "conditions": [dict(status="reviewed", evidence=["d:l1"])]}
    event = dict(kind="apply_open", due="2031", title="부모님 신청 시기를 확인해 보세요", evidence=["d:l1"])
    assert notification("u", trusted, {"verdict": "opens_later"}, today=date(2031, 1, 15), event=event)
    event.update(kind="closing", due="2027-02-01", notify_from="2026-10-31")
    assert notification("u", trusted, {"verdict": "needs_check"}, today=TODAY, event=event)
    assert not notification("u", trusted, {"verdict": "needs_check"}, today=date(2026, 10, 30), event=event)


def test_smtp_accepted_but_record_failed_is_distinct(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.invalid")
    monkeypatch.setenv("MAIL_FROM", "demo@example.invalid")
    profile = dict(user_id="u", self=dict(email="demo@example.invalid", alert_channel="이메일", alert_categories=["주거"]))
    factory = MagicMock()
    factory.return_value.__enter__.return_value.send_message.return_value = {}
    record = MagicMock(side_effect=RuntimeError("private DB error"))
    with pytest.raises(DeliveryRecordError, match="기록 실패"):
        send_email(profile, dict(id="n", title="안내"), category="주거", record_sent=record, smtp_factory=factory)
    factory.return_value.__enter__.return_value.send_message.assert_called_once()


def test_test_email_does_not_expose_recipient_exception():
    store = MagicMock()
    store.test_email.side_effect = smtplib.SMTPRecipientsRefused({"private@example.invalid": (550, "refused")})
    app = FastAPI()
    app.include_router(create_router(store, lambda: "owner", lambda: "admin"))
    response = TestClient(app).post("/notify/test-email")
    assert response.status_code == 503 and "private" not in response.text
