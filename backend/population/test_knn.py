from datetime import date

import numpy as np
import pytest

from backend.population.knn import neighbors, recommend
from backend.population.eligibility import build_table
from backend.population import features


def test_missing_and_ties():
    assert neighbors([[0, 1], [0, 0], [1, 0]], [0, np.nan], 1).tolist() == [0, 1]
    assert neighbors([[0]], [np.nan]).tolist() == []
    assert neighbors([[0], [1]], [0], exclude=0).tolist() == [1]


def test_constant_scale_and_unknown_child_age_stay_missing():
    scale = {name: [1, 1] for name in features.SCALED}
    vector = features.query_vector({"self": {"birth_year": 2000, "children_count": 1}}, scale, year=2026)
    assert np.isnan(vector[features.COLUMNS.index("income_s")])
    assert np.isnan(vector[features.COLUMNS.index("자녀_6세이하")])


def test_recommend_filters_and_limits():
    rules = [dict(id=str(i), name=str(i), subject="self", benefit_type="cash") for i in range(7)]
    rules[3]["region"] = {"unknown": True}
    rules[4]["subject"] = "parent"
    verdicts = {r["id"]: {"verdict": "needs_check", "blocking_fields": ["income_self"]} for r in rules}
    verdicts["0"] = {"verdict": "eligible"}
    verdicts["1"] = {"verdict": "ineligible"}
    verdicts["2"]["deadline"] = "2026-01-01"
    out = recommend([[0], [0]], [0], np.ones((2, 7), dtype=bool), rules, verdicts,
                    tags=[["청년"], ["청년"]], known_fields=1, today=date(2026, 10, 31))
    assert [r["rule_id"] for r in out["items"]] == ["5", "6"]
    assert out["assignment"] == "reference" and out["neighbors"] == 2


def test_unreviewed_ai_never_enters_table(tmp_path):
    rules = [dict(id="a", review={"status": "unreviewed"})]
    table = build_table([{"user_id": "u"}], rules, lambda p, r: {"a": {"verdict": "eligible"}}, tmp_path / "e.npz")
    assert not table.any()
    with np.load(tmp_path / "e.npz", allow_pickle=False) as saved:
        assert saved["rule_ids"].tolist() == ["a"]
    with pytest.raises(ValueError):
        build_table([{"user_id": "u"}], rules, lambda p, r: {}, tmp_path / "bad.npz")


def test_labels_threshold_ranking_and_type_caps():
    rules = [dict(id=str(i), name=str(i), subject="self", benefit_type="cash" if i < 4 else str(i)) for i in range(9)]
    verdicts = {r["id"]: dict(verdict="needs_check", deadline="상시", blocking_fields=["income_self"]) for r in rules}
    y = np.ones((10, 9), dtype=bool)
    y[:, 8] = False
    y[:2, 8] = True  # 20%: 문턱 미달
    result = recommend(np.zeros((10, 1)), [0], y, rules, verdicts,
                       tags=[["homeless", "youth", "서울"]] * 10, known_fields=3)
    assert result["label"] == "주로 청년·무주택·서울 가구"
    assert [r["rule_id"] for r in result["items"]] == ["0", "1", "4", "5", "6"]
    verdicts["0"]["blocking_fields"] = ["a", "b"]
    verdicts["1"]["deadline"] = "미정"
    result = recommend(np.zeros((10, 1)), [0], y, rules, verdicts,
                       tags=[[]] * 10, known_fields=3)
    assert result["items"][0]["rule_id"] == "1"
