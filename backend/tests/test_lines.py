"""to_lines·read_document·save_lines(api.md §8, SPEC §10.1): 형식 가리기, 줄 ID, 항목 기호 나누기, 저장."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from backend.compiler import llm
from backend.compiler.lines import UNSUPPORTED, has_rrn, read_document, save_lines, to_lines
from backend.compiler.readers import UnsupportedDocument, ocr
from backend.tests.hwp_fixture import SAMPLE_LINES, hwpx_bytes, sample_hwp, sample_hwpx, sample_hwpx_sections

FIX = Path(__file__).parent / "fixtures"
KEYS = {"id", "page", "bbox", "text", "mark"}

NOTICE = """1. 신청자격
  ○ 공고일 현재 ○○시에 주민등록을 둔   만 19세 이상 ○ 무주택 세대구성원 ※전년도 소득 기준

※ 2026-11-03 기준 · 가구 소득 120% 이하
문의\t02-123-4567"""


def test_raw_text_bullets_and_ids():
    meta, lines = read_document("t-1", NOTICE)
    assert [l["text"] for l in lines] == [
        "1. 신청자격",
        "○ 공고일 현재 ○○시에 주민등록을 둔 만 19세 이상",  # "○○시"는 가림 글자라 안 나눈다
        "○ 무주택 세대구성원",
        "※전년도 소득 기준",
        "※ 2026-11-03 기준 · 가구 소득 120% 이하",
        "문의 02-123-4567",
    ]
    assert [l["id"] for l in lines] == [f"l{i}" for i in range(1, 7)]
    assert all(set(l) == KEYS and l["page"] is None and l["bbox"] is None for l in lines)
    assert [l["mark"] for l in lines] == [False, True, True, True, True, False]
    assert meta == {"doc_id": "t-1", "kind": "text", "pages": None, "text_layer": True, "ocr": None,
                    "sha256": hashlib.sha256(NOTICE.encode("utf-8")).hexdigest(), "n_lines": 6}


def test_more_bullets_split_mid_line():
    got = [l["text"] for l in to_lines("t", "가 ◦ 나 • 다 □ 라 ■ 마 ▶다음 출산•입양 □예")]
    assert got == ["가", "◦ 나", "• 다", "□ 라", "■ 마", "▶다음 출산•입양 □예"]


def test_text_files(tmp_path):
    md = tmp_path / "n.md"
    md.write_text("# 신청 자격\n\n- 만 19세 이상\n", encoding="utf-8")
    assert [l["text"] for l in to_lines("m", md)] == ["# 신청 자격", "- 만 19세 이상"]
    assert [l["text"] for l in to_lines("m", str(md))] == [str(md)]  # str은 언제나 원문 텍스트(파일을 열지 않는다)
    euc = tmp_path / "n.txt"
    euc.write_bytes("무주택 세대구성원\r\n소득 120% 이하".encode("cp949"))
    meta, lines = read_document("e", euc)
    assert [l["text"] for l in lines] == ["무주택 세대구성원", "소득 120% 이하"]
    assert meta["sha256"] == hashlib.sha256(euc.read_bytes()).hexdigest()
    plain = tmp_path / "notice"  # 확장자 없는 텍스트
    plain.write_text("혼인기간 7년 이내", encoding="utf-8")
    assert to_lines("p", plain)[0]["text"] == "혼인기간 7년 이내"


HTML = """<!DOCTYPE html><html><head><title>청년 월세</title>
<style>p { color: red }</style><script>var s = "<p>무시</p>";</script></head>
<body><h2>신청 자격</h2><p>만 19세 이상 ○ 무주택&nbsp;청년<br>소득 &lt;중위 150%&gt; 이하</p><noscript>켜 주세요</noscript>
<table><caption>표 1</caption><tbody><tr><th>가구원수</th><th>기준</th></tr>
<tr><td>1인</td><td><p>3,846,357원</p><table><tr><td>월</td><td>지급</td></tr></table></td></tr>
<tr><td>2인</td><td></td></tr></tbody></table>
<ul><li>신청서</li><li>임대차계약서</li></ul></body></html>"""

HTML_LINES = [("청년 월세", None), ("신청 자격", None), ("만 19세 이상", None), ("○ 무주택 청년", None),
              ("소득 <중위 150%> 이하", None), ("표 1", None), ("가구원수 | 기준", "t1"), ("1인 | 3,846,357원 월 지급", "t1"),
              ("2인 | ", "t1"), ("신청서", None), ("임대차계약서", None)]


def test_html_stripping(tmp_path):
    for src in (HTML, tmp_path / "page.html"):
        if isinstance(src, Path):
            src.write_text(HTML, encoding="utf-8")
        meta, lines = read_document("w", src)
        assert meta["kind"] == "text"
        assert [(l["text"], l.get("table")) for l in lines] == HTML_LINES
        assert [l["id"] for l in lines] == [f"l{i}" for i in range(1, 12)]
    frag = tmp_path / "frag.htm"  # 머리 없는 조각도 확장자로 HTML
    frag.write_text("<div>가</div><div>나<script>x()</script></div>", encoding="utf-8")
    assert [l["text"] for l in to_lines("f", frag)] == ["가", "나"]


def test_text_pdf():
    meta, lines = read_document("pdf-1", FIX / "notice_text.pdf")
    assert meta == {**meta, "kind": "pdf", "pages": 2, "text_layer": True, "ocr": None, "n_lines": len(lines)}
    by_id = {l["id"]: l for l in lines}
    assert by_id["p1-l4"]["text"] == "1. 신청자격"
    assert by_id["p2-l1"]["text"] == "2. 지원내용"  # 쪽마다 1부터
    for p in (1, 2):
        ids = [l["id"] for l in lines if l["page"] == p]
        assert ids == [f"p{p}-l{i}" for i in range(1, len(ids) + 1)]
    rows = [l for l in lines if "table" in l]
    assert [l["text"] for l in rows][:2] == ["가구원수 | 기준 중위소득 150%(월)", "1인 | 3,846,357원"]
    assert {l["table"] for l in rows} == {"p1-t1"} and all(l["mark"] for l in rows)
    assert all(len(l["bbox"]) == 4 and "src" not in l for l in lines)
    assert set(lines[0]) == KEYS


def test_scanned_pdf_ocr(monkeypatch):
    monkeypatch.setenv("ZINGGUM_OCR", "llm")
    usage = {"input_tokens": 1500, "output_tokens": 200}
    monkeypatch.setattr(llm, "ocr_page", lambda png, *, model=None: llm.LLMResult(
        data={"lines": ["1. 지원대상", "자녀 수 | 금리", "1명 | 0.2%p", "○ 연소득 7천 5백만 원 이하 ○ 무주택"]},
        raw_text="", model="fake", usage=usage))
    meta, lines = read_document("scan", FIX / "notice_scan.pdf", llm_ocr=True)
    assert (meta["text_layer"], meta["ocr"], meta["ocr_usage"]) == (False, "llm", usage)
    assert [(l["id"], l.get("table")) for l in lines] == [("p1-l1", None), ("p1-l2", "p1-t1"), ("p1-l3", "p1-t1"), ("p1-l4", None)]
    assert lines[3]["text"] == "○ 연소득 7천 5백만 원 이하 ○ 무주택"  # PDF 줄은 나누지 않는다
    assert all(l["src"] == "ocr" and l["bbox"] is None and l["page"] == 1 for l in lines)


def test_upload_scan_never_goes_to_llm(monkeypatch):
    """기본(사용자 업로드)은 쪽 이미지를 네이토로 보내지 않는다. tesseract가 없으면 거부."""
    monkeypatch.setenv("ZINGGUM_OCR", "llm")
    monkeypatch.setattr(ocr, "_tesseract_kor", lambda: False)
    sent = []
    monkeypatch.setattr(llm, "ocr_page", lambda png, *, model=None: sent.append(png))
    with pytest.raises(UnsupportedDocument, match="tesseract"):
        to_lines("scan", FIX / "notice_scan.pdf")
    assert sent == []


def test_scanned_pdf_without_ocr(monkeypatch):
    monkeypatch.setenv("ZINGGUM_OCR", "off")
    with pytest.raises(UnsupportedDocument, match="스캔 PDF"):
        to_lines("scan", FIX / "notice_scan.pdf")


@pytest.mark.parametrize("kind, write", [("hwp", sample_hwp), ("hwpx", sample_hwpx)])
def test_hwp_and_hwpx(tmp_path, kind, write):
    path = tmp_path / f"notice.{kind}"
    write(path)
    meta, lines = read_document("h", path)
    assert (meta["kind"], meta["pages"], meta["n_lines"]) == (kind, None, len(SAMPLE_LINES))
    assert [(l["text"], l.get("table")) for l in lines] == SAMPLE_LINES
    assert [l["id"] for l in lines] == [f"l{i}" for i in range(1, len(SAMPLE_LINES) + 1)]
    assert all(l["page"] is None and l["bbox"] is None and "src" not in l for l in lines)
    nameless = tmp_path / "upload"  # 확장자가 없어도 앞 바이트로 가린다
    nameless.write_bytes(path.read_bytes())
    assert read_document("h", nameless)[0]["kind"] == kind


def test_wrong_suffix_goes_by_magic(tmp_path):
    p = tmp_path / "notice.hwpx"
    sample_hwp(p)  # 이름만 .hwpx인 HWP 5.0
    assert read_document("x", p)[0]["kind"] == "hwp"
    q = tmp_path / "notice.txt"
    q.write_bytes(hwpx_bytes(sample_hwpx_sections()))
    assert read_document("x", q)[0]["kind"] == "hwpx"


def test_unsupported_binary(tmp_path):
    png = tmp_path / "a.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.text")
    odt = tmp_path / "a.odt"
    odt.write_bytes(buf.getvalue())
    for p in (png, odt):
        with pytest.raises(UnsupportedDocument) as e:
            to_lines("u", p)
        assert str(e.value) == UNSUPPORTED
    with pytest.raises(FileNotFoundError):
        to_lines("u", tmp_path / "없음.pdf")


@pytest.mark.parametrize("bad", ["a:b", "", "../x", "a/b", "a\\b"])
def test_bad_doc_id(tmp_path, bad):
    with pytest.raises(ValueError):
        to_lines(bad, "만 19세 이상")
    with pytest.raises(ValueError):
        save_lines(bad, [], out_dir=tmp_path)


def test_save_lines_round_trip(tmp_path):
    meta, lines = read_document("2026-11-test", HTML)
    out = save_lines("2026-11-test", lines, meta, out_dir=tmp_path / "notices")
    assert out == tmp_path / "notices" / "2026-11-test.lines.json"
    raw = out.read_text(encoding="utf-8")
    assert "신청 자격" in raw  # ensure_ascii=False
    body = raw.splitlines()
    assert body[0] == "[" and body[-1] == "]" and len(body) == len(lines) + 2  # 한 줄에 한 요소
    assert json.loads(raw) == lines
    assert json.loads((tmp_path / "notices" / "2026-11-test.meta.json").read_text(encoding="utf-8")) == meta
    empty = save_lines("empty", [], out_dir=tmp_path)
    assert json.loads(empty.read_text(encoding="utf-8")) == [] and not (tmp_path / "empty.meta.json").exists()


def test_has_rrn():
    assert has_rrn(to_lines("r", "신청인 홍길동\n주민등록번호 900101-1234567"))
    assert has_rrn([{"text": "900101 - 2234567"}])
    assert not has_rrn(to_lines("r", "문의 02-123-4567\n공고 제2026-123호\n1900101-1234567\n공고번호 2015122300020916"))
    assert not has_rrn([])
    # 같은 번호를 다르게 쓴 모양도 거부한다: 하이픈 없이 붙여 씀, 긴 줄표, 띄어쓰기, 전각 숫자, 외국인등록번호(5~8)
    for text in ("9001011234567", "900101 – 1234567", "900101  -  1234567", "９００１０１－１２３４５６７", "900101-5234567"):
        assert has_rrn([{"text": text}]), text
    # 앞 6자리와 뒷 7자리 사이에서 줄이나 표 칸이 나뉘어도 잡는다
    assert has_rrn([{"text": "주민등록번호 900101"}, {"text": "1234567 홍길동"}])
    assert has_rrn([{"text": "홍길동 | 900101 | 1234567"}])
    assert not has_rrn([{"text": "(주민등록번호 표시 예시) 123456-1234567"}])   # LH 행복주택 공고의 예시 번호(34월 56일)
    assert has_rrn([{"text": "예시 123456-1234567, 신청인 900101-1234567"}])    # 예시가 있어도 진짜 꼴이 있으면 거부
    for front in ("900001", "901301", "900100", "900132"):                      # 월 00과 13, 일 00과 32는 날짜가 아니다
        assert not has_rrn([{"text": f"{front}-1234567"}]), front
    for front in ("900101", "901231", "900131", "001201"):                      # 월 01과 12, 일 01과 31은 날짜다
        assert has_rrn([{"text": f"{front}-1234567"}]), front


# --- 검토 지적 재현 ---

def test_html_source_newlines_are_spaces():
    html = "<!doctype html><html><body><p>공고일 현재 만 19세 이상\n    34세 이하인 무주택 청년</p><pre>가\n나</pre></body></html>"
    assert [l["text"] for l in to_lines("h", html)] == ["공고일 현재 만 19세 이상 34세 이하인 무주택 청년", "가", "나"]


def test_text_that_looks_like_a_path_is_text():
    assert [l["text"] for l in to_lines("x", "/etc/hosts")] == ["/etc/hosts"]
    assert [l["text"] for l in to_lines("x", "backend/pyproject.toml")] == ["backend/pyproject.toml"]
