"""POST /judge (docs/api.md §3). 세션의 본인 프로필(DB)로 판정한다.

미인증 401, 프로필이 없으면 404, body의 user_id가 본인 것이 아니면 403(「인증·소유권 계약」).
사용자 업로드 조건표와 근거 줄은 세션 계정(owner)의 것만 읽는다.
조건표가 아직 없으면 api.md 예시(스텁)를 돌려준다.
"""

import copy
from datetime import date
from functools import partial
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app import sources
from backend.app.routers.profiles_db import _session_account
from backend.engine.cards import build_judge
from backend.engine.stub_data import EXAMPLE_JUDGE

router = APIRouter(tags=["judge"])


def own_profile(account_id: Annotated[str, Depends(_session_account)]) -> dict:
    """세션 계정과 그 프로필. 프로필이 없으면 404. 테스트는 이 의존성을 바꿔 끼운다."""
    from backend.db import connect, profiles

    with connect() as conn:
        user_id = profiles.user_id_for(conn, account_id)
        profile = profiles.load(conn, user_id) if user_id else None
    if not profile:
        raise HTTPException(status_code=404, detail="profile not found")
    return {"account_id": account_id, "profile": profile}


class JudgeRequest(BaseModel):
    user_id: str | None = None   # 보내지 않아도 된다. 보내면 세션 프로필과 같아야 한다
    step: Literal["newlywed", "child", "multi_child"] | None = None  # 단계 넘기기
    rule_id: str | None = None  # 사용자가 연 카드. 그 제도를 막는 빈 칸을 묻는다(SPEC §6)


@router.post("/judge")
def post_judge(req: JudgeRequest, own: Annotated[dict, Depends(own_profile)], today: date | None = None) -> dict:
    profile, owner = own["profile"], own["account_id"]
    if req.user_id is not None and req.user_id != profile["user_id"]:
        raise HTTPException(status_code=403, detail="본인 프로필만 판정할 수 있습니다")
    rules = sources.load_rules(owner=owner)
    if not rules:
        result = copy.deepcopy(EXAMPLE_JUDGE)
        result["user_id"] = profile["user_id"]
        return result
    from backend.engine import similar   # numpy·가상 인구는 판정할 때만 읽는다

    return build_judge(profile, rules, today, evidence=partial(sources.evidence, owner=owner),
                       step=req.step, focus=req.rule_id,
                       similar=lambda p, verdicts: similar.similar_for(p, verdicts, rules, today=today))
