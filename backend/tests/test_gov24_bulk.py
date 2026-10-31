"""정부24 대량 추출(backend/compiler/gov24_bulk.py)."""

import json

from backend.compiler import gov24_bulk as bulk
from backend.data import config


def test_one_registers_text_and_keeps_service_id_case(tmp_path, monkeypatch):
    """원문은 소문자 doc_id로 등록하고, 조건표 id는 덤프 서비스 id의 대소문자로 되돌린다."""
    monkeypatch.setattr(config, "NOTICES_DIR", tmp_path / "notices")
    seen = {}

    def fake_compile(doc_id, lines, source, **kw):
        seen.update(doc_id=doc_id, source=source, lines=[l["text"] for l in lines], meta=kw["meta"])
        return [{"id": f"gov24:{doc_id[6:]}:youth", "conditions": [{"field": "age", "op": ">=", "value": 19}]}]
    monkeypatch.setattr(bulk, "compile", fake_compile)
    item = {"서비스ID": "WII000001", "서비스명": "청년 제도", "지원대상": "만 19세 이상 청년", "선정기준": "", "신청기한": "상시"}
    meta = {"소관기관명": "서울특별시", "소관기관유형": "광역시도", "상세조회URL": "https://example.org/1"}
    out = tmp_path / "compiled"
    assert bulk.one(item, meta, out_dir=out, raw_dir=tmp_path / "raw") == 1
    assert seen["doc_id"] == "gov24-wii000001" and seen["source"] == "gov24"
    assert seen["lines"][:2] == ["[지원대상]", "만 19세 이상 청년"] and "[선정기준]" not in seen["lines"]   # 빈 칸은 넣지 않는다
    assert seen["meta"]["region"] == {"sido": "서울", "sigungu": None}
    written = json.loads((out / "gov24__WII000001__youth.json").read_text(encoding="utf-8"))
    assert written["id"] == "gov24:WII000001:youth"


def test_reviewed_rules_are_detected(tmp_path):
    """--cache-only는 사람이 검수한 조건표를 덮어쓰지 않는다."""
    (tmp_path / "gov24__X1__youth.json").write_text(json.dumps({"review": {"status": "reviewed"}}), encoding="utf-8")
    (tmp_path / "gov24__X2.json").write_text(json.dumps({"review": {"status": "unreviewed"}}), encoding="utf-8")
    assert bulk._reviewed(bulk._files(tmp_path, "X1")) and not bulk._reviewed(bulk._files(tmp_path, "X2"))
    assert bulk._files(tmp_path, "X") == []   # 앞부분만 같은 다른 id의 파일은 고르지 않는다
