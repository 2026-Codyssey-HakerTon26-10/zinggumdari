import pytest

from eval.score import extraction_score, ranking_score, verdict_score, score
from eval.coverage import coverage
from eval.explore import compare
from backend.population import features
import pandas as pd


def test_precision_counts_duplicates_and_omissions():
    gold = [dict(field="age", op=">=", value=19, evidence=["d:l1"]),
            dict(field="age", op="<=", value=34, evidence=["d:l2"])]
    item = {**gold[0], "status": "auto_verified"}
    result = extraction_score(gold, [item, item])
    assert result["correct"] == 1 and result["auto_verified"] == 2
    assert result["silent_omissions"] == [gold[1]]
    assert not extraction_score(gold, [item, dict(reason="unaccounted", evidence=["d:l2"])])["silent_omissions"]


def test_dangerous_and_missing_are_separate():
    result = verdict_score([dict(expected="ineligible", actual="eligible"), dict(expected="needs_check", actual="ineligible")])
    assert result["dangerous"] == 1 and result["missed"] == 1
    with pytest.raises(ValueError):
        verdict_score([dict(expected="fake", actual="eligible")])


def test_empty_evaluation_has_no_fabricated_accuracy():
    assert score({})["verdicts"]["accuracy"] is None
    assert ranking_score([], [])["precision_at_5"] is None
    assert ranking_score([["a", "a"]], [["a"]])["precision_at_5"] == .2


def test_holdout_comparison_masks_source_fields_reproducibly():
    rows = [{key: None for key in features.STAGE1} for _ in range(3)]
    for i, row in enumerate(rows):
        row.update(user_id=str(i), age=25 + i, children_count=0, household_size=1,
                   income_household=200, dependents_count=0, gender="여", sido="서울")
    pool, holdout = pd.DataFrame(rows[:2]), pd.DataFrame(rows[2:])
    truth = {str(i): ["r"] for i in range(3)}
    first = compare(pool, holdout, truth, ["r"], lambda q, k, b: ["r"])
    assert first == compare(pool, holdout, truth, ["r"], lambda q, k, b: ["r"])
    assert first["k"] == 20 and first["demo_enabled"]
    with pytest.raises(ValueError):
        compare(pool, pool, truth, ["r"], lambda q, k, b: [])


def test_coverage_has_no_evaluation_until_scored():
    assert coverage([])["evaluation"] is None
