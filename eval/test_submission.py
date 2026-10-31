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


def ready_fixture(root):
    from pathlib import Path
    from eval.assemble import input_hashes
    from eval.provenance import engine_digest, scorer_digest, digest_files
    import hashlib
    files = {
        'docs/external-resources.md': '| 가상 자원 | 확인됨 |',
        'rules/compiled/a.json': '{"review":{"status":"reviewed"}}',
        'rules/compiled/b.json': '{"review":{"status":"reviewed"}}',
        'eval/personas/virtual.json': '{"virtual":true}',
        'eval/score.py': '# virtual scorer', 'eval/assemble.py': '# virtual assemble',
        'backend/engine/__init__.py': '# virtual engine',
        'backend/search/corpus.py': '# virtual corpus',
    }
    for name in ('score_input.json', 'sample50.json', 'verifier_dev.json'):
        files['eval/' + name] = '{}'
    for name in ('sample50.json', 'verifier_dev.json'):
        files['eval/reviews/' + name] = '{}'
    for name, contents in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contents)
    results = {'status': 'scored', 'evaluation_scope': 'dev_only',
               'precision_auto_verified': {'dev': {'n': 1, 'correct': 0}, 'test': None, 'sample': {'n': 50, 'correct': 0}},
               'agreement': {'households': 1}, 'agreement_source': {'engine_sha256': engine_digest(root)},
               'scorer_sha256': scorer_digest(root),
               'source_snapshot': {'inputs_sha256': input_hashes(root / 'eval'),
                   'review_sha256': {name: hashlib.sha256((root / 'eval/reviews' / name).read_bytes()).hexdigest()
                                    for name in ('sample50.json', 'verifier_dev.json')}}}
    (root / 'eval/results.json').write_text(json.dumps(results))
    safety = {'n': 1, 'passed': 1, 'danger': 0, 'engine_sha256': engine_digest(root),
              'personas_sha256': digest_files(root / 'eval/personas', [Path('virtual.json')])}
    (root / 'eval/persona-results.json').write_text(json.dumps(safety))
    (root / 'eval/explore-results.json').write_text(json.dumps({'purpose': 'test', 'precision_at_5': 0}))


def test_stale_input_and_engine_cannot_pass_submission(tmp_path):
    ready_fixture(tmp_path)
    assert audit(tmp_path, team_name='가상팀', authors_confirmed=True)['ready']
    (tmp_path / 'eval/score_input.json').write_text('{"changed":true}')
    assert not audit(tmp_path, team_name='가상팀', authors_confirmed=True)['ready']
    (tmp_path / 'backend/engine/__init__.py').write_text('# changed engine')
    assert any('엔진' in s for s in audit(tmp_path, team_name='가상팀', authors_confirmed=True)['issues'])


def test_failed_safety_and_missing_knn_cannot_pass_submission(tmp_path):
    ready_fixture(tmp_path)
    p = tmp_path / 'eval/persona-results.json'
    safety = json.loads(p.read_text())
    safety['danger'] = 1
    p.write_text(json.dumps(safety))
    (tmp_path / 'eval/explore-results.json').unlink()
    issues = audit(tmp_path, team_name='가상팀', authors_confirmed=True)['issues']
    assert any('안전성' in s for s in issues)
    assert any('KNN' in s for s in issues)
