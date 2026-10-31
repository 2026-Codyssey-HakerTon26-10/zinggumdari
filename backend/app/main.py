import logging
import secrets as _secrets
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import auth, ingest, judge, notices, profiles_db, search
from backend.data.config import env
from backend.search import ports as search_ports

LOCAL_FRONTEND = "http://localhost:3000"


def cors_origins() -> list[str]:
    """쿠키를 실어 API를 부를 수 있는 화면 주소. `.env`의 CORS_ORIGINS(쉼표로 여러 개), 없으면 로컬 화면.
    쿠키를 싣는 요청에 *를 허용하면 아무 사이트나 로그인한 사용자의 세션으로 API를 부를 수 있어 받지 않는다."""
    raw = [o.strip().rstrip("/") for o in (env("CORS_ORIGINS") or "").split(",")]
    origins = [o for o in raw if o]
    if not origins or "*" in origins:
        return [LOCAL_FRONTEND]
    return origins


app = FastAPI(title="징검")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(notices.router)
app.include_router(ingest.router)
app.include_router(search.router)

app.include_router(profiles_db.router)   # 세션 본인 프로필(DB). 메모리 스텁(profiles.py)은 엔진 테스트용으로만 남는다
app.include_router(judge.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ── 세션 헬퍼 ─────────────────────────────────────────────────────────────────
# DATABASE_URL이 없는 환경(DB 없이 실행)에서는 None을 돌려줘 미로그인으로 처리.

def _session_user(request: Request):
    try:
        from backend.db import connect, sessions
        from backend.db import profiles as db_profiles
        token = request.cookies.get(sessions.COOKIE)
        if not token:
            return None
        with connect() as conn:
            sess = sessions.get_session(conn, token)
            if not sess:
                return None
            account_id = sess["account_id"]
            user_id = db_profiles.user_id_for(conn, account_id)
            return {"account_id": account_id, "profile_id": user_id}
    except Exception:
        return None


def _load_profile(profile_id: str):
    try:
        from backend.db import connect
        from backend.db import profiles as db_profiles
        with connect() as conn:
            return db_profiles.load(conn, profile_id)
    except Exception:
        return None


search_ports.connect(session_user=_session_user, load_profile=_load_profile)


# ── FastAPI 의존성 ─────────────────────────────────────────────────────────────

def _require_user(request: Request) -> str:
    """세션 소유 프로필 ID를 반환한다. 미인증이면 401."""
    user = _session_user(request)
    if not user or not user.get("profile_id"):
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    return user["profile_id"]


def _require_admin(request: Request) -> None:
    """ADMIN_TOKEN 헤더를 검증한다. 미인증이면 403."""
    admin_token = env("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=403, detail="서버에 ADMIN_TOKEN이 설정되지 않았습니다")
    token = request.headers.get("X-Admin-Token", "")
    if not _secrets.compare_digest(token.encode(), admin_token.encode()):
        raise HTTPException(status_code=403, detail="관리자만 사용할 수 있습니다")


# ── 알림 라우터 (#13) ─────────────────────────────────────────────────────────

_log = logging.getLogger(__name__)


@contextmanager
def _db_errors(what: str):
    """DB 오류를 빈 결과나 200으로 숨기지 않고 503으로 올린다. 로그에는 오류 종류만 남긴다."""
    try:
        yield
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — 오류를 503으로 바꿔 올림
        _log.error("%s 실패: %s", what, type(exc).__name__)
        raise HTTPException(status_code=503, detail="알림 저장소를 쓸 수 없습니다") from None


class _NotifyStore:
    """알림 DB 저장소. router.create_router에 주입한다."""

    def list(self, user_id: str) -> list:
        with _db_errors("알림 목록"):
            from backend.db import connect
            from backend.db import notifications as db_notif
            with connect() as conn:
                return db_notif.list_for_user(conn, user_id)

    def mark_read(self, user_id: str, notification_id: str):
        with _db_errors("알림 읽음"):
            from backend.db import connect
            from backend.db import notifications as db_notif
            with connect() as conn:
                return db_notif.mark_read(conn, user_id, notification_id)

    def rebuild(self, today, rule_ids=None, account_id=None):
        """account_id가 있으면 그 계정 프로필만, 그 계정이 올린 조건표까지 읽는다(공고 투입 뒤)."""
        from datetime import date

        from backend.app.sources import load_rules
        from backend.engine import judge as judge_fn
        from backend.notify import service as notify_svc

        with _db_errors("알림 재판정"):
            from backend.db import connect
            from backend.db import notifications as db_notif
            from backend.db import profiles as db_profiles

            rules = load_rules(owner=account_id)
            with connect() as conn:
                if account_id:
                    rows = conn.execute("SELECT user_id, account_id FROM users WHERE account_id = %s",
                                        (account_id,)).fetchall()
                else:
                    rows = conn.execute("SELECT user_id, account_id FROM users").fetchall()
                all_profiles = []
                for row in rows:
                    p = db_profiles.load(conn, str(row[0]))
                    if p:
                        p["account_id"] = str(row[1])
                        all_profiles.append(p)

                def save(uid, item):
                    db_notif.upsert(conn, uid, item)

                return notify_svc.rebuild(all_profiles, rules, judge_fn, save,
                                          today=today if isinstance(today, date) else date.today(),
                                          rule_ids=rule_ids, account_id=account_id)

    def test_email(self, user_id: str):
        from backend.notify.email import send_email

        with _db_errors("테스트 메일 준비"):
            from backend.db import connect
            from backend.db import notifications as db_notif
            from backend.db import profiles as db_profiles
            conn_cm = connect()
        with conn_cm as conn:
            profile = db_profiles.load(conn, user_id)
            if not profile:
                raise HTTPException(status_code=404, detail="프로필이 없습니다")
            items = db_notif.list_for_user(conn, user_id)
            if not items:
                return {"sent": False, "reason": "보낼 알림이 없습니다"}
            categories = (profile.get("self") or {}).get("alert_categories") or []
            if not categories:
                return {"sent": False, "reason": "이메일로 받을 알림 분야가 없습니다"}

            def record(uid, nid, at):
                db_notif.record_sent(conn, uid, nid, at)

            try:
                sent = send_email(profile, items[0], category=categories[0], record_sent=record)
            except ValueError:  # SMTP_HOST·MAIL_FROM 미설정
                raise HTTPException(status_code=503, detail="메일 서버 설정이 없습니다") from None
            return {"sent": sent}


# import가 깨지면 서버가 바로 실패해야 한다. 조용히 라우트가 빠지지 않게 try로 감싸지 않는다.
from backend.notify.router import create_router as _notify_router

_notify_store = _NotifyStore()
app.include_router(_notify_router(_notify_store, _require_user, _require_admin))


def _after_ingest(*, rule_ids, today, account_id=None):
    """공고 투입(collector.ingest) 뒤 새 조건표로 알림을 만든다. 업로드는 올린 계정에게만(요청 22).
    알림 저장소가 죽어도 투입은 이미 끝났으니 실패로 알리고 넘어간다."""
    try:
        return _notify_store.rebuild(today, rule_ids=rule_ids, account_id=account_id)
    except HTTPException:
        return {"status": "failed", "notifications": 0, "reason": "알림 저장소를 쓸 수 없습니다"}


from backend.notify import api as _notify_api

_notify_api.connect(_after_ingest)


# ── 통계 라우터 (#14) ─────────────────────────────────────────────────────────

from backend.app.sources import load_rules as _load_rules
from eval.coverage import create_router as _coverage_router

app.include_router(_coverage_router(_load_rules))
