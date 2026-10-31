"""원문과 줄 목록(backend/notices), 원문 보기 API."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import notices as notices_router
from backend.data import config
from backend.notices import store
from backend.notices.lh import file_kind, find_attachments
from backend.notices.lines import find_quote, html_to_text, split_text, text_lines, to_lines
from backend.tests.pdf_helper import make_pdf

PROSE = """○ 지원대상
 - 대출신청일 현재 민법상 성년인 세대주로서 대출대상주택 임차계약을 체결하고 임차보증금의 5% 이상을 지불한 자
 - 부부합산 연소득 7천 5백만 원 이하 ※ 신혼가구는 혼인기간 7년 이내
신청 방법은 은행 창구"""


def test_split_text_on_newline_and_bullets():
    assert split_text(PROSE) == [
        "○ 지원대상",
        "- 대출신청일 현재 민법상 성년인 세대주로서 대출대상주택 임차계약을 체결하고 임차보증금의 5% 이상을 지불한 자",
        "- 부부합산 연소득 7천 5백만 원 이하",
        "※ 신혼가구는 혼인기간 7년 이내",
        "신청 방법은 은행 창구",
    ]
    assert split_text("2026-03-30 ~ 2026-05-29") == ["2026-03-30 ~ 2026-05-29"]   # 날짜의 -는 끊지 않는다


def test_text_lines_ids_and_marks():
    lines = text_lines(PROSE)
    assert [ln["id"] for ln in lines] == ["l1", "l2", "l3", "l4", "l5"]
    assert [ln["mark"] for ln in lines] == [False, True, True, True, False]
    assert lines[0]["page"] is None and lines[0]["bbox"] is None
    assert to_lines("x", PROSE) == lines                         # 경로가 아니면 산문으로 본다


def test_html_to_text_drops_script_and_nav():
    html = "<html><head><title>t</title><script>var x=1</script></head><body><nav>메뉴</nav>" \
           "<div><p>대출대상</p><ul><li>무주택 세대주</li><li>연소득 5천만원 이하</li></ul></div></body></html>"
    assert split_text(html_to_text(html)) == ["대출대상", "무주택 세대주", "연소득 5천만원 이하"]


def test_find_quote_across_lines():
    lines = text_lines(PROSE)
    assert find_quote(lines, "연소득 7천5백만 원 이하※신혼가구는") == ["l3", "l4"]
    assert find_quote(lines, "혼인기간 7년 이내") == ["l4"]
    assert find_quote(lines, "혼인기간 5년 이내") == []


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
def test_pdf_lines_ids_bbox_marks(tmp_path, notice_pdf):
    meta = store.register(notice_pdf, "t-1", "applyhome", "https://example.org/a.pdf", "t", "2026-10-31", notices_dir=tmp_path)
    assert meta["kind"] == "pdf" and meta["pages"] == 2 and len(meta["sha256"]) == 64
    lines = store.load_lines("t-1", tmp_path)
    first = lines[0]
    assert first["id"] == "p1-l1" and first["text"] == "Notice for newlyweds" and first["page"] == 1
    x0, top, x1, bottom = first["bbox"]
    assert 70 < x0 < 74 and top < bottom < 60                    # 왼쪽 위 원점이라 위쪽 줄은 top이 작다
    assert [ln["id"] for ln in lines if ln["page"] == 2][0] == "p2-l1"
    assert find_quote(lines, "aged 19 to 39") == ["p1-l2"]


@needs_pdf
def test_scan_and_hwp_rejected(tmp_path):
    scan = make_pdf(tmp_path / "scan.pdf", [[(72, 700, "x")]])
    with pytest.raises(ValueError, match="스캔"):
        store.register(scan, "scan", "lh", None, "t", notices_dir=tmp_path)
    hwp = tmp_path / "a.hwp"
    hwp.write_bytes(b"\xd0\xcf\x11\xe0 hwp")
    with pytest.raises(ValueError, match="HWP"):
        store.register(hwp, "hwp", "lh", None, "t", notices_dir=tmp_path)


def test_doc_id_rules():
    for good in ["nhuf-newlywed-jeonse", "lh-2026000123", "gov24-wii000001"]:
        assert store.valid_doc_id(good)
    for bad in ["../etc", "a/b", "", "gov24:WII", "Upper"]:
        assert not store.valid_doc_id(bad)


def test_evidence_resolves_ids(tmp_path):
    store.register_text(PROSE, "nhuf-test", "web", "https://nhuf.molit.go.kr/x", "t", notices_dir=tmp_path)
    ev = store.evidence(["nhuf-test:l4", "nhuf-test:l99", "nope:l1"], tmp_path)
    assert ev[0] == {"id": "nhuf-test:l4", "page": None, "bbox": None, "text": "※ 신혼가구는 혼인기간 7년 이내"}
    assert ev[1]["text"] is None and ev[2]["text"] is None


@needs_pdf
def test_notices_api(tmp_path, notice_pdf, monkeypatch):
    monkeypatch.setattr(config, "NOTICES_DIR", tmp_path)
    store.register(notice_pdf, "demo-pdf", "applyhome", "https://example.org/a.pdf", "시연 공고", "2026-10-31")
    store.register_text(PROSE, "demo-web", "web", "https://example.org/w", "웹 원문", "2026-10-31")
    app = FastAPI()
    app.include_router(notices_router.router)
    c = TestClient(app)
    pdf = c.get("/notices/demo-pdf").json()
    assert pdf["kind"] == "pdf" and pdf["lines"] is None and pdf["fetched_at"] == "2026-10-31"
    web = c.get("/notices/demo-web").json()
    assert web["kind"] == "text" and web["lines"][3]["id"] == "l4"
    f = c.get("/notices/demo-pdf/file")
    assert f.status_code == 200 and f.headers["content-type"] == "application/pdf" and f.content[:5] == b"%PDF-"
    assert c.get("/notices/demo-web/file").headers["content-type"].startswith("text/plain")
    assert c.get("/notices/nope").status_code == 404 and c.get("/notices/A:B").status_code == 404
    assert sorted(m["doc_id"] for m in c.get("/notices").json()) == ["demo-pdf", "demo-web"]


def test_lh_attachments_pick_pdf_not_hwp():
    detail = [{"dsSch": [{"PAN_ID": "1"}]}, {"dsAhflInfo": [
        {"SL_PAN_AHFL_DS_CD_NM": "공고문(PDF)", "CMN_AHFL_NM": "모집공고.pdf", "AHFL_URL": "https://apply.lh.or.kr/f?id=1"},
        {"SL_PAN_AHFL_DS_CD_NM": "공고문(HWP)", "CMN_AHFL_NM": "모집공고.hwp", "AHFL_URL": "https://apply.lh.or.kr/f?id=2"}]}]
    assert [(a["block"], a["url_key"], a["kind"]) for a in find_attachments(detail)] == [
        ("dsAhflInfo", "AHFL_URL", "pdf"), ("dsAhflInfo", "AHFL_URL", "hwp")]
    assert file_kind(None, "https://x/y.PDF") == "pdf"

