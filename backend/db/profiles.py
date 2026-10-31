"""프로필 저장·읽기. api.md §2 모양(dict) ↔ 테이블 여러 개. 칸 이름은 팀 시트 DB필드_ 탭 그대로.

동의 확인(민감정보·부모님 칸 지우기)은 라우터가 저장 전에 한다. 여기서는 받은 칸을 그대로 넣는다.
`derived`는 판정 때 계산하는 값이라 저장하지 않는다.
"""

import secrets
from datetime import date
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

# self 칸이 들어가는 테이블. users 칸은 ① 가입, 나머지는 ② 알림 설정.
USERS = ("nickname", "gender", "birth_year", "sido", "sigungu", "marital_status", "marriage_date", "pregnant",
         "due_month", "children_count", "youngest_child_age", "household_size", "employment_status")
ONE_ROW = {
    "user_housing": ("tenure_type", "is_householder", "is_homeless", "deposit", "monthly_rent", "move_in_date",
                     "house_price"),
    "user_income": ("employment_type", "income_self", "income_spouse", "income_household", "dependents_count",
                    "supports_parent_65", "support_start_date"),
    "user_subscription": ("has_account", "joined_date", "payment_count", "deposit_amount"),
    "user_alert": ("alert_categories", "alert_channel", "email"),
}
QUALIFICATION = ("qual_code", "target", "verified")
HISTORY = ("event_type", "event_date")
PARENT = ("relation", "birth_year", "sido", "sigungu", "lives_alone", "lives_with_child", "ltc_grade",
          "disability_registered", "basic_pension", "livelihood_status", "care_wanted")
SELF_FIELDS = set(USERS).union(*ONE_ROW.values(), {"qualifications", "history"})


def create_account(conn: psycopg.Connection, email: str, password_hash: str) -> str:
    """계정 한 줄. 비밀번호는 해시만 받는다. account_id(문자열)를 돌려준다."""
    row = conn.execute("INSERT INTO auth_accounts (email, password_hash) VALUES (%s, %s) RETURNING account_id",
                       (email, password_hash)).fetchone()
    return str(row[0])


def create(conn: psycopg.Connection, account_id: str, profile: dict) -> str:
    """새 프로필을 계정에 연결해 저장하고 무작위 user_id를 돌려준다. 계정당 하나(두 번째는 UniqueViolation)."""
    _check_fields(profile)
    user_id = "U" + secrets.token_hex(8)
    with conn.transaction():
        conn.execute("INSERT INTO users (user_id, account_id) VALUES (%s, %s)", (user_id, account_id))
        _write(conn, {**profile, "user_id": user_id})
    return user_id


def save(conn: psycopg.Connection, profile: dict) -> None:
    """있는 프로필(user_id 필수)을 통째로 다시 쓴다. PATCH는 load → 합치기 → save."""
    _check_fields(profile)
    with conn.transaction():
        if conn.execute("SELECT 1 FROM users WHERE user_id = %s", (profile["user_id"],)).fetchone() is None:
            raise KeyError(profile["user_id"])
        _write(conn, profile)


def load(conn: psycopg.Connection, user_id: str) -> dict | None:
    """api.md §2 모양. 없으면 None. 아직 안 받은 칸은 None, 줄 목록은 []."""
    users = _row(conn, "users", user_id)
    if users is None:
        return None
    me = {k: users[k] for k in USERS}
    for table, cols in ONE_ROW.items():
        row = _row(conn, table, user_id) or {}
        me.update({k: row.get(k) for k in cols})
    me["qualifications"] = _rows(conn, "user_qualifications", QUALIFICATION, user_id)
    me["history"] = _rows(conn, "user_history", HISTORY, user_id)
    return {
        "user_id": user_id,
        "stages_done": users["stages_done"],
        "consents": {"sensitive": users["consent_sensitive"], "parent": users["consent_parent"]},
        "self": {k: _out(v) for k, v in me.items()},
        "parents": _rows(conn, "parents", PARENT, user_id, order="relation"),
    }


def user_id_for(conn: psycopg.Connection, account_id: str) -> str | None:
    row = conn.execute("SELECT user_id FROM users WHERE account_id = %s", (account_id,)).fetchone()
    return row[0] if row else None


def delete(conn: psycopg.Connection, user_id: str) -> None:
    """프로필과 딸린 줄(②③, 부모님, 알림)을 지운다. 계정은 남는다."""
    conn.execute("DELETE FROM users WHERE user_id = %s", (user_id,))


def delete_account(conn: psycopg.Connection, account_id: str) -> None:
    """탈퇴. 계정 하나를 지우면 세션·프로필·알림이 FK로 같이 지워진다(SPEC §14.1).
    업로드 조건표(파일)는 여기서 못 지운다 → 부르는 쪽이 같은 흐름에서 collector.ingest.delete_uploads를 부른다."""
    conn.execute("DELETE FROM auth_accounts WHERE account_id = %s", (account_id,))


def _check_fields(profile: dict) -> None:
    unknown = set(profile.get("self") or {}) - SELF_FIELDS
    for p in profile.get("parents") or []:
        unknown |= set(p) - set(PARENT)
    if unknown:
        raise ValueError(f"모르는 칸: {sorted(unknown)}")


def _write(conn: psycopg.Connection, profile: dict) -> None:
    user_id = profile["user_id"]
    me = profile.get("self") or {}
    consents = profile.get("consents") or {}
    sets = ", ".join(f"{k} = %s" for k in USERS)
    conn.execute(
        f"UPDATE users SET stages_done = %s, consent_sensitive = %s, consent_parent = %s, {sets}, updated_at = now() "
        "WHERE user_id = %s",
        (list(profile.get("stages_done") or []), bool(consents.get("sensitive")), bool(consents.get("parent")),
         *(me.get(k) for k in USERS), user_id))
    for table, cols in ONE_ROW.items():
        conn.execute(f"DELETE FROM {table} WHERE user_id = %s", (user_id,))
        if any(me.get(k) is not None for k in cols):
            _insert(conn, table, {"user_id": user_id, **{k: me.get(k) for k in cols}})
    for table, cols, items in (("user_qualifications", QUALIFICATION, me.get("qualifications")),
                               ("user_history", HISTORY, me.get("history")),
                               ("parents", PARENT, profile.get("parents"))):
        conn.execute(f"DELETE FROM {table} WHERE user_id = %s", (user_id,))
        for item in items or []:
            _insert(conn, table, {"user_id": user_id, **{k: item.get(k) for k in cols}})


def _insert(conn: psycopg.Connection, table: str, row: dict) -> None:
    conn.execute(f"INSERT INTO {table} ({', '.join(row)}) VALUES ({', '.join(['%s'] * len(row))})",
                 tuple(row.values()))


def _row(conn: psycopg.Connection, table: str, user_id: str) -> dict | None:
    cur = conn.cursor(row_factory=dict_row)
    return cur.execute(f"SELECT * FROM {table} WHERE user_id = %s", (user_id,)).fetchone()


def _rows(conn: psycopg.Connection, table: str, cols: tuple, user_id: str, order: str = "id") -> list[dict]:
    cur = conn.cursor(row_factory=dict_row)
    rows = cur.execute(f"SELECT {', '.join(cols)} FROM {table} WHERE user_id = %s ORDER BY {order}", (user_id,))
    return [{k: _out(v) for k, v in r.items()} for r in rows]


def _out(v):
    """DB 값 → JSON 값. 날짜는 ISO 문자열, 금액(numeric)은 정수면 int."""
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    return v
