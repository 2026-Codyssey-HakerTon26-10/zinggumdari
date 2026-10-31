"""공고 투입(backend/collector, POST /ingest)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.data import config
from backend.notices import store
from backend.tests.pdf_helper import make_pdf

try:
    import pdfplumber  # noqa: F401
except ImportError:
    pdfplumber = None
needs_pdf = pytest.mark.skipif(pdfplumber is None, reason="pdfplumber가 의존성에 아직 없다")


@pytest.fixture
def notice_pdf(tmp_path):
    filler = [(72, 700 - 14 * k, f"filler line number {k} for the text layer check") for k in range(6)]
    return make_pdf(tmp_path / "src.pdf", [
        [(72, 740, "Notice for newlyweds"), (72, 720, "Applicants aged 19 to 39 with no house"), *filler],
        [(72, 740, "household income under 7500 per year"), *filler],
    ])

@needs_pdf
def test_ingest_flow_cache_and_rejects(tmp_path, notice_pdf, monkeypatch):
    from backend.app.routers import ingest as ingest_router
    from backend.collector import ingest as ing

    monkeypatch.setattr(config, "NOTICES_DIR", tmp_path / "notices")
    monkeypatch.setattr(ing, "upload_rules_dir", lambda: tmp_path / "compiled")
    monkeypatch.setattr(ing, "_after_merge", lambda ids: None)
    from backend.search.ports import ports
    monkeypatch.setattr(ports, "session_user",
                        lambda req: {"account_id": "A1", "profile_id": "U1"} if req.headers.get("x-test-login") else None)

    def fake_compile(doc_id, lines, source):
        return [{"id": f"upload:{doc_id}:newlywed", "name": "t", "conditions": [
            {"field": "age", "op": "<=", "value": 39, "evidence": [f"{doc_id}:p1-l2"], "status": "auto_verified",
             "checks": {"schema": "ok", "value": "ok"}},
            {"field": "income_couple", "op": "<=", "value": 7500, "income_basis": "absolute_annual",
             "evidence": [f"{doc_id}:p2-l1"], "status": "needs_review", "checks": {"comparator": "fail:no_comparator"}},
            {"field": "other", "text": "원문 조건 미반영", "reason": "unaccounted", "evidence": [f"{doc_id}:p1-l1"],
             "status": "needs_review"}],
            "compiled": {"model": "m", "prompt": "v1", "llm_calls": 1, "schema_retries": 0}}]

    app = FastAPI()
    app.include_router(ingest_router.router)
    c = TestClient(app, headers={"x-test-login": "1"})
    pdf = notice_pdf.read_bytes()
    anon = TestClient(app)
    assert anon.post("/ingest", files={"file": ("a.pdf", pdf, "application/pdf")}).status_code == 401

    monkeypatch.setattr(ing, "_compile", lambda: None)
    r = c.post("/ingest", files={"file": ("a.pdf", pdf, "application/pdf")})
    assert r.status_code == 503 and "연결" in r.json()["detail"]          # 읽기 없고 캐시도 없다

    monkeypatch.setattr(ing, "_compile", lambda: fake_compile)
    body = c.post("/ingest", files={"file": ("a.pdf", pdf, "application/pdf")}).json()
    log = body["log"]
    assert body["replayed"] is False and log["doc_id"].startswith("upload-") and log["rules"] == 1
    assert (log["conditions"], log["auto_verified"], log["needs_review"]) == (3, 1, 2)
    assert log["fails"][0]["check"] == "comparator" and log["fails"][0]["reason"] == "no_comparator"
    assert log["unaccounted"] == [f"{log['doc_id']}:p1-l1"] and log["model"] == "m"
    assert (tmp_path / "compiled").glob("*.json")
    assert store.load_meta(log["doc_id"])["rules"] == [body["rules"][0]["id"]]
    assert store.load_meta(log["doc_id"])["uploaded_by"] == "A1"

    replay = c.post("/ingest", files={"file": ("a.pdf", pdf, "application/pdf")}, data={"replay": "true"}).json()
    assert replay["replayed"] is True and replay["log"] == log

    def broken(*a):
        raise RuntimeError("LLM 시간 초과")
    monkeypatch.setattr(ing, "_compile", lambda: broken)
    fallback = c.post("/ingest", files={"file": ("a.pdf", pdf, "application/pdf")}).json()
    assert fallback["replayed"] is True and "시간 초과" in fallback["replay_reason"]

    assert c.post("/ingest", files={"file": ("a.hwp", b"\xd0\xcf\x11\xe0", "application/x-hwp")}).status_code == 422
    rrn = make_pdf(tmp_path / "rrn.pdf", [[(72, 700 - 14 * k, f"name 900101-1234567 line {k} more text here") for k in range(5)]])
    r = c.post("/ingest", files={"file": ("rrn.pdf", rrn.read_bytes(), "application/pdf")})
    assert r.status_code == 422 and "주민등록번호" in r.json()["detail"]
    assert not any("rrn" in p.name or p.name.endswith("-04.pdf") for p in (tmp_path / "notices").iterdir())
    assert c.post("/ingest").status_code == 400

    assert ing.delete_uploads("someone-else") == 0
    assert ing.delete_uploads("A1") == 1                                   # 탈퇴하면 올린 것 전부
    assert store.load_meta(log["doc_id"]) is None and not list((tmp_path / "compiled").glob("*.json"))
    assert not list(ing.cache_dir().glob("*.json"))
