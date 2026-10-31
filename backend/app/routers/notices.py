"""원문 보기 API (docs/api.md §8). 담당 백엔드2.

하이라이트는 카드 조건의 근거 줄(evidence의 page, bbox)로만 그린다. 여기서 텍스트를 검색해 위치를 찾지 않는다.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.notices import store

router = APIRouter(tags=["notices"])


def _meta_or_404(doc_id: str) -> dict:
    meta = store.load_meta(doc_id) if store.valid_doc_id(doc_id) else None
    if not meta:
        raise HTTPException(status_code=404, detail="원문 없음")
    return meta


@router.get("/notices")
def list_notices() -> list[dict]:
    return [m for d in store.list_doc_ids() if (m := store.load_meta(d))]


@router.get("/notices/{doc_id}")
def get_notice(doc_id: str) -> dict:
    """머리 + 텍스트 원문이면 줄 목록. PDF는 lines가 null이고 /file을 그린다."""
    meta = _meta_or_404(doc_id)
    return {**meta, "lines": store.load_lines(doc_id) if meta.get("kind") == "text" else None}


@router.get("/notices/{doc_id}/file")
def get_notice_file(doc_id: str) -> FileResponse:
    meta = _meta_or_404(doc_id)
    path = store.original_path(doc_id)
    if not path:
        raise HTTPException(status_code=404, detail="원문 파일 없음")
    # 웹 원문 HTML은 남의 페이지라 그대로 그리지 않고 글자로만 준다
    media = "application/pdf" if meta.get("kind") == "pdf" else "text/plain; charset=utf-8"
    return FileResponse(path, media_type=media, content_disposition_type="inline")
