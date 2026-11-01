#!/usr/bin/env bash
# DB 준비를 한 번에: PostgreSQL 확인 → .env → DB 만들기 → 마이그레이션 → 연결 확인.
# 새 서버에서 처음 한 번, 그리고 backend/db/migrations/에 새 파일이 생겼을 때 다시 돌린다(이미 한 것은 건너뛴다).
#
#   bash backend/db/setup.sh              # DB 이름 zinggumdari
#   bash backend/db/setup.sh 다른이름
#
# .env는 없을 때만 .env.example로 만들고, 비어 있는 DATABASE_URL만 채운다. 이미 있는 값은 바꾸지 않는다.
# API 키는 채우지 않는다(git으로 옮기지 말고 서버에서 직접 넣는다).
set -euo pipefail
cd "$(dirname "$0")/../.."

DB_NAME="${1:-zinggumdari}"

need() {
    command -v "$1" >/dev/null 2>&1 || { echo "✗ $1 이 없습니다. $2"; exit 1; }
}
need psql "PostgreSQL 14 이상을 설치하세요(macOS: brew install postgresql@16, Ubuntu: sudo apt install postgresql)."
need createdb "PostgreSQL 클라이언트 도구가 PATH에 있어야 합니다."
need uv "https://docs.astral.sh/uv/ 를 보고 설치하세요."
if ! pg_isready -q 2>/dev/null; then
    echo "✗ PostgreSQL이 꺼져 있습니다(macOS: brew services start postgresql@16, Ubuntu: sudo systemctl start postgresql)."
    exit 1
fi
echo "✓ PostgreSQL $(psql --version | awk '{print $3}')"

if [ ! -f .env ]; then
    cp .env.example .env
    echo "✓ .env를 .env.example로 만들었습니다"
fi

url="$(grep -E '^DATABASE_URL=' .env | head -1 | cut -d= -f2- || true)"
if [ -z "$url" ]; then
    url="postgresql://localhost/$DB_NAME"
    tmp="$(mktemp)"
    awk -v u="$url" '/^DATABASE_URL=/ && !done { print "DATABASE_URL=" u; done = 1; next } { print }' .env > "$tmp"
    grep -q '^DATABASE_URL=' "$tmp" || echo "DATABASE_URL=$url" >> "$tmp"
    cat "$tmp" > .env && rm -f "$tmp"
    echo "✓ .env DATABASE_URL=$url"
else
    echo "✓ .env의 DATABASE_URL을 그대로 씁니다"
fi

if psql "$url" -Atc "select 1" >/dev/null 2>&1; then
    echo "✓ DB가 이미 있습니다"
else
    db="${url##*/}"; db="${db%%\?*}"
    case "$url" in
        postgresql://localhost/*|postgres://localhost/*|postgresql:///*)
            createdb "$db" && echo "✓ DB $db 를 만들었습니다" ;;
        *)
            echo "✗ $db 에 접속할 수 없습니다. 주소의 사용자·비밀번호·호스트를 확인하거나 DB를 먼저 만드세요."
            exit 1 ;;
    esac
fi

uv sync --project backend --quiet
uv run --project backend python -m backend.db.migrate
uv run --project backend python - <<'PY'
from backend.db import connect
with connect() as conn:
    names = [r[0] for r in conn.execute("SELECT name FROM schema_migrations ORDER BY name")]
    tables = conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'").fetchone()[0]
print(f"✓ 마이그레이션 {len(names)}개(마지막 {names[-1]}), 테이블 {tables}개")
PY

echo
echo "다음: .env에 API 키를 넣고(README 「클론한 뒤 설치」), API를 띄우세요."
echo "  uv run --project backend uvicorn backend.app.main:app --port 8000"
