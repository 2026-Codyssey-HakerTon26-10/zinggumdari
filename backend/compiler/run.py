"""공고 읽기 CLI(SPEC §9). 한 건은 --src(파일) 또는 --text(원문 텍스트), 행안부 산문 대량 추출은 --bulk.

    python -m backend.compiler.run --src data/notices/x.pdf --doc-id x [--source upload] [--model main|bulk|<모델 ID>]
                                   [--title T] [--org O] [--url U] [--no-cache] [--save-lines] [--out DIR] [--raw-dir DIR]
    python -m backend.compiler.run --bulk data/raw/gov24.jsonl [--stage-filter] [--limit N] [--workers 4]

--src는 로그(api.md §6)를 JSON으로 찍는다. 스캔 PDF의 글자 인식 결과도 <raw-dir>/{doc_id}.ocr.json에 두고
캐시 재생 때 다시 읽는다(로그 llm_calls에 네이토 글자 인식 호출도 센다). --bulk는 조건표 파일이 이미 있는 건을
건너뛰고(이어 하기) 요약을 찍으며, 실패한 건은 <raw-dir>/bulk_failures.jsonl에 남긴다.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from backend.compiler import llm
from backend.compiler.lines import read_document, save_lines, to_lines
from backend.compiler.pipeline import KST, OUT_DIR, RAW_DIR, compile, raw_dir_for, resolve_model, write_rules

# --stage-filter: 생애 단계(청년·신혼·출산·주거·노인) 말이 있는 산문만 남긴다
STAGE_WORDS = ["청년", "신혼", "결혼", "임신", "출산", "자녀", "다자녀", "주거", "전세", "월세", "청약", "주택",
               "노인", "65세", "장기요양", "기초연금", "부모"]


def run_one(src: str | Path, doc_id: str, *, source: str = "upload", model: str | None = None, use_cache: bool = True,
            save: bool = False, out_dir: Path = OUT_DIR, raw_dir: Path | None = None, title: str | None = None,
            org: str | None = None, url: str | None = None) -> tuple[dict, list[Path]]:
    """원문 한 건(Path는 파일, str은 원문 텍스트) → 조건표 파일. (로그, 쓴 파일)을 돌려준다."""
    raw_dir = Path(raw_dir or raw_dir_for(source))
    meta, lines = read_document(doc_id, src, ocr_cache=raw_dir / f"{doc_id}.ocr.json", reuse_ocr=use_cache,
                                llm_ocr=source != "upload")  # 사용자 업로드 스캔은 네이토로 보내지 않는다
    meta |= {"source": source, "title": title, "org": org, "source_url": url,
             "fetched_at": datetime.now(KST).date().isoformat()}
    rules, log = compile(doc_id, lines, source, meta=meta, model=model, use_cache=use_cache, raw_dir=raw_dir,
                         return_log=True)
    if meta.get("ocr_calls") is not None:  # 글자 인식도 로그에. 네이토 호출이면 llm_calls에 더한다
        log |= {k: meta.get(k) for k in ("ocr", "ocr_calls", "ocr_model", "ocr_usage", "unread_pages")}
        log["llm_calls"] += meta["ocr_calls"] if meta["ocr"] == "llm" else 0
    if save:  # 주민번호 검사를 통과한 뒤에만 줄 목록을 남긴다. meta.json은 api.md §8 모양(줄 목록은 lines.json)
        save_lines(doc_id, lines, {**meta, "section": log["section"], "rules": [r["id"] for r in rules],
                                   "lines": None if meta["kind"] == "pdf" else lines})
    return log, write_rules(rules, out_dir)


def _done(out_dir: Path, source: str, doc_id: str) -> bool:
    stem = f"{source}__{doc_id}"
    return (out_dir / f"{stem}.json").exists() or any(out_dir.glob(glob.escape(stem) + "__*.json"))


def run_bulk(path: Path, *, out_dir: Path = OUT_DIR, raw_dir: Path = RAW_DIR, model: str | None = "bulk",
             stage_filter: bool = False, limit: int | None = None, workers: int = 4) -> dict:
    """JSONL(한 줄에 {doc_id, text, source, title?, org?, detail_url?, updated?}) → 조건표 파일. 요약을 돌려준다."""
    out_dir, raw_dir = Path(out_dir), Path(raw_dir)
    items = [json.loads(s) for s in Path(path).read_text(encoding="utf-8").splitlines() if s.strip()]
    if stage_filter:
        items = [it for it in items if any(w in (it.get("text") or "") for w in STAGE_WORDS)]
    todo = [it for it in items if not _done(out_dir, it["source"], it["doc_id"])]
    skipped = len(items) - len(todo)
    todo = todo[:limit] if limit else todo
    model = resolve_model(model)

    def one(it: dict) -> int:
        meta = {"title": it.get("title"), "org": it.get("org"), "source_url": it.get("detail_url"),
                "fetched_at": it.get("updated"), **({"region": it["region"]} if "region" in it else {})}
        rules = compile(it["doc_id"], to_lines(it["doc_id"], it["text"]), it["source"], meta=meta, model=model,
                        raw_dir=raw_dir)
        write_rules(rules, out_dir)
        return len(rules)

    failures, n_rules = [], 0
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futures = {ex.submit(one, it): it for it in todo}
        for n, fut in enumerate(as_completed(futures), 1):
            it = futures[fut]
            try:
                got = fut.result()
                n_rules += got
                status = f"조건표 {got}"
            except Exception as e:  # 한 건이 실패해도 나머지는 계속한다
                failures.append({"doc_id": it.get("doc_id"), "source": it.get("source"), "error": f"{type(e).__name__}: {e}"})
                status = "실패"
            print(f"[{n}/{len(todo)}] {it.get('doc_id')} {status}", file=sys.stderr)
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "bulk_failures.jsonl").write_text("".join(json.dumps(f, ensure_ascii=False) + "\n" for f in failures),
                                                 encoding="utf-8")
    return {"items": len(items), "done": len(todo) - len(failures), "skipped": skipped, "failed": len(failures),
            "rules": n_rules, "model": model}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m backend.compiler.run", description="공고 원문 → AI 조건표")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--src", type=Path, help="원문 파일 경로(PDF, HWP, HWPX, 텍스트, HTML)")
    g.add_argument("--text", help="원문 텍스트")
    g.add_argument("--bulk", type=Path, help="JSONL 파일")
    p.add_argument("--doc-id")
    p.add_argument("--source", default="upload")
    p.add_argument("--title")
    p.add_argument("--org")
    p.add_argument("--url", help="원문 출처(→ detail_url)")
    p.add_argument("--model", help="main | bulk | 모델 ID (기본: --src는 main, --bulk는 bulk)")
    p.add_argument("--no-cache", action="store_true", help="원응답 캐시를 쓰지 않고 다시 부른다")
    p.add_argument("--save-lines", action="store_true", help="data/notices/{doc_id}.lines.json·meta.json도 쓴다")
    p.add_argument("--out", type=Path, default=OUT_DIR)
    p.add_argument("--raw-dir", type=Path, default=None, help="기본: upload는 rules/uploads/_raw, 그 밖은 rules/compiled/_raw")
    p.add_argument("--stage-filter", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--workers", type=int, default=4)
    a = p.parse_args(argv)

    if a.bulk:
        summary = run_bulk(a.bulk, out_dir=a.out, raw_dir=a.raw_dir or RAW_DIR, model=a.model or "bulk",
                           stage_filter=a.stage_filter, limit=a.limit, workers=a.workers)
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    if not a.doc_id:
        p.error("--src·--text에는 --doc-id가 필요합니다")
    try:
        log, paths = run_one(a.src if a.src else a.text, a.doc_id, source=a.source, model=a.model, use_cache=not a.no_cache,
                             save=a.save_lines, out_dir=a.out, raw_dir=a.raw_dir, title=a.title, org=a.org, url=a.url)
    except (ValueError, OSError, llm.LLMError) as e:  # IngestRejected·UnsupportedDocument는 ValueError
        print(json.dumps({"doc_id": a.doc_id, "error": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(log, ensure_ascii=False, indent=1))
    for path in paths:
        print(f"wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
