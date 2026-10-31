"""조건표(rules/manual, rules/compiled) 읽기. 쓰는 것은 백엔드 1과 AI 담당이고 여기서는 읽기만 한다."""

from __future__ import annotations

import json
from pathlib import Path

from backend.data import config


def load_rules(dirs: tuple[Path, ...] | None = None) -> list[dict]:
    """파일 하나 = 제도 하나. 깨진 파일은 건너뛴다(다른 조건표까지 막지 않는다)."""
    rules = []
    for folder in dirs or config.RULES_DIRS:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            try:
                rule = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(rule, dict) and rule.get("id"):
                rules.append(rule)
    return rules

