"""행안부(정부24) 제도 대량 추출(SPEC §9, roles.md AI 절). rules/compiled/의 gov24 조건표는 이 모듈로 만들었다.

    python -m backend.compiler.gov24_bulk [--limit N] [--workers 8]
    python -m backend.compiler.gov24_bulk --cache-only      # 저장된 원응답으로만 다시 조립(LLM을 부르지 않는다)

- 대상: 정부24 상세 덤프(data/raw/gov24_serviceDetail)의 지원대상, 선정기준, 신청기한에 생애 단계 말(run.STAGE_WORDS)이
  있는 제도 중 소관기관이 중앙행정기관이거나 서울특별시로 시작하는 것. 손 조건표의 same_as에 걸린 제도는 뺀다.
  2026-11-01 기준 626건, 조건표 800개(Haiku 4.5, 프롬프트 v1).
- 원문: 세 칸을 「[지원대상]」 같은 제목 줄과 함께 텍스트로 이어 data/notices/gov24-<서비스ID 소문자>로 등록한다
  (원문 저장소는 소문자 doc_id만 받는다). 카드의 근거 줄은 이 원문을 연다.
- 조건표 id는 덤프의 서비스 id와 대소문자까지 같게(gov24:WII…) 맞춘다. 검색 문서에 붙으려면 같아야 한다.
- 이미 있는 조건표는 건너뛰어 이어 할 수 있다. --cache-only는 원응답(rules/compiled/_raw/)이 있는 것만 다시 조립하고,
  사람이 검수한 조건표(review.status가 reviewed)는 덮어쓰지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from backend.compiler import llm
from backend.compiler.pipeline import OUT_DIR, RAW_DIR, compile, write_rules
from backend.compiler.run import STAGE_WORDS
from backend.data.load import iter_items
from backend.data.rules import load_rules
from backend.notices import store
from backend.search.corpus import _region_from_org

FIELDS = ("지원대상", "선정기준", "신청기한")
FETCHED_AT = "2026-10-31"   # 정부24 덤프를 받은 날


def text_of(item: dict) -> str:
    return "\n".join(f"[{k}]\n{str(item.get(k) or '').strip()}" for k in FIELDS if str(item.get(k) or "").strip())


def targets(raw_dir: Path | None = None) -> list[tuple[dict, dict]]:
    """(상세 항목, 목록 항목) 중 대량 추출 대상."""
    listing = {it["서비스ID"]: it for it in iter_items("gov24_serviceList", raw_dir)}
    manual_same = {sid for r in load_rules() if r.get("source") == "manual" for sid in r.get("same_as") or []}
    out = []
    for it in iter_items("gov24_serviceDetail", raw_dir):
        meta = listing.get(it["서비스ID"]) or {}
        org_type, org = meta.get("소관기관유형") or "", meta.get("소관기관명") or ""
        if (any(w in text_of(it) for w in STAGE_WORDS) and ("중앙" in org_type or org.startswith("서울특별시"))
                and f"gov24:{it['서비스ID']}" not in manual_same):
            out.append((it, meta))
    return out


def _files(out_dir: Path, sid: str) -> list[Path]:
    return [p for p in (out_dir / f"gov24__{sid}.json", *out_dir.glob(f"gov24__{sid}__*.json")) if p.exists()]


def _reviewed(paths: list[Path]) -> bool:
    return any((json.loads(p.read_text(encoding="utf-8")).get("review") or {}).get("status") == "reviewed" for p in paths)


def one(item: dict, meta: dict, out_dir: Path = OUT_DIR, raw_dir: Path = RAW_DIR) -> int:
    """제도 하나를 등록하고 읽어 조건표를 쓴다. 쓴 조건표 수."""
    sid = item["서비스ID"]
    doc_id = f"gov24-{sid.lower()}"
    registered = store.register_text(text_of(item), doc_id, "api", meta.get("상세조회URL"), item.get("서비스명") or sid,
                                     FETCHED_AT)
    rules = compile(doc_id, store.load_lines(doc_id), "gov24", model="bulk", raw_dir=raw_dir,
                    meta={"title": item.get("서비스명"), "org": meta.get("소관기관명"), "source_url": meta.get("상세조회URL"),
                          "fetched_at": FETCHED_AT, "sha256": registered.get("sha256"),
                          "region": _region_from_org(meta.get("소관기관명"), meta.get("소관기관유형"))})
    for rule in rules:   # compile은 doc_id(소문자)로 id를 만든다. 덤프 서비스 id의 대소문자로 되돌린다
        rule["id"] = f"gov24:{sid}" + rule["id"][len(f"gov24:{sid.lower()}"):]
    for old in _files(out_dir, sid):   # 트랙 수가 바뀌었을 수 있어 옛 파일을 지우고 쓴다
        old.unlink()
    write_rules(rules, out_dir)
    return len(rules)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="정부24 제도 대량 추출")
    ap.add_argument("--limit", type=int, help="이번에 처리할 최대 건수")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--cache-only", action="store_true", help="원응답이 있는 것만 다시 조립한다(LLM을 부르지 않는다)")
    a = ap.parse_args(argv)
    todo = targets()
    if a.cache_only:
        def no_call(*_, **__):
            raise llm.LLMError("--cache-only: 원응답 캐시에 없는 입력이다")
        llm.call_json = no_call
        todo = [(it, m) for it, m in todo if (RAW_DIR / f"gov24-{it['서비스ID'].lower()}.json").exists()
                and not _reviewed(_files(OUT_DIR, it["서비스ID"]))]
    else:
        todo = [(it, m) for it, m in todo if not _files(OUT_DIR, it["서비스ID"])]
    todo = todo[: a.limit] if a.limit else todo
    print(f"대상 {len(todo)}", flush=True)
    t0, ok, failed = time.time(), 0, []
    with ThreadPoolExecutor(max(1, a.workers)) as ex:
        futures = {ex.submit(one, it, m): it["서비스ID"] for it, m in todo}
        for n, fut in enumerate(as_completed(futures), 1):
            try:
                fut.result()
                ok += 1
            except Exception as exc:   # noqa: BLE001  한 건 실패로 나머지를 멈추지 않는다
                failed.append((futures[fut], str(exc)[:200]))
            if n % 50 == 0:
                print(f"{n}/{len(todo)} 성공 {ok} 실패 {len(failed)} {time.time() - t0:.0f}초", flush=True)
    for sid, why in failed:
        print("실패", sid, why, flush=True)
    print(f"끝 성공 {ok} 실패 {len(failed)} {time.time() - t0:.0f}초", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
