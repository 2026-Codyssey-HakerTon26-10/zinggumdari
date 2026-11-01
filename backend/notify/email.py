"""표준 라이브러리 SMTP: 명시적으로 선택한 분야만 이메일 발송."""

from datetime import datetime, timezone
from email.message import EmailMessage
import os
import smtplib
import ssl


class DeliveryRecordError(RuntimeError):
    """SMTP는 수락했지만 기록이 미확정인 상태. 자동 재발송하지 않는다."""


def send_email(profile, notification, *, category, record_sent, smtp_factory=smtplib.SMTP):
    settings = profile["self"]
    if (settings.get("alert_channel") != "이메일"
            or category not in settings.get("alert_categories", [])
            or not settings.get("email") or notification.get("emailed_at")):
        return False
    host, sender = os.environ.get("SMTP_HOST"), os.environ.get("MAIL_FROM")
    if not host or not sender:
        raise ValueError("SMTP_HOST와 MAIL_FROM이 필요합니다")
    message = EmailMessage()
    message["From"], message["To"] = sender, settings["email"]
    message["Subject"] = "[징검] " + notification["title"]
    message.set_content(notification["title"] + "\n참고용 모의 판정, 실제 자격은 접수 기관 심사로 결정")
    with smtp_factory(host, int(os.environ.get("SMTP_PORT", "587")), timeout=15) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if os.environ.get("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    try:
        record_sent(profile["user_id"], notification["id"], datetime.now(timezone.utc).isoformat())
    except Exception:
        raise DeliveryRecordError("SMTP 수락 후 기록 실패: 발송 상태 확인이 필요합니다") from None
    return True


def send_report(to, subject, text, html, *, smtp_factory=smtplib.SMTP):
    """생애주기 리포트 한 통(텍스트 + HTML). 수신 동의 확인은 부르는 쪽이 한다."""
    host, sender = os.environ.get("SMTP_HOST"), os.environ.get("MAIL_FROM")
    if not host or not sender:
        raise ValueError("SMTP_HOST와 MAIL_FROM이 필요합니다")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = sender, to, subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    with smtp_factory(host, int(os.environ.get("SMTP_PORT", "587")), timeout=15) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        if os.environ.get("SMTP_USER"):
            smtp.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
    return True
