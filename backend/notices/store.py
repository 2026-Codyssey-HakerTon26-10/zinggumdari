"""data/notices/ 안의 원문. 원문 하나에 파일 셋이다.

    {doc_id}.pdf | .hwp | .hwpx | .html | .txt   원문 그대로
    {doc_id}.meta.json            docs/api.md §8의 머리(출처, 받은 날짜, 해시, 쪽 수)
    {doc_id}.lines.json           줄 목록

손으로 받은 원문(청약홈, 지자체 공고, 손 조건표의 웹 원문)도 같은 명령으로 등록한다.

    uv run --project backend python -m backend.notices.store data/notices/nhuf-newlywed-jeonse.html \\
        --source web --source-url https://nhuf.molit.go.kr/… --title "신혼부부전용 전세자금"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
from datetime import date
from pathlib import Path

from backend.compiler.lines import read_document, save_lines
from backend.compiler.pipeline import raw_dir_for
from backend.compiler.readers import UnsupportedDocument
from backend.data import config

DOC_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,120}$")   # `:`를 쓰지 않는다(근거 ID의 구분자)
SOURCES = ("applyhome", "lh", "local", "upload", "web", "api")
SUFFIX = {"pdf": ".pdf", "hwp": ".hwp", "hwpx": ".hwpx", "html": ".html", "text": ".txt"}


class ScannedPdf(ValueError):
    """글자를 한 줄도 읽지 못한 PDF(이미지 스캔인데 글자 인식도 못 한 것). 받지 않는다."""


class Unsupported(ValueError):
    """읽을 수 없는 형식(암호·배포용 HWP, HWP 3.x, 그 밖의 형식). 메시지를 화면에 그대로 보여준다."""


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


def _tmp_for(path: Path) -> Path:
    """같은 폴더의 임시 이름. 점으로 시작하고 .tmp로 끝나 list_doc_ids의 *.meta.json에 걸리지 않는다."""
    return path.with_name(f".{path.name}.{secrets.token_hex(4)}.tmp")


def _write_atomic(path: Path, text: str) -> None:
    """임시 파일에 다 쓴 뒤 이름만 바꾼다. 쓰다 죽거나 두 요청이 겹쳐도 반쯤 쓴 머리가 남지 않는다
    (반쯤 쓴 JSON은 _read에서 깨져 그 원문이 통째로 사라져 보인다)."""
    tmp = _tmp_for(path)
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def save_meta(meta: dict, notices_dir: Path | None = None) -> None:
    _check(meta["doc_id"])
    path = _base(notices_dir) / f"{meta['doc_id']}.meta.json"
    _write_atomic(path, json.dumps(meta, ensure_ascii=False, indent=2))


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

    줄 만들기는 AI 공고 읽기와 같은 backend.compiler.lines.read_document다(줄 ID가 어디서 만들어도 같게).
    스캔한 쪽은 글자 인식으로 읽고, 사용자 업로드는 네이토로 보내지 않는다(tesseract만). 그래도 못 읽은 쪽은
    머리의 unread_pages에 남고 compile(meta=)가 그 쪽에 확인 필요 조건을 붙인다.
    extra는 머리에 같이 쓸 값이다(사용자 업로드의 uploaded_by처럼 등록 순간에 있어야 하는 것).
    """
    _check(doc_id)
    if source not in SOURCES:
        raise ValueError(f"source는 {SOURCES} 중 하나다")
    base = _base(notices_dir)
    base.mkdir(parents=True, exist_ok=True)
    try:
        doc, lines = read_document(doc_id, Path(src), ocr_cache=raw_dir_for(source) / f"{doc_id}.ocr.json",
                                   llm_ocr=source != "upload")
    except UnsupportedDocument as exc:
        raise Unsupported(str(exc)) from exc
    kind = doc["kind"]
    if kind == "pdf" and not lines:
        raise ScannedPdf("글자를 읽을 수 없는 PDF(이미지 스캔)는 받지 않는다")
    dest = base / f"{doc_id}{SUFFIX.get(kind, '.txt')}"
    if Path(src).resolve() != dest.resolve():
        for old in SUFFIX.values():   # 종류가 바뀌어 다시 등록하면 옛 원문을 지운다
            (base / f"{doc_id}{old}").unlink(missing_ok=True)
        tmp = _tmp_for(dest)
        try:
            shutil.copyfile(src, tmp)
            os.replace(tmp, dest)
        finally:
            tmp.unlink(missing_ok=True)
    old = load_meta(doc_id, notices_dir) or {}
    meta = {
        "doc_id": doc_id,
        "title": title,
        "source": source,
        "kind": "pdf" if kind == "pdf" else "text",   # api.md §8. HWP·HWPX·HTML도 줄 목록을 그리는 text다
        "source_url": source_url,
        "fetched_at": fetched_at or old.get("fetched_at") or date.today().isoformat(),
        "sha256": doc["sha256"],
        "pages": doc["pages"] if kind == "pdf" else None,
        "text_layer": doc["text_layer"] if kind == "pdf" else None,
        "ocr": doc.get("ocr"),
        "unread_pages": doc.get("unread_pages") or [],
        "pblanc_no": pblanc_no,
        "section": old.get("section"),   # 자격 구간은 AI 공고 읽기(compiler)가 채운다
        "rules": old.get("rules", []),
        **(extra or {}),
    }
    save_lines(doc_id, lines, None, out_dir=base)
    _write_atomic(base / f"{doc_id}.meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def register_text(text: str, doc_id: str, source: str, source_url: str | None, title: str,
                  fetched_at: str | None = None, notices_dir: Path | None = None) -> dict:
    """API 산문(행안부 혜택의 지원대상·선정기준 등)을 원문으로 등록한다."""
    _check(doc_id)
    base = _base(notices_dir)
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{doc_id}.txt"
    _write_atomic(path, text)
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
    except (ScannedPdf, Unsupported) as exc:
        raise SystemExit(str(exc)) from exc
    lines = load_lines(meta["doc_id"]) or []
    print(json.dumps({**meta, "lines": len(lines), "marked": sum(ln["mark"] for ln in lines)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
