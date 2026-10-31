"""공고 투입 API (docs/api.md §6, 「인증·소유권 계약」). 담당 백엔드2.

    POST /ingest   multipart: file(PDF) 또는 url, replay(캐시 재생, 기본 false)

사용자 업로드라 로그인이 필수다. 로그인하지 않았으면(세션이 아직 연결되지 않은 경우 포함) 401.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from backend.collector.ingest import MAX_BYTES, NOTICE, Rejected, ingest
from backend.search.ports import ports

router = APIRouter(tags=["ingest"])


@router.get("/ingest/notice")
def ingest_notice() -> dict:
    """업로드 화면에 띄울 안내문."""
    return {"notice": NOTICE}


@router.post("/ingest")
async def post_ingest(request: Request, file: UploadFile | None = File(None), url: str | None = Form(None),
                      replay: bool = Form(False)) -> dict:
    user = ports.session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    if not file and not url:
        raise HTTPException(status_code=400, detail="PDF 파일이나 URL 하나를 주세요")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "upload.pdf"
        if file:
            data = await file.read(MAX_BYTES + 1)
            name = file.filename or "upload.pdf"
        else:
            if not url.startswith(("https://", "http://")):
                raise HTTPException(status_code=400, detail="http(s) 주소만 받습니다")
            try:
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    res = await client.get(url)
                    res.raise_for_status()
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail=f"URL을 받지 못했습니다: {exc.__class__.__name__}") from exc
            data, name = res.content, url.rsplit("/", 1)[-1] or "upload.pdf"
        path.write_bytes(data)
        try:
            return ingest(path, name, source_url=url, replay=replay, uploaded_by=user.get("account_id"))
        except Rejected as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
