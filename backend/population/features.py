"""KNN 입력 (팀 시트 「KNN용_1단계_조인」, 「KNN용_2단계_전처리」, 「KNN용_피처사전」 그대로).

1단계: 표들을 user_id로 합친 1인 1행. 2단계: 원핫 + 최소-최대 정규화한 0~1 행렬(32열).
최소·최대는 가상 인구에서 잰 값(scale)을 저장해 두고, 신규 가입자도 같은 값으로 편다.
빈 칸은 NaN으로 남긴다. 거리에서 빼는 것은 KNN 쪽 일이다(SPEC §13.2).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

BASE_YEAR = 2026  # 시트 「KNN용_1단계」 B1 기준연도. 나이 = 기준연도 − 출생연도

STAGE1 = ["user_id", "age", "gender", "sido", "marital_status", "children_count", "youngest_child_age",
          "household_size", "employment_status", "pregnant", "tenure_type", "is_householder",
          "is_homeless", "employment_type", "income_household", "dependents_count",
          "supports_parent_65", "has_account"]

# 최소-최대 정규화하는 칸 → 2단계 열 이름
SCALED = {"age": "age_s", "children_count": "children_s", "household_size": "household_s",
          "income_household": "income_s", "dependents_count": "dependents_s"}

# 2단계 열 순서 그대로: (열 이름, 원본 칸, 값이 이것이면 1)
ONE_HOT = [
    ("gender_여", "gender", "여"),
    ("sido_서울", "sido", "서울"), ("sido_경기", "sido", "경기"),
    ("혼인_미혼", "marital_status", "미혼"), ("혼인_예비부부", "marital_status", "예비부부"),
    ("혼인_신혼", "marital_status", "신혼"), ("혼인_기혼", "marital_status", "기혼"),
    ("혼인_이혼·사별", "marital_status", "이혼·사별"),
    ("취업_재학", "employment_status", "재학"), ("취업_구직", "employment_status", "구직"),
    ("취업_재직", "employment_status", "재직"), ("취업_자영업", "employment_status", "자영업"),
    ("취업_육아휴직", "employment_status", "육아휴직"), ("취업_기타", "employment_status", "기타"),
    ("임신", "pregnant", "Y"),
    ("점유_자가", "tenure_type", "자가"), ("점유_전세", "tenure_type", "전세"),
    ("점유_월세", "tenure_type", "월세"), ("점유_보증부월세", "tenure_type", "보증부월세"),
    ("점유_무상거주", "tenure_type", "무상거주"),
    ("세대주", "is_householder", "세대주"), ("무주택", "is_homeless", "Y"),
    ("맞벌이", "employment_type", "맞벌이"), ("노부모부양", "supports_parent_65", "Y"),
    ("청약통장", "has_account", "Y"),
]
COLUMNS = ["age_s", "gender_여", "sido_서울", "sido_경기", "sido_기타",
           "혼인_미혼", "혼인_예비부부", "혼인_신혼", "혼인_기혼", "혼인_이혼·사별",
           "children_s", "자녀_6세이하", "household_s",
           "취업_재학", "취업_구직", "취업_재직", "취업_자영업", "취업_육아휴직", "취업_기타", "임신",
           "점유_자가", "점유_전세", "점유_월세", "점유_보증부월세", "점유_무상거주",
           "세대주", "무주택", "맞벌이", "income_s", "dependents_s", "노부모부양", "청약통장"]


def stage1(users: pd.DataFrame) -> pd.DataFrame:
    out = users.assign(age=BASE_YEAR - users["birth_year"])
    return out[STAGE1].reset_index(drop=True)


def fit_scale(s1: pd.DataFrame) -> dict[str, list[float]]:
    return {c: [float(s1[c].min()), float(s1[c].max())] for c in SCALED}


def stage2(s1: pd.DataFrame, scale: dict[str, list[float]]) -> pd.DataFrame:
    x = pd.DataFrame(index=s1.index)
    for src, col in SCALED.items():
        lo, hi = scale[src]
        v = pd.to_numeric(s1[src], errors="coerce")
        x[col] = v.where(v.isna(), 0.0) if hi == lo else ((v - lo) / (hi - lo)).clip(0, 1)
    for col, src, value in ONE_HOT:
        known = s1[src].notna()
        x[col] = np.where(known, (s1[src] == value).astype(float), np.nan)
    sido_known = s1["sido"].notna()
    x["sido_기타"] = np.where(sido_known, (~s1["sido"].isin(["서울", "경기"])).astype(float), np.nan)
    # 막내 6세 이하면 1, 자녀가 없으면 0. 자녀 수를 모르면 빈 칸
    youngest = pd.to_numeric(s1["youngest_child_age"], errors="coerce")
    kids = pd.to_numeric(s1["children_count"], errors="coerce")
    x["자녀_6세이하"] = np.where(
        kids.isna() | ((kids > 0) & youngest.isna()), np.nan,
        ((kids > 0) & (youngest <= 6)).astype(float),
    )
    x.insert(0, "user_id", s1["user_id"])
    return x[["user_id", *COLUMNS]]


def query_vector(profile: dict, scale: dict, *, year: int):
    """가입한 칸만 있는 프로필도 기존 인구 scale로 변환한다."""
    values = profile.get("self", profile)
    row = {key: values.get(key) for key in STAGE1}
    row["age"] = year - values["birth_year"] if values.get("birth_year") is not None else None
    return stage2(pd.DataFrame([row]), scale)[COLUMNS].iloc[0].to_numpy(dtype=float)
