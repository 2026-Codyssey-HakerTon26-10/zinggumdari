"""고정 시드 holdout 비교. 정책 필터를 포함한 추천 함수를 주입해 비교한다."""

import numpy as np
import pandas as pd

from backend.population import features
from eval.score import ranking_score


def compare(pool, holdout, truth, rule_ids, recommend, *, seed=42, fixed_k=None, validation_ids=None):
    """recommend(query, k, baseline_scores, masked_row=가린행)는 필터 후 ID를 반환한다.

    입력 행은 피처 처리 전 STAGE1 사전이다. 원핫 묶음을 통째로 가려
    원래 칸의 값을 다른 원핫 열에서 알아낼 수 없게 한다. truth는
    {user_id: [eligible rule ID]}이며 pool의 판정은 recommend 어댑터가 가진다.
    baseline_scores가 None이면 KNN, 배열이면 그 비율로 동일 필터를 적용한다.
    """
    if not len(pool) or not len(holdout) or len(set(rule_ids)) != len(rule_ids):
        raise ValueError("이웃 후보·holdout·고유 제도 ID가 필요합니다")
    if set(pool.user_id) & set(holdout.user_id):
        raise ValueError("학습 후보와 holdout이 겹칩니다")
    if fixed_k is not None:
        if fixed_k not in (20, 50, 100) or not validation_ids:
            raise ValueError("최종 시험에는 동결한 k와 검증 집합 ID가 필요합니다")
        if set(validation_ids) & (set(pool.user_id) | set(holdout.user_id)):
            raise ValueError("검증 집합은 pool·최종 시험과 분리해야 합니다")
    rng = np.random.default_rng(seed)
    popularity = np.array([sum(r in truth[u] for u in pool.user_id) / len(pool) for r in rule_ids])
    scale = features.fit_scale(pool)
    fields = [c for c in features.STAGE1 if c != "user_id"]
    results = {}
    for known in (1, 3, len(fields) // 2):
        queries = []
        for _, row in holdout.iterrows():
            present = [f for f in fields if pd.notna(row[f])]
            keep = set(rng.choice(present, min(known, len(present)), replace=False))
            masked = row.copy()
            for f in fields:
                if f not in keep:
                    masked[f] = None
            vector = features.stage2(masked.to_frame().T, scale)[features.COLUMNS].iloc[0].to_numpy(dtype=float)
            queries.append((vector, masked.to_dict()))
        expected = [truth[u] for u in holdout.user_id]
        metrics = {}
        for k in ((fixed_k,) if fixed_k is not None else (20, 50, 100)):
            metrics[str(k)] = ranking_score([recommend(q, k, None, masked_row=row) for q, row in queries], expected)
        metrics["baseline_popular"] = ranking_score([recommend(q, fixed_k or 50, popularity, masked_row=row) for q, row in queries], expected)
        metrics["baseline_random"] = ranking_score([recommend(q, fixed_k or 50, rng.random(len(rule_ids)), masked_row=row) for q, row in queries], expected)
        results[str(known)] = metrics
    # k는 precision@5, recall@5가 높은 순으로 선택하고 동률이면 작은 k.
    best = fixed_k or max((20, 50, 100), key=lambda k: (
        sum(v[str(k)]["precision_at_5"] or 0 for v in results.values()),
        sum(v[str(k)]["recall_at_5"] or 0 for v in results.values()), -k))
    enabled = all((v[str(best)]["precision_at_5"] or 0) >= (v["baseline_popular"]["precision_at_5"] or 0)
                  for v in results.values())
    return dict(k=best, scenarios=results, demo_enabled=enabled if fixed_k is not None else None,
                purpose="test" if fixed_k is not None else "validation",
                validation_ids=list(validation_ids) if fixed_k is not None else list(holdout.user_id), seed=seed,
                basis="가상 인구(가정 분포) 기준. 정답도 같은 규칙에서 나온 값")


def write_results(result, path):
    """독립 시험 결과만 공개 통계로 저장한다. scenarios는 가림 수준별 상세다."""
    import json
    from pathlib import Path
    if result.get("purpose") != "test":
        raise ValueError("탐색용 검증 결과는 최종 시험 성능으로 공개할 수 없습니다")
    selected = [v[str(result["k"])] for v in result["scenarios"].values()]
    def mean(rows, key):
        values = [r[key] for r in rows if r[key] is not None]
        return sum(values) / len(values) if values else None
    out = {k: v for k, v in result.items() if k != "validation_ids"}
    out.update(precision_at_5=mean(selected, "precision_at_5"), recall_at_5=mean(selected, "recall_at_5"),
               baseline_question_only=None, variant_rule_bins=None)
    for name in ("baseline_popular", "baseline_random"):
        rows = [v[name] for v in result["scenarios"].values()]
        out[name] = {key: mean(rows, key) for key in ("precision_at_5", "recall_at_5")}
    Path(path).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    return out


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path
    parser = argparse.ArgumentParser(description="독립 시험 결과를 공개 통계 형식으로 내보내기")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("eval/explore-results.json"))
    args = parser.parse_args()
    write_results(json.loads(args.input.read_text()), args.output)
