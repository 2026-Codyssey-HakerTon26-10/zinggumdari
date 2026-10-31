"""진입점 세 개가 api.md 모양을 돌려주는지(스텁 단계부터 유지)."""

from backend.compiler import compile, to_lines, verify


def test_entrypoints_shape():
    lines = to_lines("demo", "x")
    assert all({"id", "page", "bbox", "text", "mark"} <= set(l) for l in lines)
    rules = compile("demo", lines, "upload")
    assert rules and rules[0]["review"]["status"] == "unreviewed"
    for c in rules[0]["conditions"]:
        assert c["evidence"] and all(e.startswith("demo:") for e in c["evidence"])
    assert verify(rules[0], lines)["id"] == rules[0]["id"]
