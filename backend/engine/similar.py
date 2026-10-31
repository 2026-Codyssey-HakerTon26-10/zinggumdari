"""비슷한 가구(SPEC §13, api.md §3 similar). 박범규의 가상 인구·KNN(backend/population)에 엔진 judge를 연결한다.

오프라인: 이웃 후보(pool) 전원을 judge()로 판정해 해당 여부 표를 만든다(population.eligibility.build_table).
    uv run --project backend python -m backend.population.build --n 10000 --holdout 1000 --seed 42 --no-xlsx
    uv run --project backend python -m backend.engine.similar           # → data/population/eligibility.npz
런타임: 내 프로필을 같은 scale로 벡터로 바꿔 이웃을 찾고(population.knn.recommend) similar 모양으로 돌려준다.
캐시(data/population/)가 없으면 None이다. 맞춤 추천과 섞지 않고, 확정(eligible)만 이웃의 해당으로 센다.
"""

from __future__ import annotations

import json
import math
from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np

from backend.engine import judge
from backend.engine.derive import tags as profile_tags
from backend.engine.values import birth_year_of

ROOT = Path(__file__).resolve().parents[2]
POP_DIR = ROOT / "data" / "population"
K = 50


def _clean(v):
    """parquet의 NaN·numpy 값을 엔진이 읽는 파이썬 값으로."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if isinstance(v, np.generic):
        v = v.item()
        return None if isinstance(v, float) and math.isnan(v) else v
    if isinstance(v, np.ndarray):
        return [_clean(x) for x in v.tolist()]
    return v


SELF_FIELDS = ["gender", "birth_year", "sido", "sigungu", "marital_status", "marriage_date", "pregnant", "due_month",
               "children_count", "youngest_child_age", "household_size", "employment_status", "tenure_type",
               "is_householder", "is_homeless", "employment_type", "income_self", "income_spouse", "income_household",
               "dependents_count", "supports_parent_65", "has_account"]


def _users():
    import pandas as pd

    return pd.read_parquet(POP_DIR / "users.parquet")


def pool_profiles() -> list[dict]:
    """이웃 후보(split == pool)를 프로필 모양으로. 가상 인구라 민감정보 동의가 있는 것으로 둔다."""
    users = _users()
    pool = users[users["split"] == "pool"]
    return [{"user_id": row["user_id"], "self": {f: _clean(row.get(f)) for f in SELF_FIELDS if f in row},
             "consents": {"sensitive": True, "parent": False}, "parents": []}
            for row in pool.to_dict("records")]


def _as_of() -> date:
    meta = json.loads((POP_DIR / "meta.json").read_text(encoding="utf-8"))
    return date.fromisoformat(meta.get("as_of", date.today().isoformat())[:10])


def build(rules: list[dict] | None = None, today: date | None = None) -> np.ndarray:
    """이웃 후보 전원을 엔진으로 판정해 data/population/eligibility.npz를 쓴다. 나 대상 조건표만 넣는다."""
    from backend.data.rules import load_rules
    from backend.population.eligibility import build_table

    rules = [r for r in (rules if rules is not None else load_rules()) if r.get("subject", "self") == "self"]
    today = today or _as_of()
    table = build_table(pool_profiles(), rules, lambda p, rs: judge(p, rs, today), POP_DIR / "eligibility.npz")
    clear_cache()
    return table


@lru_cache(maxsize=1)
def _load():
    from backend.search.corpus import short_sido

    paths = [POP_DIR / n for n in ("users.parquet", "X.npy", "meta.json", "eligibility.npz")]
    if not all(p.exists() for p in paths):
        return None
    users = _users()
    pool_mask = (users["split"] == "pool").to_numpy()
    matrix = np.load(POP_DIR / "X.npy")[pool_mask]
    meta = json.loads((POP_DIR / "meta.json").read_text(encoding="utf-8"))
    table = np.load(POP_DIR / "eligibility.npz")
    pool = users[pool_mask]
    if list(table["user_ids"]) != list(pool["user_id"]):
        return None   # 인구를 다시 만들었는데 표를 안 만들었다
    tags = []
    for row in pool.to_dict("records"):
        me = {f: _clean(row.get(f)) for f in SELF_FIELDS if f in row}
        sido = short_sido(me.get("sido"))
        tags.append(set(profile_tags(me, _as_of())) | ({sido} if sido else set()))
    return {"matrix": matrix, "scale": meta["scale"], "eligibility": table["eligibility"],
            "rule_ids": list(table["rule_ids"]), "tags": tags}


def clear_cache() -> None:
    _load.cache_clear()


def similar_for(profile: dict, verdicts: dict[str, dict], rules: list[dict], today: date | None = None,
                k: int = K) -> dict | None:
    """api.md §3 similar. verdicts는 judge() 결과({rule_id: 카드}). 캐시가 없으면 None."""
    from backend.population import features, knn
    from backend.search.corpus import short_sido

    cache = _load()
    if cache is None:
        return None
    today = today or date.today()
    by_id = {r["id"]: r for r in rules}
    cols = [j for j, rid in enumerate(cache["rule_ids"]) if rid in by_id]
    # 박범규 recommend()는 지역 이름을 그대로 비교하므로 조건표 쪽 시도 이름을 프로필 표기(short_sido)로 맞춰 넘긴다
    use = []
    for j in cols:
        rule = dict(by_id[cache["rule_ids"][j]])
        if rule.get("region") and rule["region"].get("sido"):
            rule["region"] = {**rule["region"], "sido": short_sido(rule["region"]["sido"])}
        use.append(rule)
    me = profile.get("self", profile)
    # 가상 인구(행렬)는 출생연도로 만들었다. 프로필은 생년월일이 기준이라 연도만 꺼내 넘긴다
    by = birth_year_of(me)
    query = features.query_vector({"self": {**me, "birth_year": by}}, cache["scale"], year=today.year)
    known = sum(1 for f in features.STAGE1 if f not in ("user_id", "age") and me.get(f) is not None) \
        + (1 if by is not None else 0)
    return knn.recommend(cache["matrix"], query, cache["eligibility"][:, cols], use, verdicts,
                         tags=cache["tags"], known_fields=known, sido=short_sido(me.get("sido")),
                         sigungu=me.get("sigungu"), today=today, k=k)


def main() -> None:
    table = build()
    print(f"이웃 후보 {table.shape[0]}명 × 조건표 {table.shape[1]}개 → {(POP_DIR / 'eligibility.npz').relative_to(ROOT)}"
          f" (해당 {int(table.sum())}칸)")


if __name__ == "__main__":
    main()
