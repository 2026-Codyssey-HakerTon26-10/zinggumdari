import hashlib
import json

import pytest

from eval.assemble import apply_grades


def test_changed_input_or_ungraded_condition_cannot_reuse_review(tmp_path):
    row = {"rule_id": "virtual", "index": 0, "correct": None}
    raw = json.dumps({"sample50": [row]}).encode()
    inp, rev = tmp_path / "input.json", tmp_path / "review.json"
    inp.write_bytes(raw)
    label = {**row, "row_sha256": hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest(), "memo": "가상 테스트"}
    review = {"input_sha256": hashlib.sha256(raw).hexdigest(), "source_commit": "virtual", "rows": [label]}
    rev.write_text(json.dumps(review))
    with pytest.raises(ValueError):
        apply_grades(inp, rev, "sample50")
    label["correct"] = False
    rev.write_text(json.dumps(review))
    assert apply_grades(inp, rev, "sample50")[0][0]["correct"] is False
    inp.write_bytes(raw + b'\n')
    with pytest.raises(ValueError, match="바뀌"):
        apply_grades(inp, rev, "sample50")
