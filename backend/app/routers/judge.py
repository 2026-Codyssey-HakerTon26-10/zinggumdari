"""POST /judge (docs/api.md §3). 스텁: api.md 예시를 그대로 돌려준다."""

import copy
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.routers.profiles import require_dev_api
from backend.engine import judge
from backend.engine.stub_data import EXAMPLE_JUDGE

router = APIRouter(tags=["judge"], dependencies=[Depends(require_dev_api)])   # 로그인 붙기 전까지 개발 모드에서만


class JudgeRequest(BaseModel):
    user_id: str | None = None
    step: str | None = None  # 단계 넘기기: newlywed | child | multi_child


@router.post("/judge")
def post_judge(req: JudgeRequest, today: date | None = None) -> dict:
    result = copy.deepcopy(EXAMPLE_JUDGE)
    if req.user_id:
        result["user_id"] = req.user_id
    result["cards"] = judge({}, [], today)
    return result
