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
    rlog = replay["log"]
    assert replay["replayed"] is True and rlog["doc_id"] != log["doc_id"]      # 지금 올린 계정 앞으로 새 원문
    import json as _json
    assert rlog == _json.loads(_json.dumps(log).replace(log["doc_id"], rlog["doc_id"]))   # 같은 화면, 원문 ID만 새것
    assert rlog["unaccounted"] == [f"{rlog['doc_id']}:p1-l1"]                  # 근거 줄도 새 원문을 가리킨다
    assert replay["rules"][0]["id"] == f"upload:{rlog['doc_id']}:newlywed"
    assert store.load_meta(rlog["doc_id"])["rules"] == [replay["rules"][0]["id"]]   # 카드에 합류
    assert "replay_warning" not in replay

    def broken(*a):
        raise RuntimeError("LLM 시간 초과")
    monkeypatch.setattr(ing, "_compile", lambda: broken)
    fallback = c.post("/ingest", files={"file": ("a.pdf", pdf, "application/pdf")}).json()
    assert fallback["replayed"] is True and "시간 초과" in fallback["replay_reason"]
    assert store.load_meta(fallback["log"]["doc_id"])["uploaded_by"] == "A1"

    assert c.post("/ingest", files={"file": ("a.hwp", b"\xd0\xcf\x11\xe0", "application/x-hwp")}).status_code == 422
    rrn = make_pdf(tmp_path / "rrn.pdf", [[(72, 700 - 14 * k, f"name 900101-1234567 line {k} more text here") for k in range(5)]])
    r = c.post("/ingest", files={"file": ("rrn.pdf", rrn.read_bytes(), "application/pdf")})
    assert r.status_code == 422 and "주민등록번호" in r.json()["detail"]
    assert not any("rrn" in p.name or p.name.endswith("-04.pdf") for p in (tmp_path / "notices").iterdir())
    assert c.post("/ingest").status_code == 400

    assert ing.delete_uploads("someone-else") == 0
    assert ing.delete_uploads("A1") == 3                                   # 탈퇴하면 올린 것 전부(새로 읽기, 재생 둘)
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
    assert store.load_meta(again["log"]["doc_id"])["uploaded_by"] == "erin"    # 재생한 원문은 erin 것으로 남는다
    assert store.load_meta(first["log"]["doc_id"])["uploaded_by"] == "dave"
    assert ing.delete_uploads("erin") == 1 and store.list_doc_ids() == [first["log"]["doc_id"]]


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


def test_ingest_checks_login_and_size_before_reading_body(monkeypatch):
    """로그인하지 않았으면 본문을 받기 전에 401, 상한을 넘는 본문은 받다가 413."""
    from backend.app.routers import ingest as ingest_router
    from backend.search.ports import ports

    read = []
    real = ingest_router._read_form

    async def spy(request):
        read.append(1)
        return await real(request)

    monkeypatch.setattr(ingest_router, "_read_form", spy)
    monkeypatch.setattr(ingest_router, "MAX_BYTES", 1000)
    monkeypatch.setattr(ingest_router, "FORM_SLACK", 100)
    monkeypatch.setattr(ports, "session_user", lambda req: {"account_id": "A1"} if req.headers.get("x-test-login") else None)
    app = FastAPI()
    app.include_router(ingest_router.router)
    big = {"file": ("a.pdf", b"%PDF-" + b"x" * 5000, "application/pdf")}

    assert TestClient(app).post("/ingest", files=big).status_code == 401
    assert read == []                                                   # 본문을 열어 보지도 않았다
    c = TestClient(app, headers={"x-test-login": "1"})
    assert c.post("/ingest", files=big).status_code == 413              # Content-Length로 바로 끊는다
    chunks = iter([b"x" * 600, b"x" * 600])
    assert c.post("/ingest", content=chunks, headers={"content-type": "multipart/form-data; boundary=b"}).status_code == 413
    assert c.post("/ingest", data={"replay": "true"}).status_code == 400   # 파일도 URL도 없다


def test_fetch_url_connects_to_checked_ip(monkeypatch):
    """DNS 재바인딩: 검사할 때는 공개 IP, 접속할 때는 127.0.0.1을 주는 이름. 검사한 IP로만 접속해야 한다."""
    import socket

    import httpx

    from backend.collector import ingest as ing

    answers = iter(["8.8.8.8", "127.0.0.1", "127.0.0.1"])
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, *a, **k: [(2, 1, 6, "", (next(answers), port))])
    seen = []

    def handler(req):
        seen.append((req.url.host, req.headers["host"], req.extensions.get("sni_hostname")))
        return httpx.Response(200, content=b"%PDF-1.4 ok")

    assert ing.fetch_url("https://notice.example.kr/a.pdf", transport=httpx.MockTransport(handler)) == b"%PDF-1.4 ok"
    assert seen == [("8.8.8.8", "notice.example.kr", "notice.example.kr")]


def test_fetch_url_blocks_nat64_and_stops_at_total_time(monkeypatch):
    import httpx

    from backend.collector import ingest as ing

    with pytest.raises(ing.Rejected, match="내부"):
        ing.fetch_url("http://[64:ff9b::7f00:1]/a.pdf",
                      transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"%PDF-")))

    monkeypatch.setattr(ing, "FETCH_SECONDS", -1)   # 이미 시간이 다 지난 것처럼
    slow = httpx.MockTransport(lambda r: httpx.Response(200, content=iter([b"%PDF-", b"x"])))
    with pytest.raises(ing.Rejected, match="오래"):
        ing.fetch_url("http://8.8.8.8/a.pdf", transport=slow)


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


@needs_pdf
def test_rules_and_evidence_are_scoped_to_uploader(tmp_path, world, notice_pdf, monkeypatch):
    """A의 업로드가 B의 판정과 근거 줄에 섞이지 않는다(#14 리뷰)."""
    from backend.data.rules import load_rules

    ing = world
    monkeypatch.setattr(config, "UPLOAD_RULES_DIR", tmp_path / "uploads")
    monkeypatch.setattr(config, "RULES_DIRS", (tmp_path / "manual",))
    (tmp_path / "manual").mkdir()
    (tmp_path / "manual" / "m.json").write_text('{"id": "manual:x", "conditions": []}')
    monkeypatch.setattr(ing, "_compile", lambda: lambda doc_id, lines, source: [
        {"id": f"upload:{doc_id}:y", "conditions": [{"field": "age", "evidence": [f"{doc_id}:p1-l1"]}]}])
    a = ing.ingest(notice_pdf, "a.pdf", uploaded_by="A1")["log"]["doc_id"]
    other = make_pdf(tmp_path / "b.pdf", [[(72, 700 - 14 * k, f"other notice line {k} with text") for k in range(5)]])
    b = ing.ingest(other, "b.pdf", uploaded_by="B1")["log"]["doc_id"]

    assert [r["id"] for r in load_rules()] == ["manual:x"]                          # 기본은 업로드 없음
    assert sorted(r["id"] for r in load_rules(owner="A1")) == ["manual:x", f"upload:{a}:y"]
    assert f"upload:{b}:y" not in {r["id"] for r in load_rules(owner="A1")}

    eid = f"{a}:p1-l1"
    assert store.evidence([eid], owner="A1")[0]["text"] == "Notice for newlyweds"
    assert store.evidence([eid], owner="B1")[0] == {"id": eid, "page": None, "bbox": None, "text": None}
    assert store.evidence([eid])[0]["text"] is None


@needs_pdf
def test_replay_reverifies_when_lines_changed(tmp_path, world, notice_pdf, monkeypatch):
    """캐시를 만들 때와 줄 목록이 다르면 캐시의 상태를 쓰지 않고 검증기를 다시 돌린다(#20 리뷰)."""
    import importlib
    import json as _json

    verify_mod = importlib.import_module("backend.compiler.verify")   # 패키지가 같은 이름의 함수를 내보내서 모듈로 집는다

    ing = world
    monkeypatch.setattr(ing, "_compile", lambda: lambda doc_id, lines, source: [
        {"id": f"upload:{doc_id}:x", "conditions": [
            {"field": "age", "op": "<=", "value": 39, "evidence": [f"{doc_id}:p1-l2"], "status": "auto_verified"},
            {"field": "is_homeless", "op": "==", "value": "Y", "evidence": [f"{doc_id}:p1-l2"], "status": "reviewed"}]}])
    first = ing.ingest(notice_pdf, "a.pdf", uploaded_by="A1")
    cache = next(ing.cache_dir().glob("*.json"))
    assert _json.loads(cache.read_text())["lines_fp"] == ing.lines_fingerprint(store.load_lines(first["log"]["doc_id"]))

    calls = []

    def fake_verify(rule, lines, **kw):
        calls.append(len(lines))
        out = _json.loads(_json.dumps(rule))
        for c in out["conditions"]:
            if c["status"] != "reviewed":
                c["status"] = "needs_review"
        return out
    monkeypatch.setattr(verify_mod, "verify", fake_verify)

    same = ing.ingest(notice_pdf, "a.pdf", replay=True, uploaded_by="B1")       # 줄 목록이 같으면 그대로
    assert calls == [] and "replay_warning" not in same
    assert same["rules"][0]["conditions"][0]["status"] == "auto_verified"

    data = _json.loads(cache.read_text())
    cache.write_text(_json.dumps({**data, "lines_fp": "줄 만들기가 바뀜"}, ensure_ascii=False))
    changed = ing.ingest(notice_pdf, "a.pdf", replay=True, uploaded_by="C1")
    assert calls and "검증기" in changed["replay_warning"]
    conds = changed["rules"][0]["conditions"]
    assert [c["status"] for c in conds] == ["needs_review", "reviewed"]           # 사람이 확인한 조건은 그대로
    assert changed["log"]["needs_review"] == 1 and changed["log"]["auto_verified"] == 0

    data.pop("lines_fp")
    cache.write_text(_json.dumps(data, ensure_ascii=False))                       # 지문이 없는 옛 캐시도 다시 검사
    calls.clear()
    assert "replay_warning" in ing.ingest(notice_pdf, "a.pdf", replay=True, uploaded_by="D1") and calls


def test_ingest_accepts_text_and_passes_meta(tmp_path, world, monkeypatch):
    """줄 만들기를 compiler.lines로 바꿔서 텍스트도 받는다. 원문 머리는 compile(meta=)로 넘긴다."""
    ing = world
    seen = {}

    def compile_with_meta(doc_id, lines, source, *, meta=None):
        seen["meta"], seen["lines"] = meta, lines
        return [{"id": f"upload:{doc_id}:x", "conditions": []}]
    monkeypatch.setattr(ing, "_compile", lambda: compile_with_meta)
    src = tmp_path / "notice.txt"
    src.write_text("○ 지원대상\n - 만 19세 이상 39세 이하 무주택 세대주\n", encoding="utf-8")
    out = ing.ingest(src, "notice.txt", uploaded_by="A1")
    assert out["replayed"] is False and seen["meta"]["kind"] == "text" and seen["meta"]["uploaded_by"] == "A1"
    assert seen["meta"]["unread_pages"] == [] and [ln["id"] for ln in seen["lines"]] == ["l1", "l2"]
    bad = tmp_path / "bin.dat"
    bad.write_bytes(b"\x00\x01\x02 binary")
    with pytest.raises(ing.Rejected):
        ing.ingest(bad, "bin.dat", uploaded_by="A1")
