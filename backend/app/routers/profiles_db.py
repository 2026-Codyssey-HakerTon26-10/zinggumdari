"""/profiles DB 버전 (api.md §2, 「인증·소유권 계약」).

DATABASE_URL이 있을 때 세션 인증 + PostgreSQL로 동작한다.
미인증은 401, 남의 것이나 없는 것은 404(소유 여부 드러내지 않음).
"""

from __future__ import annotations

import copy
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.engine.derive import derive
from backend.engine.fields import SENSITIVE, is_sensitive_qual
from backend.engine.stub_data import EXAMPLE_PROFILE

router = APIRouter(prefix="/profiles", tags=["profiles"])


# ── 의존성 ────────────────────────────────────────────────────────────────────

def _get_conn():
    from backend.db import connect
    return connect()


def _session_account(request: Request) -> str:
    """세션에서 account_id를 꺼낸다. 미인증이면 401."""
    try:
        from backend.db import sessions
        from backend.db import connect
        token = request.cookies.get(sessions.COOKIE)
        if not token:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다")
        with connect() as conn:
            sess = sessions.get_session(conn, token)
        if not sess:
            raise HTTPException(status_code=401, detail="세션이 만료됐습니다")
        return sess["account_id"]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")


def _own_profile(account_id: str, user_id: str) -> None:
    """user_id가 account_id 소유인지 확인한다. 아니면 404(소유 여부 노출 없음)."""
    try:
        from backend.db import connect
        from backend.db import profiles
        with connect() as conn:
            owner = profiles.user_id_for(conn, account_id)
        if owner != user_id:
            raise HTTPException(status_code=404, detail="profile not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="profile not found")


# ── 공통 유틸 (stub 라우터와 동일 로직) ───────────────────────────────────────

def _out(profile: dict, today: date | None = None) -> dict:
    return {**{k: v for k, v in profile.items() if k != "derived"}, "derived": derive(profile, today)}


def _consents(raw, partial: bool) -> dict:
    if raw is None and not partial:
        return {}
    if not isinstance(raw, dict) or any(k not in ("sensitive", "parent") or type(v) is not bool
                                        for k, v in raw.items()):
        raise HTTPException(status_code=422, detail='consents는 {"sensitive": true|false, "parent": true|false}')
    return raw


def _shape(body: dict) -> None:
    def bad(what: str):
        raise HTTPException(status_code=422, detail=f"{what} 형식이 아니다")
    me = body.get("self")
    if me is not None:
        if not isinstance(me, dict):
            bad("self는 객체")
        quals = me.get("qualifications")
        if quals is not None and not (isinstance(quals, list) and all(isinstance(q, dict) for q in quals)):
            bad("self.qualifications는 객체 배열")
        if quals is not None and any(q.get("has", "Y") not in ("Y", "N") for q in quals):  # 미해당 값도 API에서 명시적으로 검사한다.
            bad("self.qualifications의 has는 Y 또는 N이어야 합니다")  # 불리언·null·오타를 해당함으로 저장하지 않는다.
    parents = body.get("parents")
    if parents is not None and not (isinstance(parents, list) and all(isinstance(p, dict) for p in parents)):
        bad("parents는 객체 배열")
    if "stages_done" in body and not isinstance(body["stages_done"], list):
        bad("stages_done은 배열")


def _apply_consents(profile: dict) -> None:
    consents = profile["consents"]
    if not consents.get("sensitive"):
        profile["self"] = {k: v for k, v in profile["self"].items() if k not in SENSITIVE}
        if "qualifications" in profile["self"]:
            profile["self"]["qualifications"] = [q for q in profile["self"].get("qualifications") or []
                                                 if not is_sensitive_qual((q or {}).get("qual_code"))]
        profile["parents"] = [{k: v for k, v in p.items() if k not in SENSITIVE} for p in profile["parents"]]
    if not consents.get("parent"):
        profile["parents"] = []


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.post("")
def create_profile(body: dict, account_id: str = Depends(_session_account)) -> dict:
    """세션 계정에 프로필을 만든다. 계정당 하나(두 번째는 409)."""
    _shape(body)
    consents_raw = _consents(body.get("consents"), partial=False)
    profile = {
        "stages_done": list(body.get("stages_done") or ["signup"]),
        "consents": {"sensitive": consents_raw.get("sensitive", False), "parent": consents_raw.get("parent", False)},
        "self": dict(body.get("self") or {}),
        "parents": list(body.get("parents") or []),
    }
    _apply_consents(profile)
    try:
        from backend.db import connect
        from backend.db import profiles
        with connect() as conn:
            user_id = profiles.create(conn, account_id, profile)
        return {"user_id": user_id}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))  # #44
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="이미 프로필이 있습니다")
        raise


PRESETS = {"jiwon": {"label": "지원(1999, 예비부부) + 어머니(1966)", "profile": EXAMPLE_PROFILE}}


@router.get("/presets")
def list_presets() -> list[dict]:
    return [{"id": k, "label": v["label"], "virtual": True} for k, v in PRESETS.items()]


@router.post("/presets/{preset_id}")
def create_from_preset(preset_id: str, account_id: str = Depends(_session_account)) -> dict:
    if preset_id not in PRESETS:
        raise HTTPException(status_code=404, detail="preset not found")
    profile = copy.deepcopy(PRESETS[preset_id]["profile"])
    profile.pop("derived", None)
    profile.pop("user_id", None)
    try:
        from backend.db import connect
        from backend.db import profiles
        with connect() as conn:
            user_id = profiles.create(conn, account_id, profile)
        return {"user_id": user_id, "preset": preset_id}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail="이미 프로필이 있습니다")
        raise


@router.get("/{user_id}")
def get_profile(user_id: str, today: date | None = None,
                account_id: str = Depends(_session_account)) -> dict:
    _own_profile(account_id, user_id)
    try:
        from backend.db import connect
        from backend.db import profiles
        with connect() as conn:
            profile = profiles.load(conn, user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="profile not found")
        return _out(profile, today)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="profile not found")


@router.patch("/{user_id}")
def update_profile(user_id: str, body: dict,
                   account_id: str = Depends(_session_account)) -> dict:
    """복사본에서 검증·동의 정리 후 한 번에 저장. 실패해도 원본 안 바뀜."""
    _own_profile(account_id, user_id)
    _shape(body)

    def change(profile: dict) -> None:
        if "consents" in body:
            profile["consents"].update(_consents(body["consents"], partial=True))
        profile["self"].update(body.get("self") or {})
        if "parents" in body:
            profile["parents"] = list(body["parents"])
        if "stages_done" in body:
            profile["stages_done"] = body["stages_done"]
        _apply_consents(profile)

    try:
        from backend.db import connect
        from backend.db import profiles
        with connect() as conn:
            updated = profiles.update(conn, user_id, change)
        if not updated:
            raise HTTPException(status_code=404, detail="profile not found")
        return _out(updated)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))  # #44


@router.delete("/{user_id}", status_code=204)
def delete_profile(user_id: str, account_id: str = Depends(_session_account)) -> None:
    _own_profile(account_id, user_id)
    try:
        from backend.db import connect
        from backend.db import profiles
        with connect() as conn:
            profiles.delete(conn, user_id)
    except Exception:
        raise HTTPException(status_code=404, detail="profile not found")
