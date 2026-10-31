"""캐시된 AI 조건의 auto_verified 중 무작위 표본 50개를 추출한다. 정답은 만들지 않는다."""

import argparse
import hashlib
import json
from pathlib import Path
import random


def prepare(rules, *, seed=42):
    candidates = {}
    for rule in rules:
        if rule.get("source") in {"manual", "upload"}:
            continue
        for index, condition in enumerate(rule.get("conditions", [])):
            if condition.get("status") != "auto_verified":
                continue
            evidence = condition.get("evidence") or []
            if not evidence or not rule.get("id"):
                raise ValueError("표본에는 rule_id와 원문 근거 줄이 필요합니다")
            key = (rule["id"], index)
            if key in candidates:
                raise ValueError("같은 AI 조건표가 중복됐습니다")
            candidates[key] = {"rule_id": rule["id"], "condition_index": index,
                               "condition": condition, "correct": None}
    if len(candidates) < 50:
        raise ValueError(f"auto_verified 후보 {len(candidates)}개: 실제 조건 50개 이상이 필요합니다")
    ordered = [candidates[k] for k in sorted(candidates)]
    digest = hashlib.sha256(json.dumps(ordered, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {"status": "awaiting_review", "seed": seed, "population": len(ordered),
            "population_sha256": digest, "rows": random.Random(seed).sample(ordered, 50)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-dir", type=Path, default=Path("rules/compiled"))
    parser.add_argument("--output", type=Path, default=Path("eval/sample50.json"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("기존 표본은 덮어쓰지 않습니다. 검토 중인 표본을 유지하세요")
    rules = [json.loads(p.read_text()) for p in sorted(args.rules_dir.glob("*.json"))]
    try:
        result = prepare(rules, seed=args.seed)
    except ValueError as e:
        parser.error(str(e))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
