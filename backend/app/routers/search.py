"""검색 API (docs/api.md §7, 「인증·소유권 계약」). 담당 백엔드2.

로그인 없이 검색할 수 있고, 그때는 개인화 배지가 없다(badge null, 조건표 없는 제도는 no_rule).
로그인했으면 세션의 본인 프로필로만 배지를 단다. 예전 user_id 쿼리는 다른 사람을 고르는 데 쓰지 않는다:
로그인하지 않았으면 401, 본인 프로필이 아니면 403.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request

from backend.search import service
from backend.search.ports import ports

log = logging.getLogger(__name__)


@asynccontextmanager
async def _warm_index(app):
    """앱이 뜰 때 색인을 미리 만든다. 첫 요청에 만들면 덤프 1만 6천 건과 조건표 830개로 첫 검색이 1.4초다(SPEC §11 1초).
    실패해도 앱은 뜨고, 첫 검색 때 다시 만든다."""
    try:
        service.get_index()
    except Exception:
        log.warning("검색 색인을 미리 만들지 못했다. 첫 검색 때 다시 만든다", exc_info=True)
    yield


router = APIRouter(tags=["search"], lifespan=_warm_index)


@router.get("/search")
def search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=100),
    user_id: str | None = None,
    tag: str | None = None,
    subject: str | None = Query(None, pattern="^(self|parent)$"),
    region: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    today: date | None = None,
) -> dict:
    user = ports.session_user(request)
    if user_id is not None:
        if not user:
            raise HTTPException(status_code=401, detail="로그인이 필요합니다")
        if user.get("profile_id") != user_id:
            raise HTTPException(status_code=403, detail="본인 프로필만 쓸 수 있습니다")
    return service.search(q, user and user.get("profile_id"), tag, subject, region, limit, today)
