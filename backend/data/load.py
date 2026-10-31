"""저장된 덤프 읽기. 런타임(검색, 공고문)은 이것만 쓰고 API를 부르지 않는다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

from backend.data import config
from backend.data.sources import DETAIL_SOURCES, LIST_SOURCES, parse


def _folder(name: str, raw_dir: Path | None) -> Path:
    return (raw_dir or config.RAW_DIR) / name


def meta(name: str, raw_dir: Path | None = None) -> dict | None:
    path = _folder(name, raw_dir) / "_meta.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def iter_items(name: str, raw_dir: Path | None = None) -> Iterator[dict]:
    """목록 덤프의 항목을 페이지 순서대로."""
    src = LIST_SOURCES[name]
    folder = _folder(name, raw_dir)
    if not folder.is_dir():
        return
    for path in sorted(folder.glob(f"page-*.{src.fmt}")):
        for item in src.items(parse(src.fmt, path.read_text(encoding="utf-8"))):
            if isinstance(item, dict):
                yield item


def iter_details(name: str, raw_dir: Path | None = None) -> Iterator[tuple[str, object]]:
    """상세 덤프를 (항목 ID, 파싱한 응답)으로."""
    src = DETAIL_SOURCES[name]
    folder = _folder(name, raw_dir)
    if not folder.is_dir():
        return
    for path in sorted(folder.glob(f"*.{src.fmt}")):
        if path.name.startswith("_"):
            continue
        yield path.stem, parse(src.fmt, path.read_text(encoding="utf-8"))
