"""인증 API (docs/api.md 「인증·소유권 계약」, SPEC §4.1·§14.1).

POST   /auth/signup  이메일·비밀번호로 계정 생성 → 세션 쿠키 발급
POST   /auth/login   이메일·비밀번호 인증 → 세션 쿠키 발급
POST   /auth/logout  현재 세션 폐기 + 쿠키 삭제
GET    /auth/me      현재 계정 식별 정보 + 연결된 프로필 ID
DELETE /auth/me      계정·세션·프로필·알림·업로드 전체 삭제

쿠키: HttpOnly, SameSite=strict(CSRF 방어).
COOKIE_SECURE=1 환경변수 세팅 시 Secure 플래그 추가(HTTPS 전용).
로그인 실패 메시지는 계정 존재 여부를 드러내지 않는다.
"""

from __future__ import annotations

import re

import psycopg.errors
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from backend.data.config import env
from backend.db import connect
from backend.db import profiles, sessions

_SECURE = env("COOKIE_SECURE") == "1"
_WRONG = "이메일 또는 비밀번호가 올바르지 않습니다"
PASSWORD_MIN, PASSWORD_MAX = 8, 128   # 화면 가입 폼(minLength·maxLength)과 같다
# 로컬@도메인.최상위. 공백·@ 두 개는 거른다. 실제 수신 확인은 하지 않는다(가입은 메일 인증 없음)
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

router = APIRouter(prefix="/auth", tags=["auth"])


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        sessions.COOKIE, token,
        httponly=True, samesite="strict", secure=_SECURE,
        max_age=sessions.SESSION_DAYS * 86400, path="/",
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(sessions.COOKIE, path="/")


def _require_session(request: Request, conn) -> dict:
    """유효한 세션 dict({account_id}) 또는 401."""
    token = request.cookies.get(sessions.COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    sess = sessions.get_session(conn, token)
    if not sess:
        raise HTTPException(status_code=401, detail="세션이 만료됐습니다. 다시 로그인해 주세요")
    return sess


# ── 요청 바디 ─────────────────────────────────────────────────────────────────

class SignupBody(BaseModel):
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


def _check_signup(body: SignupBody) -> None:
    """가입 값 검사. 틀리면 422. FastAPI 기본 422와 달리 입력값(비밀번호)을 응답에 되돌려주지 않는다."""
    if len(body.email) > 254 or not _EMAIL.fullmatch(body.email):
        raise HTTPException(status_code=422, detail="이메일 형식이 아닙니다")
    if not PASSWORD_MIN <= len(body.password) <= PASSWORD_MAX:
        raise HTTPException(status_code=422, detail=f"비밀번호는 {PASSWORD_MIN}~{PASSWORD_MAX}자로 입력해 주세요")


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.post("/signup", status_code=201)
def signup(body: SignupBody, response: Response) -> dict:
    """계정 생성 + 세션 쿠키 발급. 이메일 형식·비밀번호 길이가 틀리면 422(DB에 닿기 전)."""
    _check_signup(body)
    with connect() as conn:
        try:
            account_id = profiles.create_account(conn, body.email, sessions.hash_password(body.password))
        except psycopg.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다")
        token = sessions.create_session(conn, account_id)
    _set_cookie(response, token)
    return {"account_id": account_id}


@router.post("/login")
def login(body: LoginBody, response: Response) -> dict:
    """이메일·비밀번호 인증 후 세션 쿠키 발급."""
    with connect() as conn:
        row = conn.execute(
            "SELECT account_id, password_hash FROM auth_accounts WHERE lower(email) = lower(%s)",
            (body.email,),
        ).fetchone()
        if not row or not sessions.verify_password(body.password, row[1]):
            raise HTTPException(status_code=401, detail=_WRONG)
        account_id = str(row[0])
        token = sessions.create_session(conn, account_id)
    _set_cookie(response, token)
    return {"account_id": account_id}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    """서버 세션 폐기 + 쿠키 삭제."""
    token = request.cookies.get(sessions.COOKIE)
    if token:
        with connect() as conn:
            sessions.revoke_session(conn, token)
    _clear_cookie(response)


@router.get("/me")
def me(request: Request) -> dict:
    """현재 계정 식별 정보. user_id는 프로필이 없으면 null."""
    with connect() as conn:
        sess = _require_session(request, conn)
        account_id = sess["account_id"]
        row = conn.execute(
            "SELECT email FROM auth_accounts WHERE account_id = %s", (account_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="계정이 없습니다")
        user_id = profiles.user_id_for(conn, account_id)
    return {"account_id": account_id, "email": row[0], "user_id": user_id}


@router.delete("/me", status_code=204)
def delete_me(request: Request, response: Response) -> None:
    """계정·세션·프로필·알림 삭제. 업로드 조건표(파일)도 같이 지운다(SPEC §14.1, PR #5)."""
    with connect() as conn:
        sess = _require_session(request, conn)
        account_id = sess["account_id"]
        try:
            from backend.collector.ingest import delete_uploads
        except ImportError:
            delete_uploads = None
        if delete_uploads is not None:
            try:
                delete_uploads(account_id)
            except Exception as exc:
                raise HTTPException(status_code=500, detail="업로드 파일 삭제에 실패했습니다") from exc
        profiles.delete_account(conn, account_id)
    _clear_cookie(response)
