"""가상 인구 만들기 (SPEC §13.1).

    uv run --project backend python -m backend.population.build --n 10000 --holdout 1000 --seed 42

뼈대는 NVIDIA Nemotron-Personas-Korea(CC BY 4.0)의 19~39세 n명이다. 뽑은 원본은
data/raw/nemotron/에 캐시해 두고(커밋), 다음부터는 네트워크 없이 같은 결과를 만든다.

data/population/에 쓰는 것:
- users.parquet: 1인 1행. 시트 DB샘플 칸 전부 + split, 원본 칸, from_text
- X.npy: 시트 「KNN용_2단계」 그대로의 입력 행렬(users.parquet와 같은 순서)
- meta.json: 출처, 가정값, 정규화 최소·최대, 열 이름, 글에서 온 칸 수
- 더미데이터.xlsx: 팀 시트와 같은 탭(DB샘플 4개, KNN용 1·2단계, 출처·가정)

판정표(eligibility.npz)는 규칙 엔진이 생기면 여기에 붙인다.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from backend.population import features
from backend.population.synth import AS_OF, ASSUMPTIONS, check, synthesize

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "nemotron"
OUT_DIR = ROOT / "data" / "population"

SOURCE = "hf://datasets/nvidia/Nemotron-Personas-Korea/data/*.parquet"
SOURCE_URL = "https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea"
AGE_RANGE = (19, 39)
RAW_COLUMNS = ["uuid", "sex", "age", "marital_status", "family_type", "occupation",
               "province", "district", "persona", "family_persona"]

TABLES = {  # 시트 DB필드 탭의 칸 순서(situation_text는 MVP에서 받지 않아 뺀다)
    "DB샘플_users(원본)": ["user_id", "nickname", "gender", "birth_year", "sido", "sigungu",
                         "marital_status", "marriage_date", "pregnant", "due_month", "children_count",
                         "youngest_child_age", "household_size", "employment_status"],
    "DB샘플_housing(원본)": ["user_id", "tenure_type", "is_householder", "is_homeless"],
    "DB샘플_income(원본)": ["user_id", "employment_type", "income_self", "income_spouse",
                          "income_household", "dependents_count", "supports_parent_65"],
    "DB샘플_subscription(원본)": ["user_id", "has_account"],
}


def fetch(n: int, seed: int, refresh: bool = False) -> pd.DataFrame:
    """19~39세에서 n명. md5(uuid + seed) 순서라 같은 n, seed면 언제나 같은 사람들이다."""
    path = RAW_DIR / f"slice_n{n}_seed{seed}.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    import duckdb

    lo, hi = AGE_RANGE
    df = duckdb.sql(f"""
        SELECT {", ".join(RAW_COLUMNS)} FROM '{SOURCE}'
        WHERE age BETWEEN {lo} AND {hi}
        ORDER BY md5(uuid || '{seed}') LIMIT {n}
    """).df()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="zstd", index=False)
    return df


def _meta(users: pd.DataFrame, scale: dict, n: int, seed: int, holdout: int) -> dict:
    return {
        "as_of": AS_OF.isoformat(),
        "source": {"name": "NVIDIA Nemotron-Personas-Korea", "url": SOURCE_URL, "license": "CC BY 4.0",
                   "age_range": list(AGE_RANGE), "columns": RAW_COLUMNS},
        "basis": "가상 인구(가정 분포). 성별·나이·지역·혼인·가구 형태·직업은 원본, 나머지는 글에서 읽거나 가정값",
        "n": n, "seed": seed, "holdout": holdout,
        "assumptions": ASSUMPTIONS,
        "from_text": dict(Counter(f for fs in users["from_text"] for f in fs)),
        "scale": scale,
        "x_columns": features.COLUMNS,
    }


def _write_xlsx(path: Path, users: pd.DataFrame, s1: pd.DataFrame, x: pd.DataFrame, meta: dict) -> None:
    rows = [("출처", f"{meta['source']['name']} ({meta['source']['license']}) {meta['source']['url']}"),
            ("뽑은 범위", f"{AGE_RANGE[0]}~{AGE_RANGE[1]}세 {meta['n']}명, seed {meta['seed']}, 기준일 {meta['as_of']}"),
            ("원본 그대로", "gender, birth_year(나이에서), sido, sigungu, marital_status(미혼·이혼·사별), household_size(가구 형태에서)"),
            ("글에서 읽은 칸 수", json.dumps(meta["from_text"], ensure_ascii=False))]
    rows += [(f"가정: {k}", json.dumps(v, ensure_ascii=False)) for k, v in ASSUMPTIONS.items()]
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for sheet, cols in TABLES.items():
            users[cols].to_excel(xw, sheet_name=sheet, index=False)
        s1.to_excel(xw, sheet_name="KNN용_1단계_조인(1인1행)", index=False)
        x.to_excel(xw, sheet_name="KNN용_2단계_전처리(입력행렬)", index=False)
        pd.DataFrame(rows, columns=["항목", "값"]).to_excel(xw, sheet_name="출처·가정", index=False)


def build(n: int, holdout: int, seed: int, refresh: bool = False, xlsx: bool = True) -> pd.DataFrame:
    raw = fetch(n, seed, refresh)
    users = synthesize(raw, seed, holdout)
    problems = check(users)
    if problems:
        raise SystemExit("모순이 있어 만들지 않았다:\n" + "\n".join(problems[:20]))

    s1 = features.stage1(users)
    scale = features.fit_scale(s1[users["split"] == "pool"])
    x = features.stage2(s1, scale)
    meta = _meta(users, scale, n, seed, holdout)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    users.to_parquet(OUT_DIR / "users.parquet", index=False)
    np.save(OUT_DIR / "X.npy", x[features.COLUMNS].to_numpy(dtype=np.float32))
    (OUT_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    if xlsx:
        _write_xlsx(OUT_DIR / "더미데이터.xlsx", users, s1, x, meta)
    return users


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--n", type=int, default=10000)
    p.add_argument("--holdout", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--refresh", action="store_true", help="캐시를 무시하고 원본을 다시 받는다")
    p.add_argument("--no-xlsx", action="store_true")
    a = p.parse_args()
    users = build(a.n, a.holdout, a.seed, a.refresh, not a.no_xlsx)
    print(f"{len(users)}명 → {OUT_DIR.relative_to(ROOT)}/ (이웃 후보 {len(users) - a.holdout}, 평가 {a.holdout})")
    for col in ("marital_status", "employment_status", "children_count", "tenure_type", "pregnant"):
        print(f"  {col}: {users[col].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
