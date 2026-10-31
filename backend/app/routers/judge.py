"""POST /judge (docs/api.md §3). 조건표가 아직 없으면 api.md 예시(스텁)를 돌려준다."""

import copy
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app import sources
from backend.app.routers.profiles import _get, require_dev_api
from backend.engine.cards import build_judge
from backend.engine.stub_data import EXAMPLE_JUDGE

router = APIRouter(tags=["judge"], dependencies=[Depends(require_dev_api)])   # 로그인 붙기 전까지 개발 모드에서만


class JudgeRequest(BaseModel):
    user_id: str | None = None
    step: Literal["newlywed", "child", "multi_child"] | None = None  # 단계 넘기기
    rule_id: str | None = None  # 사용자가 연 카드. 그 제도를 막는 빈 칸을 묻는다(SPEC §6)


@router.post("/judge")
def post_judge(req: JudgeRequest, today: date | None = None) -> dict:
    rules = sources.load_rules()
    if not rules:
        result = copy.deepcopy(EXAMPLE_JUDGE)
        if req.user_id:
            result["user_id"] = req.user_id
        return result
    profile = _get(req.user_id or "")
    return build_judge(profile, rules, today, evidence=sources.evidence, step=req.step, focus=req.rule_id)
