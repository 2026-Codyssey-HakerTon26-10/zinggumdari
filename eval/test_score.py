import pytest

from eval.score import extraction_score, ranking_score, verdict_score, score
from eval.coverage import coverage
from eval.explore import compare, write_results
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
    seen = []
    def recommend(q, k, b, *, masked_row):
        import numpy as np
        assert sum(pd.notna(v) for key, v in masked_row.items() if key != "user_id") <= len(features.STAGE1) // 2
        if masked_row["sido"] is None:
            assert np.isnan(q[features.COLUMNS.index("sido_서울")])
        seen.append(masked_row)
        return ["r"]
    first = compare(pool, holdout, truth, ["r"], recommend)
    assert first == compare(pool, holdout, truth, ["r"], recommend)
    assert first["k"] == 20 and first["demo_enabled"] is None
    assert first["purpose"] == "validation" and seen
    with pytest.raises(ValueError):
        write_results(first, "unused.json")
    with pytest.raises(ValueError):
        compare(pool, pool, truth, ["r"], lambda q, k, b: [])


def test_coverage_has_no_evaluation_until_scored():
    assert coverage([])["eval"] is None


def test_fixed_test_cannot_overlap_validation_and_only_calls_frozen_k(tmp_path):
    rows = [{key: None for key in features.STAGE1} for _ in range(2)]
    for i, row in enumerate(rows):
        row.update(user_id=str(i), age=25, children_count=0, household_size=1, income_household=200, dependents_count=0)
    pool, test = pd.DataFrame(rows[:1]), pd.DataFrame(rows[1:])
    truth = {"0": ["r"], "1": ["r"]}
    ks = []
    def recommend(q, k, b, *, masked_row):
        ks.append(k)
        return ["r"]
    with pytest.raises(ValueError):
        compare(pool, test, truth, ["r"], recommend, fixed_k=50, validation_ids=["1"])
    result = compare(pool, test, truth, ["r"], recommend, fixed_k=50, validation_ids=["validation-only"])
    assert set(ks) == {50} and result["purpose"] == "test"
    exported = write_results(result, tmp_path / "explore.json")
    assert exported["precision_at_5"] == pytest.approx(.2)
    assert "validation_ids" not in exported


def test_other_text_is_part_of_matching_key_and_test_is_rejected():
    gold = dict(field="other", text="순자산 기준 이하", evidence=["d:l1"])
    actual = dict(field="other", text="다른 조건", evidence=["d:l2"])
    assert extraction_score([gold], [actual])["silent_omissions"] == [gold]
    document = {"extraction": [dict(rule_id="test", gold=[gold], extracted=[actual])]}
    with pytest.raises(ValueError):
        score(document, {"dev": ["dev"], "test": ["test"]})
    document["extraction"][0]["rule_id"] = "dev"
    result = score(document, {"dev": ["dev"], "test": ["test"]})
    assert result["missed"] == 1 and result["split"] == {"dev": 1, "test": 1}
    assert coverage([], result)["eval"]["missed"] == 1
    assert ranking_score([[]], [[]])["recall_n"] == 0


@pytest.mark.parametrize("rule_id", ["test", "outside", "unknown", None])
def test_only_dev_can_contribute_extraction_and_agreement(rule_id):
    split = {"dev": ["dev"], "test": ["test"], "outside": ["outside"]}
    for document in ({"extraction": [{"rule_id": rule_id, "gold": [], "extracted": []}]},
                     {"verdicts": [{"rule_id": rule_id, "user_id": "virtual", "expected": "eligible", "actual": "eligible"}]}):
        with pytest.raises(ValueError):
            score(document, split)


def test_dev_results_are_labelled_and_test_is_always_null():
    c = dict(field="age", op=">=", value=19, status="auto_verified")
    result = score({"extraction": [{"rule_id": "dev", "gold": [c], "extracted": [c]}],
                    "verdicts": [{"rule_id": "dev", "user_id": "virtual", "expected": "ineligible", "actual": "eligible"}]},
                   {"dev": ["dev"], "test": ["test"]})
    assert result["precision_auto_verified"] == {"dev": {"correct": 1, "n": 1}, "test": None, "sample": None}
    assert result["agreement"]["danger"] == 1
    assert result["evaluation_scope"] == "dev_only" and result["limitation"]
    assert score({}, {"dev": ["dev"], "test": ["test"]})["status"] == "not_evaluated"


def test_duplicate_judgments_and_extractions_cannot_inflate_counts():
    p = {"rule_id": "dev", "gold": [], "extracted": []}
    v = {"rule_id": "dev", "user_id": "virtual", "expected": "eligible", "actual": "eligible"}
    for document in ({"extraction": [p, p]}, {"verdicts": [v, v]}):
        with pytest.raises(ValueError):
            score(document, {"dev": ["dev"], "test": []})


def test_outside_metadata_objects_are_supported_and_cannot_overlap():
    split = {"dev": ["dev"], "test": ["test"], "outside": [{"id": "outside", "why": "virtual"}]}
    assert score({}, split)["status"] == "not_evaluated"
    split["outside"][0]["id"] = "dev"
    with pytest.raises(ValueError):
        score({}, split)
