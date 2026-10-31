"""/profiles (docs/api.md §2). 스텁: DB 대신 메모리에 둔다. 서버를 재시작하면 지워진다.

로그인·소유권 확인이 붙기 전까지는 개발 모드(DEV_STUB_API=1)에서만 열린다. 기본은 닫힘(404).
"""

import copy
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException

from backend.engine.fields import SENSITIVE, is_sensitive_qual
from backend.engine.stub_data import EXAMPLE_PROFILE


def require_dev_api() -> None:
    if os.environ.get("DEV_STUB_API", "").lower() not in ("1", "true", "yes", "on"):
        raise HTTPException(status_code=404)


router = APIRouter(prefix="/profiles", tags=["profiles"], dependencies=[Depends(require_dev_api)])

_store: dict[str, dict] = {EXAMPLE_PROFILE["user_id"]: copy.deepcopy(EXAMPLE_PROFILE)}


def _get(user_id: str) -> dict:
    if user_id not in _store:
        raise HTTPException(status_code=404, detail="profile not found")
    return _store[user_id]


def _consents(raw, partial: bool) -> dict:
    """동의는 JSON true/false만 받는다. "false" 같은 문자열을 True로 바꾸지 않는다."""
    if raw is None and not partial:
        return {}
    if not isinstance(raw, dict) or any(k not in ("sensitive", "parent") or type(v) is not bool for k, v in raw.items()):
        raise HTTPException(status_code=422, detail="consents는 {\"sensitive\": true|false, \"parent\": true|false}")
    return raw


def _apply_consents(profile: dict) -> None:
    """동의가 없는 정보는 저장하지 않는다(SPEC §4.4). 동의를 거두면 이미 있던 값도 지운다."""
    consents = profile["consents"]
    if not consents.get("sensitive"):
        profile["self"] = {k: v for k, v in profile["self"].items() if k not in SENSITIVE}
        if "qualifications" in profile["self"]:
            profile["self"]["qualifications"] = [q for q in profile["self"]["qualifications"] or []
                                                 if not is_sensitive_qual((q or {}).get("qual_code"))]
        profile["parents"] = [{k: v for k, v in p.items() if k not in SENSITIVE} for p in profile["parents"]]
    if not consents.get("parent"):
        profile["parents"] = []


@router.post("")
def create_profile(body: dict) -> dict:
    """① 가입 칸 저장. body: {"self": {...}, "consents"?: {...}, "parents"?: [...]}. 동의는 기본 False."""
    user_id = "U" + secrets.token_hex(4)
    consents = _consents(body.get("consents"), partial=False)
    profile = {
        "user_id": user_id,
        "stages_done": ["signup"],
        "consents": {"sensitive": consents.get("sensitive", False), "parent": consents.get("parent", False)},
        "self": dict(body.get("self") or {}),
        "parents": list(body.get("parents") or []),
    }
    _apply_consents(profile)
    _store[user_id] = profile
    return {"user_id": user_id}


@router.get("/{user_id}")
def get_profile(user_id: str) -> dict:
    return _get(user_id)


@router.patch("/{user_id}")
def update_profile(user_id: str, body: dict) -> dict:
    """② 알림 설정, ③ 공고별 확인에서 받은 칸을 더한다."""
    profile = _get(user_id)
    if "consents" in body:
        profile["consents"].update(_consents(body["consents"], partial=True))
    profile["self"].update(body.get("self") or {})
    if "parents" in body:
        profile["parents"] = list(body["parents"])
    if "stages_done" in body:
        profile["stages_done"] = body["stages_done"]
    _apply_consents(profile)
    return profile


@router.delete("/{user_id}", status_code=204)
def delete_profile(user_id: str) -> None:
    _get(user_id)
    del _store[user_id]
