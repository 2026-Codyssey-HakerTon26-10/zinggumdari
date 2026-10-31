"""원문 보기 API (docs/api.md §8, 「인증·소유권 계약」). 담당 백엔드2.

하이라이트는 카드 조건의 근거 줄(evidence의 page, bbox)로만 그린다. 여기서 텍스트를 검색해 위치를 찾지 않는다.
공개 공고 원문은 누구나 본다. 사용자 업로드(source: upload)는 올린 본인 세션에만 보이고, 다른 사람에게는
없는 원문과 같은 404를 준다. 올린 계정(uploaded_by)은 응답에 싣지 않는다.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from backend.notices import store
from backend.search.ports import ports

router = APIRouter(tags=["notices"])


def _visible(meta: dict, request: Request) -> bool:
    if meta.get("source") != "upload":
        return True
    user = ports.session_user(request)
    return bool(user and meta.get("uploaded_by") and user.get("account_id") == meta["uploaded_by"])


def _public(meta: dict) -> dict:
    return {k: v for k, v in meta.items() if k != "uploaded_by"}


def _meta_or_404(doc_id: str, request: Request) -> dict:
    meta = store.load_meta(doc_id) if store.valid_doc_id(doc_id) else None
    if not meta or not _visible(meta, request):
        raise HTTPException(status_code=404, detail="원문 없음")
    return meta


@router.get("/notices")
def list_notices(request: Request) -> list[dict]:
    metas = (store.load_meta(d) for d in store.list_doc_ids())
    return [_public(m) for m in metas if m and _visible(m, request)]


@router.get("/notices/{doc_id}")
def get_notice(doc_id: str, request: Request) -> dict:
    """머리 + 텍스트 원문이면 줄 목록. PDF는 lines가 null이고 /file을 그린다."""
    meta = _meta_or_404(doc_id, request)
    return {**_public(meta), "lines": store.load_lines(doc_id) if meta.get("kind") == "text" else None}


@router.get("/notices/{doc_id}/file")
def get_notice_file(doc_id: str, request: Request) -> FileResponse:
    meta = _meta_or_404(doc_id, request)
    path = store.original_path(doc_id)
    if not path:
        raise HTTPException(status_code=404, detail="원문 파일 없음")
    # 웹 원문 HTML은 남의 페이지라 그대로 그리지 않고 글자로만 준다. HWP·HWPX는 내려받기만 한다
    if meta.get("kind") == "pdf":
        return FileResponse(path, media_type="application/pdf", content_disposition_type="inline")
    if path.suffix in (".hwp", ".hwpx"):
        return FileResponse(path, media_type="application/octet-stream", filename=path.name)
    return FileResponse(path, media_type="text/plain; charset=utf-8", content_disposition_type="inline")
