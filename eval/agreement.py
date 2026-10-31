"""가상 인구 캐시에서 개발용 손/AI 조건표의 판정을 비교한다. 부모 정보는 지어내지 않는다."""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path

import pandas as pd

from eval.provenance import engine_digest


def build(document, population, rules_dir, *, today):
    from backend.engine import judge
    rows = pd.read_parquet(population)
    pool = rows[rows["split"] == "pool"]
    pairs = document["extraction"]
    rules = []
    skipped = []
    for pair in pairs:
        rid = pair["rule_id"]
        if not rid.startswith("manual:") or Path(rid[7:]).name != rid[7:]:
            raise ValueError("손 조건표 ID를 확인하세요")
        gold = json.loads((Path(rules_dir) / (rid[7:] + '.json')).read_text())
        if gold["subject"] == "parent":
            skipped.append(rid)
            continue
        rules.append(({**gold, "conditions": pair["gold"]}, {**gold, "source": "ai", "review": {"status": "unreviewed"}, "conditions": pair["extracted"]}))
    if not rules or pool.empty:
        raise ValueError("개발용 조건표와 pool 가상 인구가 필요합니다")
    verdicts = []
    # 식별용 source_uuid와 자유 텍스트는 판정에 전달하지 않는다.
    for record in pool.drop(columns=[c for c in ("source_uuid", "from_text") if c in pool]).to_dict('records'):
        me = {k: None if pd.isna(v) else v for k, v in record.items() if k not in ('user_id','split')}
        profile = {"user_id": record['user_id'], "self": me, "parents": [], "consents": {"sensitive": True, "parent": False}}
        for gold, ai in rules:
            rid = gold['id']
            expected = judge(profile, [gold], today=today)[rid]['verdict']
            actual = judge(profile, [ai], today=today, ai_eligible=True)[rid]['verdict']
            verdicts.append({"user_id": str(record['user_id']), "rule_id": rid, "expected": expected, "actual": actual})
    return {"verdicts": verdicts, "population_sha256": hashlib.sha256(Path(population).read_bytes()).hexdigest(),
            "engine_sha256": engine_digest(Path(__file__).resolve().parents[1]),
            "today": today.isoformat(), "households": len(pool), "skipped_parent_rules": skipped,
            "limitation": "가상 인구의 pool만 사용. 부모 정보가 없어 부모 제도는 제외. 같은 엔진에 손/AI 조건을 각각 넣어 비교한 값이며 독립적인 법률 정확도가 아님."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--population', required=True, type=Path)
    parser.add_argument('--rules-dir', type=Path, default=Path('rules/manual'))
    parser.add_argument('--today', required=True, type=date.fromisoformat)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = build(json.loads(args.input.read_text()), args.population, args.rules_dir, today=args.today)
    args.output.write_text(json.dumps(result,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='verdicts'},ensure_ascii=False))


if __name__ == '__main__':
    main()
