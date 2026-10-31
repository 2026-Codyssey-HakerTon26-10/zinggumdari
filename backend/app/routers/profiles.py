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


def _shape(body: dict) -> None:
    """구조가 틀린 입력은 저장 전에 422로 거절한다: self는 객체, parents·qualifications는 객체 배열."""
    def bad(what: str):
        raise HTTPException(status_code=422, detail=f"{what} 형식이 아니다")
    me = body.get("self")
    if me is not None:
        if not isinstance(me, dict):
            bad("self는 객체")
        quals = me.get("qualifications")
        if quals is not None and not (isinstance(quals, list) and all(isinstance(q, dict) for q in quals)):
            bad("self.qualifications는 객체 배열")
    parents = body.get("parents")
    if parents is not None and not (isinstance(parents, list) and all(isinstance(p, dict) for p in parents)):
        bad("parents는 객체 배열")
    if "stages_done" in body and not isinstance(body["stages_done"], list):
        bad("stages_done은 배열")


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
    _shape(body)
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


# 시연 프리셋(SPEC §2). 전부 가상 인물이다. 고르면 새 프로필을 하나 만들고 다른 프로필은 건드리지 않는다
PRESETS = {"jiwon": {"label": "지원(1999, 예비부부) + 어머니(1966)", "profile": EXAMPLE_PROFILE}}


@router.get("/presets")
def list_presets() -> list[dict]:
    return [{"id": k, "label": v["label"], "virtual": True} for k, v in PRESETS.items()]


@router.post("/presets/{preset_id}")
def create_from_preset(preset_id: str) -> dict:
    if preset_id not in PRESETS:
        raise HTTPException(status_code=404, detail="preset not found")
    user_id = "U" + secrets.token_hex(4)
    profile = copy.deepcopy(PRESETS[preset_id]["profile"])
    profile.update(user_id=user_id, preset=preset_id)
    _store[user_id] = profile
    return {"user_id": user_id}


@router.get("/{user_id}")
def get_profile(user_id: str) -> dict:
    return _get(user_id)


@router.patch("/{user_id}")
def update_profile(user_id: str, body: dict) -> dict:
    """② 알림 설정, ③ 공고별 확인에서 받은 칸을 더한다.
    복사본에서 검증·동의 정리를 다 끝낸 뒤 한 번에 바꾼다. 실패한 요청은 저장본을 조금도 바꾸지 않는다."""
    _shape(body)
    profile = copy.deepcopy(_get(user_id))
    if "consents" in body:
        profile["consents"].update(_consents(body["consents"], partial=True))
    profile["self"].update(body.get("self") or {})
    if "parents" in body:
        profile["parents"] = list(body["parents"])
    if "stages_done" in body:
        profile["stages_done"] = body["stages_done"]
    _apply_consents(profile)
    _store[user_id] = profile
    return profile


@router.delete("/{user_id}", status_code=204)
def delete_profile(user_id: str) -> None:
    _get(user_id)
    del _store[user_id]
