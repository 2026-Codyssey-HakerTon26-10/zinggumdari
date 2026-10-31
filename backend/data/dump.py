"""공공데이터 덤프. 응답 원문을 data/raw/<소스>/에 저장한다. 시연 중에는 부르지 않는다.

    uv run --project backend python -m backend.data.dump --source gov24
    uv run --project backend python -m backend.data.dump --source lh --detail-limit 30
    uv run --project backend python -m backend.data.dump --source all

키가 없거나 승인 전이면 그 소스는 건너뛰고 끝에 모아서 알려준다.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

from backend.data import config
from backend.data.load import iter_items
from backend.data.sources import (
    DETAIL_SOURCES,
    GROUPS,
    LIST_SOURCES,
    DetailSource,
    ListSource,
    api_error,
    parse,
)


class Skip(Exception):
    """이 소스는 건너뛴다(키 없음, 승인 전, 응답 오류)."""


def _key(env_name: str) -> str:
    key = config.data_go_kr_key() if env_name == "DATA_GO_KR_KEY" else config.env(env_name)
    if not key:
        raise Skip(f"{env_name} 없음")
    return key


def _get(client: httpx.Client, url: str, params: dict, fmt: str) -> tuple[str, object]:
    for attempt in range(3):
        try:
            res = client.get(url, params=params)
            break
        except httpx.TransportError as exc:
            if attempt == 2:
                raise Skip(f"연결 실패: {exc.__class__.__name__}") from exc
            time.sleep(1 + attempt)
    text = res.text
    try:
        parsed = parse(fmt, text)
    except Exception as exc:
        raise Skip(f"HTTP {res.status_code}, 응답을 {fmt}로 읽지 못함: {text[:120]!r}") from exc
    err = api_error(parsed)
    if err or res.status_code >= 400:
        hint = " (활용신청 승인 전이거나 키가 다를 수 있다)" if "KEY" in (err or "") or res.status_code in (401, 403) else ""
        raise Skip(f"HTTP {res.status_code} {err or ''}{hint}".strip())
    return text, parsed


def _write_meta(folder: Path, meta: dict) -> None:
    (folder / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def dump_list(src: ListSource, client: httpx.Client, max_pages: int | None) -> dict:
    key = _key(src.key_env)
    final = config.RAW_DIR / src.name
    tmp = config.RAW_DIR / f".{src.name}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)

    page, count, total = 1, 0, None
    try:
        while True:
            params = {src.key_param: key, src.page_param: page, src.size_param: src.page_size, **src.extra}
            text, parsed = _get(client, src.url, params, src.fmt)
            items = src.items(parsed)
            total = total or src.total(parsed)
            (tmp / f"page-{page:04d}.{src.fmt}").write_text(text, encoding="utf-8")
            count += len(items)
            done = len(items) < src.page_size or (total is not None and count >= total)
            if done or (max_pages and page >= max_pages):
                break
            page += 1
    except Skip:
        shutil.rmtree(tmp, ignore_errors=True)
        raise

    meta = {
        "source": src.name, "dataset": src.dataset, "endpoint": src.url,
        "params": {k: v for k, v in src.extra.items()}, "page_size": src.page_size,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "pages": page, "items": count, "total": total,
    }
    _write_meta(tmp, meta)
    # 새 덤프가 다 받아진 뒤에만 이전 덤프를 바꾼다.
    shutil.rmtree(final, ignore_errors=True)
    tmp.rename(final)
    return meta


def dump_details(src: DetailSource, client: httpx.Client, limit: int | None) -> dict:
    key = _key(src.key_env)
    parents = list(iter_items(src.parent))
    if not parents:
        raise Skip(f"{src.parent} 덤프가 없다. 목록을 먼저 받는다")
    folder = config.RAW_DIR / src.name
    folder.mkdir(parents=True, exist_ok=True)
    limit = src.default_limit if limit is None else limit

    fetched = skipped = 0
    for item in parents:
        if fetched >= limit:
            break
        item_id = src.item_id(item)
        if not item_id:
            continue
        path = folder / f"{item_id}.{src.fmt}"
        if path.exists():   # 하루 호출 한도가 있어 받은 것은 다시 받지 않는다
            skipped += 1
            continue
        text, _ = _get(client, src.url, {src.key_param: key, **src.params(item)}, src.fmt)
        path.write_text(text, encoding="utf-8")
        fetched += 1

    meta = {
        "source": src.name, "dataset": src.dataset, "endpoint": src.url, "parent": src.parent,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "fetched_now": fetched, "already_had": skipped,
        "files": len([p for p in folder.iterdir() if p.suffix in (".json", ".xml")]),
    }
    _write_meta(folder, meta)
    return meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="공공데이터 덤프")
    ap.add_argument("--source", required=True, help=f"묶음({', '.join(GROUPS)}) 또는 개별 이름")
    ap.add_argument("--max-pages", type=int, default=None, help="목록 API 최대 페이지")
    ap.add_argument("--detail-limit", type=int, default=None, help="상세 API를 이번에 새로 부를 최대 건수")
    args = ap.parse_args(argv)

    names = GROUPS.get(args.source, [args.source])
    unknown = [n for n in names if n not in LIST_SOURCES and n not in DETAIL_SOURCES]
    if unknown:
        ap.error(f"모르는 소스: {', '.join(unknown)}")

    done, skipped = [], []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for name in names:
            try:
                if name in LIST_SOURCES:
                    meta = dump_list(LIST_SOURCES[name], client, args.max_pages)
                    done.append(f"{name}: {meta['items']}건 / 전체 {meta['total']} ({meta['pages']}쪽)")
                else:
                    meta = dump_details(DETAIL_SOURCES[name], client, args.detail_limit)
                    done.append(f"{name}: 새로 {meta['fetched_now']}건, 있던 것 {meta['already_had']}건")
            except Skip as reason:
                skipped.append(f"{name}: {reason}")

    for line in done:
        print("받음  ", line)
    for line in skipped:
        print("건너뜀", line)
    return 0 if done or not skipped else 1


if __name__ == "__main__":
    sys.exit(main())
