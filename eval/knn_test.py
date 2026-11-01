"""KNN 독립 시험. 가상 인구 holdout을 검증·시험으로 나눠 k는 검증으로만 고르고 시험은 한 번만 돌린다.

pool은 이웃 후보이고, holdout(가상 인구 생성 때 따로 뗀 1000명)을 고정 seed로 반씩 나눈다.
정답은 holdout의 원래 행 전체를 엔진에 넣어 확정(eligible)인 제도다. 추천 쪽 판정은
compare()가 가린 행(masked_row)만 엔진에 넣어 계산하고 원래 행을 보지 않는다.
제도는 나 대상이고 검수된 조건표만 쓴다. 검수 전 AI 조건표는 이웃 해당 표에서 항상 0이라
(population.eligibility) KNN이 추천할 수 없고 정답에도 들 수 없다.
결과에는 집계 지표만 남기고 제도 이름·개인 행은 남기지 않는다.

    uv run --project backend python -m eval.knn_test --today 2026-11-01
"""

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from eval.explore import compare, write_results
from eval.provenance import engine_digest

ROOT = Path(__file__).resolve().parents[1]


def split_holdout(user_ids, seed):
    """holdout ID를 고정 seed로 섞어 (검증, 시험) 두 묶음으로 나눈다."""
    ids = sorted(user_ids)
    order = np.random.default_rng(seed).permutation(len(ids))
    half = len(ids) // 2
    return [ids[i] for i in order[:half]], [ids[i] for i in order[half:]]


def baseline_pick(rules, verdicts, scores, *, sido, sigungu, today):
    """기준선: KNN과 같은 정책 필터를 거친 뒤 이웃 비율 대신 주어진 점수 순으로 고른다."""
    from backend.population.knn import open_to, top_by_type
    candidates = []
    for rule, score in zip(rules, scores):
        mine = verdicts.get(rule["id"], {})
        end = open_to(rule, mine, sido=sido, sigungu=sigungu, today=today)
        if end is None:
            continue
        fields = set(mine.get("blocking_fields", []))
        candidates.append((-float(score), len(fields), end, rule["id"],
                           {"rule_id": rule["id"], "benefit_type": rule.get("benefit_type")}))
    return [item["rule_id"] for item in top_by_type(candidates)]


def _rules():
    from backend.data.rules import load_rules
    from backend.search.corpus import short_sido
    out = []
    for rule in load_rules():
        if rule.get("subject", "self") != "self" or rule.get("review", {}).get("status") != "reviewed":
            continue
        rule = dict(rule)
        # similar_for()와 같이 조건표의 시도 이름을 프로필 표기로 맞춘다
        if rule.get("region") and rule["region"].get("sido"):
            rule["region"] = {**rule["region"], "sido": short_sido(rule["region"]["sido"])}
        out.append(rule)
    return out


def _profile(user_id, values):
    from backend.engine.similar import SELF_FIELDS, _clean
    me = {f: _clean(values.get(f)) for f in SELF_FIELDS if f in values}
    return {"user_id": user_id, "self": me, "parents": [], "consents": {"sensitive": True, "parent": False}}


def run(population, *, today, seed=42):
    from backend.engine import judge
    from backend.engine.derive import tags as profile_tags
    from backend.population import features, knn
    from backend.search.corpus import short_sido

    users = pd.read_parquet(population).drop(columns=["source_uuid", "from_text"], errors="ignore")
    pool_rows = users[users["split"] == "pool"].reset_index(drop=True)
    holdout_rows = users[users["split"] == "holdout"]
    validation_ids, test_ids = split_holdout(holdout_rows["user_id"], seed)
    rules = _rules()
    rule_ids = [r["id"] for r in rules]
    if not rules or pool_rows.empty or not test_ids:
        raise ValueError("검수된 나 대상 조건표, pool, holdout이 필요합니다")

    def eligible(profile):
        verdicts = judge(profile, rules, today)
        return [rid for rid in rule_ids if verdicts[rid]["verdict"] == "eligible"]

    pool_profiles = [_profile(r["user_id"], r) for r in pool_rows.to_dict("records")]
    truth = {p["user_id"]: eligible(p) for p in pool_profiles}
    truth.update({r["user_id"]: eligible(_profile(r["user_id"], r))
                  for r in holdout_rows.to_dict("records")})
    table = np.array([[rid in truth[p["user_id"]] for rid in rule_ids] for p in pool_profiles], dtype=bool)
    tags = [set(profile_tags(p["self"], today)) | ({s} if (s := short_sido(p["self"].get("sido"))) else set())
            for p in pool_profiles]

    pool = features.stage1(pool_rows)
    scale = features.fit_scale(pool)   # compare()가 질의를 만들 때와 같은 scale
    matrix = features.stage2(pool, scale)[features.COLUMNS].to_numpy(dtype=float)
    holdout = features.stage1(holdout_rows).set_index("user_id", drop=False)

    cache = {}

    def recommend(query, k, baseline_scores, *, masked_row):
        me = {f: v for f, v in masked_row.items() if f not in ("user_id", "age")}
        age = masked_row.get("age")
        if age is not None and not pd.isna(age):
            me["birth_year"] = int(features.BASE_YEAR - age)
        profile = _profile(None, me)
        key = json.dumps(profile["self"], sort_keys=True, default=str)
        if key not in cache:
            cache[key] = judge(profile, rules, today)
        verdicts = cache[key]
        sido = short_sido(profile["self"].get("sido"))
        if baseline_scores is not None:
            return baseline_pick(rules, verdicts, baseline_scores, sido=sido, sigungu=None, today=today)
        known = sum(1 for v in profile["self"].values() if v is not None)
        result = knn.recommend(matrix, query, table, rules, verdicts, tags=tags, known_fields=known,
                               sido=sido, sigungu=None, today=today, k=k)
        return [item["rule_id"] for item in result["items"]]

    selection = compare(pool, holdout.loc[validation_ids].reset_index(drop=True), truth, rule_ids, recommend,
                        seed=seed)
    # 시험은 검증에서 고른 k로 한 번만. 시험 결과로 k를 다시 고르지 않는다.
    result = compare(pool, holdout.loc[test_ids].reset_index(drop=True), truth, rule_ids, recommend,
                     seed=seed, fixed_k=selection["k"], validation_ids=selection["validation_ids"])
    result.update(
        selection={"k": selection["k"], "n": len(validation_ids), "scenarios": selection["scenarios"]},
        split={"pool": len(pool), "validation": len(validation_ids), "test": len(test_ids), "seed": seed},
        rules=len(rules), rules_with_positive=int(table.any(axis=0).sum()),
        positive_share=float(table.mean()), today=today.isoformat(),
        population_sha256=hashlib.sha256(Path(population).read_bytes()).hexdigest(),
        engine_sha256=engine_digest(ROOT),
        limitation="가상 인구(가정 분포) 기준이며 정답은 같은 규칙 엔진의 확정 판정이다. 가상 인구에 자산 등 칸이 없어 "
                   "확정 판정이 나오는 제도가 rules_with_positive개로 적고, 이 범위에서 KNN은 무작위보다 높고 인기순과 같다. "
                   "시군구 제도와 부모 제도는 범위 밖이다.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--population", type=Path, default=ROOT / "data/population/users.parquet")
    parser.add_argument("--today", required=True, type=date.fromisoformat)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=ROOT / "eval/explore-results.json")
    parser.add_argument("--overwrite", action="store_true", help="기존 시험 결과를 덮어쓴다(코드·인구가 바뀌어 다시 잴 때만)")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        parser.exit(1, f"{args.output}가 이미 있습니다. 다시 재려면 --overwrite\n")
    out = write_results(run(args.population, today=args.today, seed=args.seed), args.output)
    print(json.dumps({key: out[key] for key in ("k", "demo_enabled", "precision_at_5", "recall_at_5",
                                                "baseline_popular", "baseline_random", "split", "rules")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
