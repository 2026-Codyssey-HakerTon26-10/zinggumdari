"""공고 투입 API (docs/api.md §6, 「인증·소유권 계약」). 담당 백엔드2.

    POST /ingest   multipart: file(PDF, HWP, HWPX, 텍스트) 또는 url, replay(캐시 재생, 기본 false)

사용자 업로드라 로그인이 필수다. 로그인하지 않았으면(세션이 아직 연결되지 않은 경우 포함) 401.
본문을 받기 전에 로그인과 크기를 먼저 본다. File()로 받으면 FastAPI가 핸들러보다 먼저 파일 전체를
임시 파일로 받아 두어, 로그인하지 않은 요청도 디스크를 채울 수 있었다.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from backend.collector.ingest import MAX_BYTES, NOTICE, Rejected, fetch_url, ingest
from backend.search.ports import ports

router = APIRouter(tags=["ingest"])
ALLOWED_SUFFIX = (".pdf", ".hwp", ".hwpx", ".txt", ".md")
FORM_SLACK = 1024 * 1024   # 파일 말고 폼 경계·url·replay 칸이 차지하는 여유


@router.get("/ingest/notice")
def ingest_notice() -> dict:
    """업로드 화면에 띄울 안내문."""
    return {"notice": NOTICE}


async def _read_form(request: Request):
    """본문을 상한까지만 받아 폼으로 푼다. 상한을 넘으면 받다가 끊는다(413)."""
    limit = MAX_BYTES + FORM_SLACK
    too_big = HTTPException(status_code=413, detail="파일이 너무 큽니다(30MB까지)")
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > limit:
        raise too_big
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > limit:
            raise too_big

    async def receive() -> dict:
        return {"type": "http.request", "body": bytes(body), "more_body": False}

    return await Request(request.scope, receive).form()


def _flag(value) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "on", "yes")


def _run(account_id: str | None, data: bytes | None, name: str | None, url: str | None, replay: bool) -> dict:
    try:
        if data is None:
            data, name = fetch_url(url), url.rsplit("/", 1)[-1] or "upload.pdf"
        suffix = Path(name).suffix.lower()
        suffix = suffix if suffix in ALLOWED_SUFFIX else ""   # 형식은 줄 만들기가 앞 바이트로 다시 가린다
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"upload{suffix}"
            path.write_bytes(data)
            return ingest(path, name, source_url=url, replay=replay, uploaded_by=account_id)
    except Rejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/ingest")
async def post_ingest(request: Request) -> dict:
    user = await run_in_threadpool(ports.session_user, request)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    form = await _read_form(request)
    file, url = form.get("file"), form.get("url") or None
    if not isinstance(file, UploadFile):
        file = None
    if not file and not url:
        raise HTTPException(status_code=400, detail="PDF 파일이나 URL 하나를 주세요")
    data, name = (await file.read(MAX_BYTES + 1), file.filename or "upload.pdf") if file else (None, None)
    # 읽기와 compile()은 오래 걸리는 동기 작업이라 이벤트 루프를 막지 않게 스레드에서 돌린다
    return await run_in_threadpool(_run, user.get("account_id"), data, name, url, _flag(form.get("replay")))
