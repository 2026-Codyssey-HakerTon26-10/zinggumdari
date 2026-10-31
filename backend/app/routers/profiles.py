"""/profiles (docs/api.md §2). 스텁: DB 대신 메모리에 둔다. 서버를 재시작하면 지워진다."""

import copy
import secrets

from fastapi import APIRouter, HTTPException

from backend.engine.stub_data import EXAMPLE_PROFILE

router = APIRouter(prefix="/profiles", tags=["profiles"])

_store: dict[str, dict] = {EXAMPLE_PROFILE["user_id"]: copy.deepcopy(EXAMPLE_PROFILE)}


def _get(user_id: str) -> dict:
    if user_id not in _store:
        raise HTTPException(status_code=404, detail="profile not found")
    return _store[user_id]


@router.post("")
def create_profile(body: dict) -> dict:
    """① 가입 칸 저장. body는 {"self": {...}} 또는 ① 칸 그대로."""
    user_id = "U" + secrets.token_hex(4)
    profile = copy.deepcopy(EXAMPLE_PROFILE)
    profile.update(user_id=user_id, stages_done=["signup"], parents=[])
    profile["self"] = body.get("self", body)
    _store[user_id] = profile
    return {"user_id": user_id}


@router.get("/{user_id}")
def get_profile(user_id: str) -> dict:
    return _get(user_id)


@router.patch("/{user_id}")
def update_profile(user_id: str, body: dict) -> dict:
    """② 알림 설정, ③ 공고별 확인에서 받은 칸을 더한다."""
    profile = _get(user_id)
    profile["self"].update(body.get("self", {}))
    for key in ("parents", "consents", "stages_done"):
        if key in body:
            profile[key] = body[key]
    return profile


@router.delete("/{user_id}", status_code=204)
def delete_profile(user_id: str) -> None:
    _get(user_id)
    del _store[user_id]
