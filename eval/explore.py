"""고정 시드 holdout 비교. 정책 필터를 포함한 추천 함수를 주입해 비교한다."""

import numpy as np
import pandas as pd

from backend.population import features
from eval.score import ranking_score


def compare(pool, holdout, truth, rule_ids, recommend, *, seed=42):
    """recommend(query, k, baseline_scores)는 필터 후 ID 상위 5개를 반환한다.

    입력 행은 피처 처리 전 STAGE1 사전이다. 원핫 묶음을 통째로 가려
    원래 칸의 값을 다른 원핫 열에서 알아낼 수 없게 한다. truth는
    {user_id: [eligible rule ID]}이며 pool의 판정은 recommend 어댑터가 가진다.
    baseline_scores가 None이면 KNN, 배열이면 그 비율로 동일 필터를 적용한다.
    """
    if not len(pool) or not len(holdout) or len(set(rule_ids)) != len(rule_ids):
        raise ValueError("이웃 후보·holdout·고유 제도 ID가 필요합니다")
    if set(pool.user_id) & set(holdout.user_id):
        raise ValueError("학습 후보와 holdout이 겹칩니다")
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
            queries.append(vector)
        expected = [truth[u] for u in holdout.user_id]
        metrics = {}
        for k in (20, 50, 100):
            metrics[str(k)] = ranking_score([recommend(q, k, None) for q in queries], expected)
        metrics["baseline_popular"] = ranking_score([recommend(q, 50, popularity) for q in queries], expected)
        metrics["baseline_random"] = ranking_score([recommend(q, 50, rng.random(len(rule_ids))) for q in queries], expected)
        results[str(known)] = metrics
    # k는 precision@5, recall@5가 높은 순으로 선택하고 동률이면 작은 k.
    best = max((20, 50, 100), key=lambda k: (
        sum(v[str(k)]["precision_at_5"] or 0 for v in results.values()),
        sum(v[str(k)]["recall_at_5"] or 0 for v in results.values()), -k))
    enabled = all((v[str(best)]["precision_at_5"] or 0) >= (v["baseline_popular"]["precision_at_5"] or 0)
                  for v in results.values())
    return dict(k=best, scenarios=results, demo_enabled=enabled, seed=seed,
                basis="가상 인구(가정 분포) 기준. 정답도 같은 규칙에서 나온 값")
