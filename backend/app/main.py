from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.routers import auth, ingest, judge, notices, profiles, search
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


# search.ports 연결: 세션 함수와 프로필 로더를 꽂는다.
# DATABASE_URL이 없는 환경(DB 없이 실행)에서는 None을 돌려줘 미로그인으로 처리.

def _session_user(request):
    try:
        from backend.db import connect
        from backend.db import profiles as db_profiles, sessions
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
