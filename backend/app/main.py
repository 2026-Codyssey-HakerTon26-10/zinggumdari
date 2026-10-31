import logging
import secrets as _secrets
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import auth, ingest, judge, notices, profiles, search
from backend.data.config import env
from backend.search import ports as search_ports

app = FastAPI(title="징검")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(notices.router)
app.include_router(ingest.router)
app.include_router(search.router)

app.include_router(profiles.router)
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

    def rebuild(self, today):
        from datetime import date

        from backend.app.sources import load_rules
        from backend.engine import judge as judge_fn
        from backend.notify import service as notify_svc

        with _db_errors("알림 재판정"):
            from backend.db import connect
            from backend.db import notifications as db_notif
            from backend.db import profiles as db_profiles

            rules = load_rules()
            with connect() as conn:
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
                                          today=today if isinstance(today, date) else date.today())

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

app.include_router(_notify_router(_NotifyStore(), _require_user, _require_admin))


# ── 통계 라우터 (#14) ─────────────────────────────────────────────────────────

from backend.app.sources import load_rules as _load_rules
from eval.coverage import create_router as _coverage_router

app.include_router(_coverage_router(_load_rules))
