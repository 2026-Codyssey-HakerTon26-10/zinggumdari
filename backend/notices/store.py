"""data/notices/ 안의 원문. 원문 하나에 파일 셋이다.

    {doc_id}.pdf | .html | .txt   원문 그대로
    {doc_id}.meta.json            docs/api.md §8의 머리(출처, 받은 날짜, 해시, 쪽 수)
    {doc_id}.lines.json           줄 목록

손으로 받은 원문(청약홈, 지자체 공고, 손 조건표의 웹 원문)도 같은 명령으로 등록한다.

    uv run --project backend python -m backend.notices.store data/notices/nhuf-newlywed-jeonse.html \\
        --source web --source-url https://nhuf.molit.go.kr/… --title "신혼부부전용 전세자금"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import date
from pathlib import Path

from backend.data import config
from backend.notices.lines import ScannedPdf, html_to_text, kind_of, pdf_lines, text_lines

DOC_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,120}$")   # `:`를 쓰지 않는다(근거 ID의 구분자)
SOURCES = ("applyhome", "lh", "local", "upload", "web", "api")
SUFFIX = {"pdf": ".pdf", "html": ".html", "text": ".txt"}


def valid_doc_id(doc_id: str) -> bool:
    return bool(DOC_ID.match(doc_id or "")) and ".." not in doc_id


def _base(notices_dir: Path | None) -> Path:
    return notices_dir or config.NOTICES_DIR


def _check(doc_id: str) -> None:
    if not valid_doc_id(doc_id):
        raise ValueError(f"doc_id 형식이 아니다(영소문자·숫자·.-_, `:` 금지): {doc_id!r}")


def original_path(doc_id: str, notices_dir: Path | None = None) -> Path | None:
    _check(doc_id)
    for suffix in SUFFIX.values():
        p = _base(notices_dir) / f"{doc_id}{suffix}"
        if p.exists():
            return p
    return None


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def load_meta(doc_id: str, notices_dir: Path | None = None) -> dict | None:
    _check(doc_id)
    return _read(_base(notices_dir) / f"{doc_id}.meta.json")


def load_lines(doc_id: str, notices_dir: Path | None = None) -> list[dict] | None:
    _check(doc_id)
    return _read(_base(notices_dir) / f"{doc_id}.lines.json")


def list_doc_ids(notices_dir: Path | None = None) -> list[str]:
    base = _base(notices_dir)
    return sorted(p.name[: -len(".meta.json")] for p in base.glob("*.meta.json")) if base.is_dir() else []


def paths_of(doc_id: str, notices_dir: Path | None = None) -> list[Path]:
    """이 원문의 파일 전부(원문, 머리, 줄). 지울 때 쓴다."""
    _check(doc_id)
    base = _base(notices_dir)
    return [base / f"{doc_id}{s}" for s in (*SUFFIX.values(), ".meta.json", ".lines.json")]


def save_meta(meta: dict, notices_dir: Path | None = None) -> None:
    _check(meta["doc_id"])
    path = _base(notices_dir) / f"{meta['doc_id']}.meta.json"
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def evidence(ids: list[str], notices_dir: Path | None = None, owner: str | None = None) -> list[dict]:
    """근거 ID 목록 → [{"id", "page", "bbox", "text"}]. 카드의 evidence 모양(api.md §3).

    없는 줄은 page, bbox, text가 None이다. 사용자 업로드(source: upload) 원문은 owner(계정 ID)가 올린 사람과
    같을 때만 줄을 준다. 다르거나 owner가 없으면 없는 줄과 같게 None이다(인증·소유권 계약).
    """
    cache: dict[str, dict] = {}
    out = []
    for eid in ids:
        doc_id, _, line_id = eid.partition(":")
        if doc_id not in cache:
            meta = load_meta(doc_id, notices_dir) if valid_doc_id(doc_id) else None
            allowed = bool(meta) and (meta.get("source") != "upload"
                                      or bool(owner and meta.get("uploaded_by") and meta["uploaded_by"] == owner))
            lines = load_lines(doc_id, notices_dir) if allowed else None
            cache[doc_id] = {ln["id"]: ln for ln in lines or []}
        ln = cache[doc_id].get(line_id)
        out.append({"id": eid, "page": ln and ln["page"], "bbox": ln and ln["bbox"], "text": ln and ln["text"]})
    return out


def register(
    src: Path,
    doc_id: str,
    source: str,
    source_url: str | None,
    title: str,
    fetched_at: str | None = None,
    pblanc_no: str | None = None,
    notices_dir: Path | None = None,
    extra: dict | None = None,
) -> dict:
    """원문 파일을 data/notices/로 옮기고 줄 목록과 머리를 쓴다. 다시 부르면 덮어쓴다.

    extra는 머리에 같이 쓸 값이다(사용자 업로드의 uploaded_by처럼 등록 순간에 있어야 하는 것).
    """
    _check(doc_id)
    if source not in SOURCES:
        raise ValueError(f"source는 {SOURCES} 중 하나다")
    kind = kind_of(src)
    if kind == "hwp":
        raise ValueError("HWP는 받지 않는다")
    base = _base(notices_dir)
    base.mkdir(parents=True, exist_ok=True)
    dest = base / f"{doc_id}{SUFFIX[kind]}"

    pages = None
    if kind == "pdf":
        lines, pages = pdf_lines(src)   # 스캔이면 여기서 ScannedPdf
    else:
        raw = src.read_text(encoding="utf-8", errors="replace")
        lines = text_lines(html_to_text(raw) if kind == "html" else raw)

    if src.resolve() != dest.resolve():
        for old in SUFFIX.values():   # 종류가 바뀌어 다시 등록하면 옛 원문을 지운다
            (base / f"{doc_id}{old}").unlink(missing_ok=True)
        shutil.copyfile(src, dest)
    old = load_meta(doc_id, notices_dir) or {}
    meta = {
        "doc_id": doc_id,
        "title": title,
        "source": source,
        "kind": "pdf" if kind == "pdf" else "text",
        "source_url": source_url,
        "fetched_at": fetched_at or old.get("fetched_at") or date.today().isoformat(),
        "sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
        "pages": len(pages) if pages else None,
        "text_layer": True if kind == "pdf" else None,
        "pblanc_no": pblanc_no,
        "section": old.get("section"),   # 자격 구간은 AI 공고 읽기(compiler)가 채운다
        "rules": old.get("rules", []),
        **(extra or {}),
    }
    (base / f"{doc_id}.lines.json").write_text(json.dumps(lines, ensure_ascii=False, indent=0), encoding="utf-8")
    (base / f"{doc_id}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def register_text(text: str, doc_id: str, source: str, source_url: str | None, title: str,
                  fetched_at: str | None = None, notices_dir: Path | None = None) -> dict:
    """API 산문(행안부 혜택의 지원대상·선정기준 등)을 원문으로 등록한다."""
    _check(doc_id)
    base = _base(notices_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{doc_id}.txt"
    path.write_text(text, encoding="utf-8")
    return register(path, doc_id, source, source_url, title, fetched_at, notices_dir=notices_dir)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="손으로 받은 원문 등록 → 줄 목록")
    ap.add_argument("src", type=Path)
    ap.add_argument("--doc-id", help="없으면 파일 이름")
    ap.add_argument("--source", required=True, choices=SOURCES)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--fetched-at", help="받은 날짜 YYYY-MM-DD, 없으면 오늘")
    ap.add_argument("--pblanc-no")
    a = ap.parse_args(argv)
    try:
        meta = register(a.src, a.doc_id or a.src.stem, a.source, a.source_url, a.title, a.fetched_at, a.pblanc_no)
    except ScannedPdf as exc:
        raise SystemExit(str(exc)) from exc
    lines = load_lines(meta["doc_id"]) or []
    print(json.dumps({**meta, "lines": len(lines), "marked": sum(ln["mark"] for ln in lines)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
