import pytest

from eval.personas import evaluate


def test_persona_runner_reports_mismatch_without_changing_gold():
    p = {"id": "virtual", "virtual": True, "today": "2026-11-01", "profile": {},
         "expected": {"rule_id": "manual:virtual", "allowed_verdicts": ["ineligible"], "evidence": ["virtual:l1"]}}
    out = evaluate([p], [{"id": "manual:virtual"}], lambda *a, **k: {"manual:virtual": {"verdict": "eligible"}})
    assert out["n"] == 1 and out["passed"] == 0 and out["danger"] == 1
    assert p["expected"]["allowed_verdicts"] == ["ineligible"]
    p["virtual"] = False
    with pytest.raises(ValueError):
        evaluate([p], [{"id": "manual:virtual"}], lambda *a, **k: {})
