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
    monkeypatch.setattr(ing, "_after_merge", lambda ids, account_id=None: None)
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


@pytest.fixture
def world(tmp_path, monkeypatch):
    from backend.collector import ingest as ing
    monkeypatch.setattr(config, "NOTICES_DIR", tmp_path / "notices")
    monkeypatch.setattr(ing, "upload_rules_dir", lambda: tmp_path / "uploads")
    monkeypatch.setattr(ing, "_after_merge", lambda ids, account_id=None: None)

    def fake_compile(doc_id, lines, source):
        return [{"id": f"upload:{doc_id}:x", "name": "t", "conditions": []}]
    monkeypatch.setattr(ing, "_compile", lambda: fake_compile)
    return ing


@needs_pdf
def test_doc_ids_do_not_collide_after_delete(tmp_path, world):
    ing = world
    pdfs = {n: make_pdf(tmp_path / f"{n}.pdf", [[(72, 700 - 14 * k, f"{n} notice line {k} with enough text") for k in range(5)]])
            for n in ("alice", "bob", "carol")}
    ids = {}
    for n in ("alice", "bob"):
        ids[n] = ing.ingest(pdfs[n], f"{n}.pdf", uploaded_by=n)["log"]["doc_id"]
    assert ing.delete_uploads("alice") == 1
    ids["carol"] = ing.ingest(pdfs["carol"], "carol.pdf", uploaded_by="carol")["log"]["doc_id"]
    assert ids["carol"] != ids["bob"]
    bob = store.load_meta(ids["bob"])
    assert bob["uploaded_by"] == "bob" and bob["title"] == "bob"           # bob 것은 그대로
    assert (tmp_path / "uploads").is_dir() and len(list((tmp_path / "uploads").glob("*.json"))) == 2


@needs_pdf
def test_failed_read_leaves_nothing(tmp_path, world, notice_pdf, monkeypatch):
    ing = world

    def broken(*a):
        raise RuntimeError("LLM 시간 초과")
    monkeypatch.setattr(ing, "_compile", lambda: broken)
    with pytest.raises(RuntimeError):
        ing.ingest(notice_pdf, "a.pdf", uploaded_by="dave")
    assert store.list_doc_ids() == []                                       # 원문이 남지 않는다

    monkeypatch.setattr(ing, "_compile", lambda: lambda *a: [{"id": "upload:x:y", "conditions": []}])
    first = ing.ingest(notice_pdf, "a.pdf", uploaded_by="dave")              # 캐시를 만든다
    monkeypatch.setattr(ing, "_compile", lambda: broken)
    again = ing.ingest(notice_pdf, "a.pdf", uploaded_by="erin")
    assert again["replayed"] is True
    assert store.list_doc_ids() == [first["log"]["doc_id"]]                 # 캐시 재생 때도 새 원문은 지운다
    assert store.load_meta(first["log"]["doc_id"])["uploaded_by"] == "dave"


def test_fetch_url_blocks_internal_and_caps_size(monkeypatch):
    import httpx

    from backend.collector import ingest as ing

    for bad in ["http://localhost/a.pdf", "http://127.0.0.1/a.pdf", "http://10.0.0.5/a.pdf",
                "http://169.254.169.254/latest", "http://[::1]/a.pdf", "ftp://8.8.8.8/a.pdf"]:
        with pytest.raises(ing.Rejected):
            ing.fetch_url(bad, transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"%PDF-")))

    redirect = httpx.MockTransport(lambda r: httpx.Response(302, headers={"location": "http://192.168.0.1/x.pdf"}))
    with pytest.raises(ing.Rejected, match="내부"):
        ing.fetch_url("http://8.8.8.8/a.pdf", transport=redirect)

    monkeypatch.setattr(ing, "MAX_BYTES", 1000)
    big = httpx.MockTransport(lambda r: httpx.Response(200, content=b"%PDF-" + b"x" * 5000))
    with pytest.raises(ing.Rejected, match="너무 큽니다"):
        ing.fetch_url("http://8.8.8.8/a.pdf", transport=big)

    ok = httpx.MockTransport(lambda r: httpx.Response(200, content=b"%PDF-1.4 small"))
    assert ing.fetch_url("http://8.8.8.8/a.pdf", transport=ok) == b"%PDF-1.4 small"


@needs_pdf
def test_upload_visible_only_to_owner(tmp_path, world, notice_pdf, monkeypatch):
    from backend.app.routers import notices as notices_router
    from backend.search.ports import ports

    ing = world
    monkeypatch.setattr(ing, "_compile", lambda: lambda doc_id, lines, source: [{"id": "upload:same-id", "conditions": []}])
    a = ing.ingest(notice_pdf, "a.pdf", uploaded_by="A1")["log"]["doc_id"]
    b = ing.ingest(make_pdf(tmp_path / "b.pdf", [[(72, 700 - 14 * k, f"other notice line {k} with text") for k in range(5)]]),
                   "b.pdf", uploaded_by="B1")["log"]["doc_id"]
    files = sorted(p.name for p in (tmp_path / "uploads").glob("*.json"))
    assert len(files) == 2 and files[0].startswith(min(a, b))               # 같은 id여도 파일이 따로 남는다

    store.register_text("○ 무주택 세대주", "web-doc", "web", "https://example.org", "공개 원문", notices_dir=None)
    monkeypatch.setattr(ports, "session_user",
                        lambda req: {"account_id": acc, "profile_id": "p"} if (acc := req.headers.get("x-acc")) else None)
    app = FastAPI()
    app.include_router(notices_router.router)
    c = TestClient(app)
    assert [m["doc_id"] for m in c.get("/notices").json()] == ["web-doc"]   # 로그인 안 하면 공개 원문만
    mine = c.get("/notices", headers={"x-acc": "A1"}).json()
    assert sorted(m["doc_id"] for m in mine) == sorted([a, "web-doc"]) and all("uploaded_by" not in m for m in mine)
    assert c.get(f"/notices/{a}", headers={"x-acc": "B1"}).status_code == 404
    assert c.get(f"/notices/{a}/file", headers={"x-acc": "B1"}).status_code == 404
    assert c.get(f"/notices/{a}/file").status_code == 404
    own = c.get(f"/notices/{a}", headers={"x-acc": "A1"})
    assert own.status_code == 200 and "uploaded_by" not in own.json()
    assert c.get(f"/notices/{a}/file", headers={"x-acc": "A1"}).status_code == 200

    assert ing.delete_uploads("A1") == 1
    assert len(list((tmp_path / "uploads").glob("*.json"))) == 1             # B1 조건표는 남는다


@needs_pdf
def test_raw_responses_deleted_on_withdraw_and_failure(tmp_path, world, monkeypatch):
    """컴파일러 원응답(rules/uploads/_raw)도 탈퇴와 읽기 실패 때 같이 지운다(#5 delete_raw)."""
    ing = world
    gone = []
    monkeypatch.setattr(ing, "_delete_raw", gone.append)
    pdf = make_pdf(tmp_path / "a.pdf", [[(72, 700 - 14 * k, f"notice line {k} with enough text here") for k in range(5)]])
    doc_id = ing.ingest(pdf, "a.pdf", uploaded_by="A1")["log"]["doc_id"]
    assert ing.delete_uploads("A1") == 1 and gone == [doc_id]

    def broken(*a):
        raise RuntimeError("LLM 시간 초과")
    monkeypatch.setattr(ing, "_compile", lambda: broken)
    pdf2 = make_pdf(tmp_path / "b.pdf", [[(72, 700 - 14 * k, f"other notice line {k} with text") for k in range(5)]])
    with pytest.raises(RuntimeError):
        ing.ingest(pdf2, "b.pdf", uploaded_by="A1")
    assert len(gone) == 2 and gone[1].startswith("upload-") and gone[1] != doc_id


@needs_pdf
def test_raw_responses_deleted_with_real_compiler(tmp_path, world, monkeypatch):
    """#5가 합쳐진 상태에서 실제 pipeline.delete_raw로 rules/uploads/_raw의 원응답과 글자 인식 캐시가 지워진다.

    #5 전에는 건너뛴다. LLM 대신 compile이 원응답을 남기는 것만 흉내 낸다.
    """
    pipeline = pytest.importorskip("backend.compiler.pipeline")
    ing = world
    raw = tmp_path / "uploads_raw"
    raw.mkdir()
    monkeypatch.setattr(pipeline, "UPLOAD_RAW_DIR", raw)

    def compile_leaving_raw(doc_id, lines, source):
        for suffix in (".json", ".ocr.json"):
            (raw / f"{doc_id}{suffix}").write_text("{}")
        return [{"id": f"upload:{doc_id}:x", "name": "t", "conditions": []}]
    monkeypatch.setattr(ing, "_compile", lambda: compile_leaving_raw)
    pdf = make_pdf(tmp_path / "a.pdf", [[(72, 700 - 14 * k, f"notice line {k} with enough text here") for k in range(5)]])
    ing.ingest(pdf, "a.pdf", uploaded_by="A1")
    assert len(list(raw.iterdir())) == 2
    assert ing.delete_uploads("A1") == 1 and list(raw.iterdir()) == []      # 탈퇴

    def compile_then_fail(doc_id, lines, source):
        (raw / f"{doc_id}.json").write_text("{}")
        raise RuntimeError("LLM 시간 초과")
    monkeypatch.setattr(ing, "_compile", lambda: compile_then_fail)
    pdf2 = make_pdf(tmp_path / "b.pdf", [[(72, 700 - 14 * k, f"other notice line {k} with text") for k in range(5)]])
    with pytest.raises(RuntimeError):
        ing.ingest(pdf2, "b.pdf", uploaded_by="A1")
    assert list(raw.iterdir()) == []                                          # 읽기 실패


def test_after_merge_passes_uploader_only(monkeypatch):
    """업로드 알림은 올린 계정만 다시 판정한다. 알림 쪽이 계정을 못 받으면 부르지 않는다."""
    import sys
    import types

    from backend.collector import ingest as ing
    calls = []
    mod = types.ModuleType("backend.notify.api")

    def rebuild_with_account(*, rule_ids, today=None, account_id=None):
        calls.append((rule_ids, account_id))
        return {"notifications": 1}
    mod.rebuild = rebuild_with_account
    monkeypatch.setitem(sys.modules, "backend.notify.api", mod)
    assert ing._after_merge(["upload:x"], account_id="A1") == {"notifications": 1}
    assert calls == [(["upload:x"], "A1")]
    assert ing._after_merge(["upload:x"], account_id=None)["status"] == "skipped"   # 계정을 모르면 전체로 보내지 않는다
    assert len(calls) == 1

    def rebuild_old(*, rule_ids, today=None):
        calls.append("everyone")
    mod.rebuild = rebuild_old
    assert ing._after_merge(["upload:x"], account_id="A1")["status"] == "skipped"
    assert calls[-1] != "everyone"
