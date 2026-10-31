"""조건표 읽기. 쓰는 것은 백엔드1(손 조건표 일부), AI 담당, 공고 투입이고 여기서는 읽기만 한다.

- rules/manual, rules/compiled: 모두가 쓰는 조건표. 기본으로 이것만 읽는다.
- rules/uploads: 사용자 업로드 조건표. owner(계정 ID)를 줄 때만 그 계정이 올린 것만 더한다
  (docs/api.md 「인증·소유권 계약」). 남의 업로드가 판정·근거 줄·알림에 섞이지 않게 한다.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.data import config


def _read(path: Path) -> dict | None:
    try:
        rule = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return rule if isinstance(rule, dict) and rule.get("id") else None


def owned_upload_doc_ids(owner: str) -> list[str]:
    """그 계정이 올린 업로드 원문(source: upload, uploaded_by == owner)."""
    from backend.notices import store   # notices가 data.config를 쓰므로 함수 안에서 부른다

    out = []
    for doc_id in store.list_doc_ids():
        meta = store.load_meta(doc_id) or {}
        if meta.get("source") == "upload" and meta.get("uploaded_by") and meta["uploaded_by"] == owner:
            out.append(doc_id)
    return out


def load_rules(dirs: tuple[Path, ...] | None = None, owner: str | None = None) -> list[dict]:
    """파일 하나 = 제도 하나. 깨진 파일은 건너뛴다(다른 조건표까지 막지 않는다).

    owner를 주면 그 계정의 업로드 조건표(rules/uploads/{doc_id}__*.json)를 더한다. 안 주면 업로드는 읽지 않는다.
    """
    rules = []
    for folder in dirs or config.RULES_DIRS:
        if folder.is_dir():
            rules += [r for p in sorted(folder.glob("*.json")) if (r := _read(p))]
    if owner and config.UPLOAD_RULES_DIR.is_dir():
        for doc_id in owned_upload_doc_ids(owner):
            rules += [r for p in sorted(config.UPLOAD_RULES_DIR.glob(f"{doc_id}__*.json")) if (r := _read(p))]
    return rules
