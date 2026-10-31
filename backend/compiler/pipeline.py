"""compile(): 자격 구간 → LLM 1회 → 검증기 → 빠짐 검사(SPEC §9.2). 스텁: api.md §1 AI 조건표 예시를 돌려준다."""

from __future__ import annotations


def compile(doc_id: str, lines: list[dict], source: str = "upload") -> list[dict]:
    return [{
        "id": f"{source}:{doc_id}:newlywed", "source": source, "name": "(스텁) 신혼부부 특별공급", "org": None,
        "region": None, "domain": "subscription", "subject": "self", "benefit_type": "discount", "aliases": [],
        "conditions": [
            {"field": "subscription_months", "op": ">=", "value": 6, "as_of": "notice_date", "evidence": [f"{doc_id}:p7-l23"],
             "status": "auto_verified", "checks": {"schema": "ok", "evidence": "ok", "value": "ok", "comparator": "ok", "unit": "ok", "keyword": "ok", "pair": "ok", "layer": "ok"}},
            {"field": "income_couple", "op": "<=", "value": 120, "income_basis": "urban_worker_pct", "evidence": [f"{doc_id}:p8-l4"],
             "status": "needs_review", "checks": {"schema": "ok", "evidence": "ok", "value": "ok", "comparator": "fail:no_comparator", "unit": "ok", "keyword": "ok", "pair": "ok", "layer": "ok"}},
            {"field": "other", "text": "원문 조건 미반영", "reason": "unaccounted", "evidence": [f"{doc_id}:p8-l9"], "status": "needs_review"},
        ],
        "exclusive_evidence": [], "documents": [], "detail_url": None, "updated": None,
        "review": {"status": "unreviewed"},
        "coverage": {"marked": 3, "used": 2, "labeled": {"definition": 0, "procedure": 0, "exclusive": 0, "out_of_scope": 0, "not_condition": 0}, "unaccounted": 1},
        "compiled": {"model": "stub", "prompt": "stub", "doc_sha256": None, "raw": None, "at": None},
    }]
