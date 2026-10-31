"""LH 공고문 PDF 받기. 목록 덤프 → 상세 덤프 → 첨부 중 PDF만(HWP 제외) → 줄 목록.

    uv run --project backend python -m backend.data.dump --source lh
    uv run --project backend python -m backend.notices.fetch --limit 10

공공데이터 API는 다시 부르지 않고 덤프만 읽는다. 첨부 파일 서버만 부른다.
"""

from __future__ import annotations

import argparse
import re
import tempfile
from datetime import date
from pathlib import Path

import httpx

from backend.data.load import iter_details, iter_items
from backend.notices import store
from backend.notices.lh import find_attachments
from backend.notices.store import ScannedPdf

UA = {"User-Agent": "Mozilla/5.0 (zinggum notice fetch)"}


SKIP_TYPES = ("토지", "상가")                      # 주택 공고만 받는다
FIRST = ("신혼", "청년", "신생아", "행복주택", "다자녀")   # 시연 단계와 맞는 공고를 먼저


def is_notice_pdf(att: dict) -> bool:
    """공고문 PDF만. 구분이 공고문(PDF), 정정공고문(PDF)이고 파일도 PDF."""
    return att["kind"] == "pdf" and "공고문" in (att.get("label") or "") and "hwp" not in (att.get("label") or "").lower()


def plan(limit: int | None = None) -> list[dict]:
    """받을 PDF 목록. 공고 하나에 공고문 PDF가 여럿이면(정정 공고) -2, -3을 붙인다."""
    items = {it.get("PAN_ID"): it for it in iter_items("lh_list")}
    jobs = []
    for pan_id, detail in iter_details("lh_detail"):
        item = items.get(pan_id, {})
        if any(t in (item.get("UPP_AIS_TP_NM") or "") for t in SKIP_TYPES):
            continue
        base = "lh-" + re.sub(r"[^a-z0-9]", "", str(pan_id).lower())
        for n, att in enumerate([a for a in find_attachments(detail) if is_notice_pdf(a)], 1):
            jobs.append({"doc_id": base + (f"-{n}" if n > 1 else ""), "url": att["url"],
                         "title": item.get("PAN_NM") or att.get("name") or str(pan_id),
                         "open": item.get("PAN_SS") in ("공고중", "접수중", "정정공고중")})
    jobs.sort(key=lambda j: (not any(w in j["title"] for w in FIRST), not j["open"]))
    return jobs[:limit] if limit else jobs


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="LH 공고문 PDF 받기")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--force", action="store_true", help="이미 있어도 다시 받는다")
    a = ap.parse_args(argv)

    jobs = plan(a.limit)
    if not jobs:
        print("받을 PDF가 없다. dump --source lh 로 목록과 상세를 먼저 받는다")
        return
    with httpx.Client(timeout=60, follow_redirects=True, headers=UA) as client, tempfile.TemporaryDirectory() as tmp:
        for job in jobs:
            if store.load_meta(job["doc_id"]) and not a.force:
                print("있음  ", job["doc_id"])
                continue
            dest = Path(tmp) / f"{job['doc_id']}.pdf"
            try:
                res = client.get(job["url"])
                res.raise_for_status()
                if res.content[:5] != b"%PDF-":
                    raise ValueError(f"PDF가 아닌 응답({res.headers.get('content-type')})")
                dest.write_bytes(res.content)
                meta = store.register(dest, job["doc_id"], "lh", job["url"], job["title"], date.today().isoformat())
                print("받음  ", job["doc_id"], f"{meta['pages']}쪽", job["title"][:40])
            except ScannedPdf:
                print("건너뜀", job["doc_id"], "이미지 스캔 PDF")
            except Exception as exc:   # 한 건 실패로 전체를 멈추지 않는다
                print("실패  ", job["doc_id"], exc)


if __name__ == "__main__":
    main()
