"""세션 발급·조회·폐기와 비밀번호 해시 (SPEC §4.1, api.md 「인증·소유권 계약」).

비밀번호는 scrypt(파이썬 내장)로 해시. 세션 토큰은 원본을 SHA-256으로 해시해서 저장.
쿠키 이름: COOKIE. 유효 기간: SESSION_DAYS.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import psycopg

COOKIE = "session"
SESSION_DAYS = 30
_SCRYPT_N = 2**14    # CPU/메모리 비용. 프로덕션에서 2**16 이상 권장
_SCRYPT_R = 8
_SCRYPT_P = 1


# ── 비밀번호 ──────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """scrypt 해시. 솔트 포함 `salt_hex:dk_hex` 형식."""
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return salt.hex() + ":" + dk.hex()


def verify_password(password: str, stored: str) -> bool:
    """타이밍 공격을 막는 상수시간 비교."""
    try:
        salt_hex, dk_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
        return secrets.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False


# ── 세션 ──────────────────────────────────────────────────────────────────────

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(conn: psycopg.Connection, account_id: str) -> str:
    """새 세션 토큰을 만들고 해시를 DB에 저장한다. 쿠키에 넣을 원본 토큰을 돌려준다."""
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    conn.execute(
        "INSERT INTO auth_sessions (account_id, token_hash, expires_at) VALUES (%s, %s, %s)",
        (account_id, _token_hash(token), expires),
    )
    return token


def get_session(conn: psycopg.Connection, token: str) -> dict | None:
    """유효한 세션 → {account_id: str}. 없거나 만료·폐기됐으면 None."""
    row = conn.execute(
        "SELECT account_id FROM auth_sessions "
        "WHERE token_hash = %s AND revoked_at IS NULL AND expires_at > now()",
        (_token_hash(token),),
    ).fetchone()
    return {"account_id": str(row[0])} if row else None


def revoke_session(conn: psycopg.Connection, token: str) -> None:
    """로그아웃: 해당 토큰의 세션을 폐기한다."""
    conn.execute(
        "UPDATE auth_sessions SET revoked_at = now() WHERE token_hash = %s",
        (_token_hash(token),),
    )
