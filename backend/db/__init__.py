"""PostgreSQL 연결 (SPEC §14.1). 연결 정보는 .env의 DATABASE_URL에서만 읽는다."""

import psycopg

from backend.data.config import env


def connect(url: str | None = None) -> psycopg.Connection:
    """autocommit 연결. 여러 문장을 한 번에 묶을 때는 `with conn.transaction():`."""
    url = url or env("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL이 없습니다. .env에 넣어 주세요(.env.example 참고)")
    return psycopg.connect(url, autocommit=True)
