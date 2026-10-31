"""검증기(SPEC §9.3). 스텁: 조건마다 검사를 전부 ok로 단다."""

from __future__ import annotations

import copy

CHECKS = ["schema", "evidence", "value", "comparator", "unit", "keyword", "pair", "layer"]


def verify(rule: dict, lines: list[dict]) -> dict:
    out = copy.deepcopy(rule)
    for c in out.get("conditions", []):
        if c.get("status") == "reviewed" or c.get("field") == "other":
            continue
        c["checks"] = {k: "ok" for k in CHECKS}
        c["status"] = "auto_verified"
    return out
