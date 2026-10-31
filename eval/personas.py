"""명시적으로 지정한 가상 페르소나만 점검한다. 추출 평가/시험용 정밀도와 별도다."""

import argparse
from datetime import date
import json
from pathlib import Path

from eval.provenance import digest_files, engine_digest


def evaluate(personas, rules, judge):
    rows = []
    for p in personas:
        expected = p["expected"]
        if p.get("virtual") is not True or not expected.get("evidence"):
            raise ValueError("가상 인물 표시와 독립적인 근거가 필요합니다")
        rid = expected["rule_id"]
        rule = next((r for r in rules if r.get("id") == rid), None)
        if rule is None:
            raise ValueError(f"필요한 손 조건표가 없습니다: {rid}")
        result = judge(p["profile"], [rule], today=date.fromisoformat(p["today"]))[rid]
        actual = result["verdict"]
        rows.append({"id": p["id"], "rule_id": rid, "actual": actual,
                     "passed": actual in expected["allowed_verdicts"], "danger": actual == "eligible" and "eligible" not in expected["allowed_verdicts"]})
    return {"scope": "persona_safety", "n": len(rows), "passed": sum(r["passed"] for r in rows),
            "danger": sum(r["danger"] for r in rows), "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--personas-dir", required=True, type=Path)
    parser.add_argument("--rules-dir", type=Path, default=Path("rules/manual"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # 필요한 ID 파일만 연다. 시험용 조건표를 무차별 로드하지 않는다.
    personas = [json.loads(p.read_text()) for p in sorted(args.personas_dir.glob("*.json"))]
    ids = {p["expected"]["rule_id"] for p in personas}
    if not personas:
        parser.error("평가할 페르소나가 없습니다")
    rules = []
    for rid in sorted(ids):
        if not rid.startswith("manual:") or Path(rid[7:]).name != rid[7:]:
            parser.error("손 조건표 ID 형식을 확인하세요")
        r = json.loads((args.rules_dir / (rid[7:] + ".json")).read_text())
        if r.get("id") != rid:
            parser.error("손 조건표 파일과 ID가 다릅니다")
        rules.append(r)
    from backend.engine import judge
    result = evaluate(personas, rules, judge)
    root = Path(__file__).resolve().parents[1]
    result["engine_sha256"] = engine_digest(root)
    result["personas_sha256"] = digest_files(args.personas_dir, [Path(p.name) for p in args.personas_dir.glob("*.json")])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('scope','n','passed','danger')},ensure_ascii=False))
    if result["passed"] != result["n"]:
        parser.exit(1,"독립 정답과 불일치합니다. 숫자에 맞춰 정답을 변경하지 마세요\n")


if __name__ == "__main__":
    main()
