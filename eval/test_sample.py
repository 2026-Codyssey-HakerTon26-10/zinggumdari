import pytest

from eval.sample import prepare


def rules(n):
    return [{"id": "ai:virtual", "source": "ai", "conditions": [
        {"field": "age", "value": i, "status": "auto_verified", "evidence": [f"virtual:l{i}"]}
        for i in range(n)]}]


def test_sampling_is_fixed_without_replacement_and_never_labels_truth():
    first = prepare(rules(60))
    assert first == prepare(rules(60))
    assert len(first["rows"]) == len({r["condition_index"] for r in first["rows"]}) == 50
    assert all(r["correct"] is None for r in first["rows"])
    changed = rules(60)
    changed[0]["conditions"][0]["value"] = -1
    assert prepare(changed)["population_sha256"] != first["population_sha256"]


def test_missing_and_non_ai_conditions_cannot_fill_sample():
    with pytest.raises(ValueError, match="50"):
        prepare([])
    manual = rules(60)
    manual[0]["source"] = "manual"
    with pytest.raises(ValueError, match="50"):
        prepare(manual)
    unverified = rules(60)
    for c in unverified[0]["conditions"]:
        c["status"] = "needs_review"
    with pytest.raises(ValueError, match="50"):
        prepare(unverified)



def test_scorer_rejects_unmarked_and_duplicate_samples():
    from eval.score import score
    sample = prepare(rules(60))
    with pytest.raises(ValueError):
        score({"sample50": sample})
    for row in sample["rows"]:
        row["correct"] = False
    result = score({"sample50": sample})
    assert result["precision_auto_verified"]["sample"]["correct"] == 0
    assert result["precision_auto_verified"]["sample"]["population_sha256"] == sample["population_sha256"]
    sample["rows"][0] = sample["rows"][1]
    with pytest.raises(ValueError, match="중복"):
        score({"sample50": sample})
