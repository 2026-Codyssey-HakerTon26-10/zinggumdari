import json

from eval.submission import audit


def test_preflight_never_treats_missing_evaluation_as_zero(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/external-resources.md").write_text("| 자원 | (채울 것) |\n")
    result = audit(tmp_path)
    assert not result["ready"]
    assert result["evaluation_status"] == "not_evaluated"
    assert result["resource_placeholders"][0]["line"] == 1


def test_preflight_requires_real_dev_and_sample_counts(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/external-resources.md").write_text("| 자원 | 확인 |\n")
    (tmp_path / "rules/compiled").mkdir(parents=True)
    (tmp_path / "rules/compiled/r.json").write_text("{}")
    (tmp_path / "eval/personas").mkdir(parents=True)
    (tmp_path / "eval/personas/virtual.json").write_text("{}")
    p = tmp_path / "eval/results.json"
    p.write_text(json.dumps({"status": "scored", "evaluation_scope": "dev_only", "precision_auto_verified": {"dev": None, "test": None, "sample": None}}))
    assert not audit(tmp_path, team_name="가상팀", authors_confirmed=True)["ready"]
    assert not audit(tmp_path, team_name="../팀", authors_confirmed=True)["ready"]


def test_confirmed_team_requires_five_distinct_accounts(tmp_path):
    import pytest
    from eval.submission import load_team
    p = tmp_path / "team.json"
    team = {"team_name": "가상팀", "members": [{"github": f"virtual{i}", "name": f"가상{i}"} for i in range(5)]}
    p.write_text(json.dumps(team))
    assert len(load_team(p)["members"]) == 5
    team["members"][1]["github"] = "VIRTUAL0"
    p.write_text(json.dumps(team))
    with pytest.raises(ValueError):
        load_team(p)
