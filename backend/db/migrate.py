"""마이그레이션 적용기. `migrations/NNNN_이름.sql`을 번호 순으로, 아직 안 한 것만 적용한다.

적용한 파일 이름은 schema_migrations에 남는다. 이미 적용한 파일은 고치지 말고 새 번호 파일을 더한다.
실행: uv run --project backend python -m backend.db.migrate
"""

from pathlib import Path

import psycopg

from backend.db import connect

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run(conn: psycopg.Connection) -> list[str]:
    """적용한 파일 이름 목록을 돌려준다. 이미 최신이면 []."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                 "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
    done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path.name in done:
            continue
        with conn.transaction():
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
        applied.append(path.name)
    return applied


if __name__ == "__main__":
    with connect() as c:
        names = run(c)
    print("적용:", ", ".join(names) if names else "없음(이미 최신)")
