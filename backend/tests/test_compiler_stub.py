"""진입점 세 개가 api.md 모양을 돌려주는지(스텁 단계부터 유지). LLM은 가짜 응답으로 바꾼다."""

import json

from backend.compiler import compile, llm, to_lines, verify
from backend.compiler.llm import LLMResult

OUT = {"rules": [{"track": "main", "name": "노인 돌봄", "subject": "parent", "domain": "elderly", "benefit_type": "service",
                  "aliases": [], "documents": [], "conditions": [
                      {"field": "age", "op": ">=", "value": 65, "income_basis": None, "as_of": None, "text": None,
                       "evidence": ["l2"], "any_of": None}]}],
       "labels": []}


def test_entrypoints_shape(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "call_json", lambda *a, **k: LLMResult(data=OUT, raw_text=json.dumps(OUT), model="m"))
    lines = to_lines("demo", "Ⅱ. 지원대상\n○ 만 65세 이상 노인")
    assert all({"id", "page", "bbox", "text", "mark"} <= set(l) for l in lines)
    rules = compile("demo", lines, "upload", raw_dir=tmp_path)
    assert rules and rules[0]["id"] == "upload:demo" and rules[0]["review"]["status"] == "unreviewed"
    for c in rules[0]["conditions"]:
        assert c["evidence"] and all(e.startswith("demo:") for e in c["evidence"])
    assert rules[0]["conditions"][0]["status"] == "auto_verified"
    assert {"coverage", "compiled", "exclusive_evidence"} <= set(rules[0])
    assert verify(rules[0], lines)["id"] == rules[0]["id"]
