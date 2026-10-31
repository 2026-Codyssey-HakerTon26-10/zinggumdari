"""비슷한 가구(SPEC §13, api.md §3 similar): 가상 인구 전수 판정표 + 박범규 KNN에 엔진 judge를 연결한다."""

import json
import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from backend.engine import judge, similar
from backend.population import features

TODAY = date(2026, 11, 1)


def C(field, op, value, **kw):
    return {"field": field, "op": op, "value": value, "evidence": ["doc:l1"], "status": "reviewed", **kw}


def R(rid, conds, **kw):
    return {"id": rid, "source": "manual", "subject": "self", "name": rid, "benefit_type": "loan",
            "conditions": conds, "review": {"status": "reviewed"}, "updated": "2026-10-31", **kw}


# 소득 600 이하면 받는 제도: 이웃(소득 300)은 다 해당, 나는 소득을 안 적어 확인 필요
LOW = R("manual:low", [C("income_household", "<=", 600)])
SEOUL = R("manual:seoul", [C("income_household", "<=", 600)], region={"sido": "서울특별시", "sigungu": None})
YOUNG = R("manual:young", [C("age", "<=", 20)])   # 이웃이 해당 안 되는 제도


def _users(n=30):
    rows = []
    for i in range(n):
        rows.append({"user_id": f"P{i:03d}", "split": "pool" if i < n - 5 else "holdout", "gender": "여",
                     "birth_year": 1997 + i % 3, "sido": "서울", "sigungu": "마포구", "marital_status": "미혼",
                     "marriage_date": math.nan, "pregnant": "N", "due_month": math.nan, "children_count": 0,
                     "youngest_child_age": None, "household_size": 1, "employment_status": "재직",
                     "tenure_type": "월세", "is_householder": "세대주", "is_homeless": "Y", "employment_type": "해당없음",
                     "income_self": 300, "income_spouse": None, "income_household": 300, "dependents_count": 0,
                     "supports_parent_65": "N", "has_account": "N"})
    return pd.DataFrame(rows)


@pytest.fixture
def pop(tmp_path, monkeypatch):
    users = _users()
    s1 = features.stage1(users)
    scale = features.fit_scale(s1[users["split"] == "pool"])
    x = features.stage2(s1, scale)
    users.to_parquet(tmp_path / "users.parquet", index=False)
    np.save(tmp_path / "X.npy", x[features.COLUMNS].to_numpy(dtype=np.float32))
    (tmp_path / "meta.json").write_text(json.dumps({"as_of": "2026-10-31", "scale": scale}), encoding="utf-8")
    monkeypatch.setattr(similar, "POP_DIR", tmp_path)
    similar.clear_cache()
    yield tmp_path
    similar.clear_cache()


def test_pool_profiles_clean_values(pop):
    profiles = similar.pool_profiles()
    assert len(profiles) == 25   # holdout은 이웃 후보가 아니다
    me = profiles[0]["self"]
    assert me["marriage_date"] is None and type(me["birth_year"]) is int and type(me["household_size"]) is int


def test_build_table_with_engine(pop):
    table = similar.build([LOW, SEOUL, YOUNG], today=TODAY)
    assert table.shape == (25, 3)
    assert table[:, 0].all() and table[:, 1].all() and not table[:, 2].any()


def test_similar_for_recommends_what_neighbors_get(pop):
    rules = [LOW, SEOUL, YOUNG]
    similar.build(rules, today=TODAY)
    me = {"self": {"birth_year": 1998, "sido": "서울", "marital_status": "미혼", "household_size": 1,
                   "is_homeless": "Y", "tenure_type": "월세"}, "consents": {"sensitive": True}}
    out = similar.similar_for(me, judge(me, rules, TODAY), rules, today=TODAY)
    assert out["basis"].startswith("가상 인구") and out["neighbors"] > 0
    ids = [i["rule_id"] for i in out["items"]]
    assert ids == ["manual:low", "manual:seoul"]   # 서울 제도도 지역 이름(서울특별시·서울)을 맞춰 남는다
    assert out["items"][0]["blocking_fields"] == ["income_household"] and out["items"][0]["prevalence"] == 1.0
    assert "청년" in out["label"]


def test_similar_skips_other_region(pop):
    rules = [SEOUL]
    similar.build(rules, today=TODAY)
    me = {"self": {"birth_year": 1998, "sido": "경남", "marital_status": "미혼"}, "consents": {"sensitive": True}}
    assert similar.similar_for(me, judge(me, rules, TODAY), rules, today=TODAY)["items"] == []


def test_similar_none_without_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(similar, "POP_DIR", tmp_path)
    similar.clear_cache()
    me = {"self": {"birth_year": 1998}}
    assert similar.similar_for(me, judge(me, [LOW], TODAY), [LOW], today=TODAY) is None
    similar.clear_cache()
