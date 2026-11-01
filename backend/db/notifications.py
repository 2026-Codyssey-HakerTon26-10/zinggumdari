"""알림 DB CRUD (api.md §5, notifications 테이블).

저장·읽기는 이 모듈에서만 한다. 알림 생성 로직은 backend/notify/service.py에 있다.
"""

from __future__ import annotations

import json

import psycopg
from psycopg.rows import dict_row


def list_for_user(conn: psycopg.Connection, user_id: str) -> list[dict]:
    """사용자의 알림을 최신순으로 돌려준다."""
    cur = conn.cursor(row_factory=dict_row)
    rows = cur.execute(
        "SELECT id, kind, subject, rule_id, title, created::text, due, extra, read, emailed_at::text "
        "FROM notifications WHERE user_id = %s ORDER BY created DESC, id DESC",
        (user_id,),
    ).fetchall()
    return [_flatten(r) for r in rows]


def mark_read(conn: psycopg.Connection, user_id: str, notification_id: str) -> dict | None:
    """알림을 읽음으로 표시하고 갱신된 알림을 돌려준다. 없으면 None."""
    cur = conn.cursor(row_factory=dict_row)
    row = cur.execute(
        "UPDATE notifications SET read = true "
        "WHERE id = %s AND user_id = %s "
        "RETURNING id, kind, subject, rule_id, title, created::text, due, extra, read, emailed_at::text",
        (notification_id, user_id),
    ).fetchone()
    return _flatten(row) if row else None


def upsert(conn: psycopg.Connection, user_id: str, item: dict) -> None:
    """알림 ID로 upsert. 같은 ID면 title과 extra 칸만 갱신한다(read·emailed_at은 그대로 둔다)."""
    extra = {k: v for k, v in item.items()
             if k not in ("id", "kind", "subject", "rule_id", "title", "created", "due", "read", "emailed_at")}
    conn.execute(
        "INSERT INTO notifications (id, user_id, kind, subject, rule_id, title, created, due, extra) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, extra = notifications.extra || EXCLUDED.extra",
        (item["id"], user_id, item["kind"], item["subject"], item["rule_id"],
         item["title"], item["created"], item.get("due"), json.dumps(extra)),
    )


def record_sent(conn: psycopg.Connection, user_id: str, notification_id: str, sent_at: str) -> None:
    """SMTP 발송 기록. emailed_at은 중복 발송 방지에 쓴다."""
    conn.execute(
        "UPDATE notifications SET emailed_at = %s WHERE id = %s AND user_id = %s",
        (sent_at, notification_id, user_id),
    )


def _flatten(row: dict) -> dict:
    """extra JSONB를 최상위로 병합한다."""
    extra = row.pop("extra", None) or {}
    if isinstance(extra, str):
        extra = json.loads(extra)
    return {**row, **extra}
