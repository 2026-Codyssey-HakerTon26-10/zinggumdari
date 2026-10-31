"""PDF reader와 글자 인식(SPEC §10.1). 픽스처는 fixtures/make_fixtures.py가 만든다.
실제 네이토 API를 부르는 테스트는 ZINGGUM_LIVE=1일 때만 돈다."""

from __future__ import annotations

import difflib
import os
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from backend.compiler import llm
from backend.compiler.readers import UnsupportedDocument, ocr
from backend.compiler.readers.pdf import group_words, read_pdf

FIX = Path(__file__).parent / "fixtures"
TEXT_PDF = FIX / "notice_text.pdf"
SCAN_PDF = FIX / "notice_scan.pdf"


def _ids(lines: list[dict]) -> dict[str, dict]:
    """lines.py가 붙일 줄 ID(p{쪽}-l{n})를 흉내 낸다."""
    out, n = {}, {}
    for l in lines:
        n[l["page"]] = n.get(l["page"], 0) + 1
        out[f"p{l['page']}-l{n[l['page']]}"] = l
    return out


def test_text_pdf_lines():
    r = read_pdf(TEXT_PDF)
    assert (r["kind"], r["pages"], r["text_layer"], r["ocr"]) == ("pdf", 2, True, None)
    assert "ocr_usage" not in r and "unread_pages" not in r
    lines = r["lines"]
    for l in lines:
        x0, top, x1, bottom = l["bbox"]
        assert 0 <= x0 < x1 <= 595 and 0 <= top < bottom <= 842
        assert l["text"].strip() and l["src"] == "text" and l["page"] in (1, 2)
    # 쪽 순서, 쪽 안에서는 위→아래
    assert [l["page"] for l in lines] == sorted(l["page"] for l in lines)
    for p in (1, 2):
        tops = [l["bbox"][1] for l in lines if l["page"] == p]
        assert tops == sorted(tops)
    ids = _ids(lines)
    assert ids["p1-l4"]["text"] == "1. 신청자격"
    assert ids["p1-l5"]["text"] == "○ 공고일 현재 ○○시에 주민등록을 둔 만 19세 이상 34세 이하 무주택 청년"
    assert ids["p2-l4"]["text"] == "○ 2026. 11. 3.(화) ~ 2026. 11. 27.(금) 18:00까지"


def test_text_pdf_table_rows():
    lines = read_pdf(TEXT_PDF)["lines"]
    rows = [l for l in lines if l["table"]]
    assert [l["text"] for l in rows] == [
        "가구원수 | 기준 중위소득 150%(월)", "1인 | 3,846,357원", "2인 | 6,307,170원", "3인 | 8,051,186원",
    ]
    assert {l["table"] for l in rows} == {"p1-t1"}
    # 표 안 단어는 일반 줄로 또 나오지 않는다
    assert sum("3,846,357원" in l["text"] for l in lines) == 1
    # 행 상자는 위에서 아래로 붙어 있고, 표 앞뒤 줄과 순서가 맞다
    assert all(a["bbox"][3] <= b["bbox"][1] + 0.5 for a, b in zip(rows, rows[1:]))
    texts = [l["text"] for l in lines]
    i = texts.index(rows[0]["text"])
    assert texts[i - 1].startswith("○ 임차보증금") and texts[i + 4].startswith("※ 다른 주거급여")


def test_text_pdf_two_columns_split():
    p2 = [l for l in read_pdf(TEXT_PDF)["lines"] if l["page"] == 2]
    left, right = p2[-2], p2[-1]
    assert left["text"] == "문의: 주거정책과 02-123-4567"
    assert right["text"] == "접수: 거주지 행정복지센터"
    assert left["bbox"][2] < right["bbox"][0]


def _w(x0, x1, top, text, h=10.0):
    return {"x0": x0, "x1": x1, "top": top, "bottom": top + h, "text": text}


def test_group_words_rows_and_gap():
    words = [
        _w(10, 30, 100.8, "만"), _w(34, 60, 100, "19세"), _w(64, 90, 100.4, "이상"),  # 높이가 조금 달라도 한 줄
        _w(300, 330, 100.2, "오른쪽"),                                              # 큰 틈: 다른 줄
        _w(10, 40, 115, "다음줄"),
    ]
    got = [(top, " ".join(w["text"] for w in seg)) for top, seg in group_words(words)]
    assert [t for _, t in got] == ["만 19세 이상", "오른쪽", "다음줄"]
    assert got[0][0] == got[1][0]  # 같은 높이 줄은 같은 세로 위치로 정렬된다
    assert group_words([]) == []


def _fake_llm(lines, usage):
    calls = []

    def fake(png, *, model=None):
        calls.append(png)
        return llm.LLMResult(data={"lines": lines}, raw_text="", model="fake", usage=usage)
    return fake, calls


def test_scan_pdf_llm_ocr(monkeypatch):
    monkeypatch.setenv("ZINGGUM_OCR", "llm")
    fake, calls = _fake_llm(
        ["1. 지원대상", "○ 부부합산 연소득 7천 5백만 원 이하", "자녀 수 | 추가 금리 지원", "1명 | 0.2%p", " ", "※ 제외"],
        {"input_tokens": 1500, "output_tokens": 200, "service_tier": "standard"},
    )
    monkeypatch.setattr(llm, "ocr_page", fake)
    r = read_pdf(SCAN_PDF)
    assert len(calls) == 1 and calls[0][:8] == b"\x89PNG\r\n\x1a\n"
    assert (r["pages"], r["text_layer"], r["ocr"]) == (1, False, "llm")
    assert r["ocr_usage"] == {"input_tokens": 1500, "output_tokens": 200}
    assert [l["text"] for l in r["lines"]] == ["1. 지원대상", "○ 부부합산 연소득 7천 5백만 원 이하",
                                              "자녀 수 | 추가 금리 지원", "1명 | 0.2%p", "※ 제외"]
    assert all(l["src"] == "ocr" and l["page"] == 1 and l["bbox"] is None for l in r["lines"])
    assert [l["table"] for l in r["lines"]] == [None, None, "p1-t1", "p1-t1", None]


TSV = "\n".join("\t".join(map(str, r)) for r in [
    ["level", "page_num", "block_num", "par_num", "line_num", "word_num", "left", "top", "width", "height", "conf", "text"],
    [1, 1, 0, 0, 0, 0, 0, 0, 1654, 2339, -1, ""],
    [2, 1, 1, 0, 0, 0, 100, 200, 800, 120, -1, ""],
    [4, 1, 1, 1, 1, 0, 100, 200, 600, 40, -1, ""],
    [5, 1, 1, 1, 1, 1, 100, 200, 120, 40, 91.5, "○"],
    [5, 1, 1, 1, 1, 2, 240, 202, 200, 38, 88.0, "만"],
    [5, 1, 1, 1, 1, 3, 460, 201, 240, 40, 90.1, "19세"],
    [5, 1, 1, 1, 1, 4, 720, 200, 10, 40, 95.0, " "],
    [4, 1, 1, 1, 2, 0, 100, 280, 500, 40, -1, ""],
    [5, 1, 1, 1, 2, 1, 100, 280, 500, 40, 80.0, "이하"],
]) + "\n"


def test_parse_tesseract_tsv():
    assert ocr.parse_tesseract_tsv(TSV, 0.5) == [
        {"bbox": [50.0, 100.0, 350.0, 120.5], "text": "○ 만 19세"},
        {"bbox": [50.0, 140.0, 300.0, 160.0], "text": "이하"},
    ]
    assert ocr.parse_tesseract_tsv("", 1.0) == []


def test_scan_pdf_tesseract(monkeypatch):
    monkeypatch.setenv("ZINGGUM_OCR", "tesseract")
    monkeypatch.setattr(ocr, "_tesseract", lambda png: TSV)
    r = read_pdf(SCAN_PDF)
    assert (r["text_layer"], r["ocr"]) == (False, "tesseract") and "ocr_usage" not in r
    s = 72 / 200
    assert r["lines"][0] == {"page": 1, "bbox": [round(100 * s, 1), round(200 * s, 1), round(700 * s, 1), round(241 * s, 1)],
                             "text": "○ 만 19세", "src": "ocr", "table": None}


def test_scan_pdf_without_ocr_is_unsupported(monkeypatch):
    monkeypatch.setenv("ZINGGUM_OCR", "off")
    with pytest.raises(UnsupportedDocument, match="스캔 PDF"):
        read_pdf(SCAN_PDF)


def test_mixed_pdf_without_ocr_reads_text_pages(monkeypatch, tmp_path):
    monkeypatch.setenv("ZINGGUM_OCR", "off")
    doc = pdfium.PdfDocument.new()
    for src in (TEXT_PDF, SCAN_PDF):
        doc.import_pages(pdfium.PdfDocument(src))
    path = tmp_path / "mixed.pdf"
    doc.save(path)
    r = read_pdf(path)
    assert (r["pages"], r["text_layer"], r["ocr"], r["unread_pages"]) == (3, False, None, [3])
    assert {l["page"] for l in r["lines"]} == {1, 2}


def test_broken_pdf(tmp_path):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"not a pdf")
    with pytest.raises(UnsupportedDocument):
        read_pdf(p)


def test_ocr_backend(monkeypatch):
    monkeypatch.setattr(ocr, "_tesseract_kor", lambda: False)
    monkeypatch.setattr(llm, "available", lambda: False)
    monkeypatch.delenv("ZINGGUM_OCR", raising=False)
    assert ocr.ocr_backend() is None
    monkeypatch.setattr(llm, "available", lambda: True)
    assert ocr.ocr_backend() == "llm"
    monkeypatch.setattr(ocr, "_tesseract_kor", lambda: True)
    assert ocr.ocr_backend() == "tesseract"
    for v, want in (("off", None), ("llm", "llm"), ("tesseract", "tesseract")):
        monkeypatch.setenv("ZINGGUM_OCR", v)
        assert ocr.ocr_backend() == want
    # 사용자 업로드: 네이토는 고르지 않는다(ZINGGUM_OCR=llm이어도)
    monkeypatch.setenv("ZINGGUM_OCR", "llm")
    assert ocr.ocr_backend(allow_llm=False) == "tesseract"
    monkeypatch.setattr(ocr, "_tesseract_kor", lambda: False)
    assert ocr.ocr_backend(allow_llm=False) is None


KEY_TOKENS = ["2026-77", "7년", "7천 5백만 원", "3억 원", "6개월", "1.5%", "150만 원", "0.2%p", "0.5%p",
              "2026. 12. 1.", "2026. 12. 31."]


@pytest.mark.skipif(os.environ.get("ZINGGUM_LIVE") != "1", reason="실제 네이토 API 호출은 ZINGGUM_LIVE=1일 때만")
def test_live_llm_ocr_scan(monkeypatch):
    monkeypatch.setenv("ZINGGUM_OCR", "llm")
    r = read_pdf(SCAN_PDF)
    got = "\n".join(l["text"] for l in r["lines"])
    truth = (FIX / "notice_scan.txt").read_text(encoding="utf-8").strip()
    ratio = difflib.SequenceMatcher(None, truth, got).ratio()
    print(f"\n[live ocr] model={llm.model_name('ocr')} ratio={ratio:.3f} usage={r['ocr_usage']}\n{got}")
    assert [t for t in KEY_TOKENS if t not in got] == []
    assert ratio > 0.9


# --- 검토 지적 재현: 쪽 가르기, 겹친 글자, CID, 2단, 글자 인식 실패 ---

from backend.tests import pdf_fixture as pf  # noqa: E402

BODY = pf.text_ops([(72, 700, 11, "Income 120% or less for all applicants")])


def _pdf(tmp_path, pages, objs=None, name="t.pdf"):
    path = tmp_path / name
    path.write_bytes(pf.build(pages, {"F1": pf.HELV, **(objs or {})}))
    return path


def _fake_ocr(monkeypatch, calls, fail=False):
    monkeypatch.setattr(ocr, "ocr_backend", lambda **_: "llm")

    def fake(page, *, backend, usage=None, info=None):
        calls.append(page.page_number)
        if fail:
            raise llm.LLMError("두 번 모두 실패: HTTP 529: overloaded")
        return [{"bbox": None, "text": "1. 지원대상"}]
    monkeypatch.setattr(ocr, "ocr_page", fake)


def test_scan_with_text_footer_is_still_a_scan(tmp_path, monkeypatch):
    footer = pf.text_ops([(30, 15, 7, "Printed 2026-03-02 10:22 page 1/1")])
    path = _pdf(tmp_path, [pf.page(footer, "full")], {"Im0": pf.scan_image()})
    calls = []
    _fake_ocr(monkeypatch, calls)
    r = read_pdf(path)
    assert calls == [1] and [l["text"] for l in r["lines"]] == ["1. 지원대상"] and r["text_layer"] is False
    monkeypatch.setattr(ocr, "ocr_backend", lambda **_: None)
    with pytest.raises(UnsupportedDocument, match="스캔 PDF"):  # 인식 수단이 없으면 꼬리말만 읽고 넘어가지 않는다
        read_pdf(path)


def test_searchable_scan_text_layer_is_ocr(tmp_path):
    layer = pf.text_ops([(72, 700, 11, "Household income 12O% or less")], mode=3)
    r = read_pdf(_pdf(tmp_path, [pf.page(layer, "full")], {"Im0": pf.scan_image()}))
    assert [(l["text"], l["src"]) for l in r["lines"]] == [("Household income 12O% or less", "ocr")]
    assert r["text_layer"] is False and r["ocr_layer_pages"] == [1]


def test_sparse_text_page_with_logo_keeps_text(tmp_path, monkeypatch):
    monkeypatch.setenv("ZINGGUM_OCR", "off")
    p1 = pf.page(pf.text_ops([(72, 600, 20, "Notice 26")]), "logo")
    r = read_pdf(_pdf(tmp_path, [p1, pf.page(BODY)], {"Im0": pf.scan_image()}))
    assert [l["text"] for l in r["lines"]] == ["Notice 26", "Income 120% or less for all applicants"]
    assert r["text_layer"] is True and "unread_pages" not in r


def test_cid_garbage_is_not_a_text_layer(tmp_path, monkeypatch):
    monkeypatch.setenv("ZINGGUM_OCR", "off")
    objs = {"F2": ("<< /Type /Font /Subtype /Type0 /BaseFont /HYGothic-Medium-Identity-H /Encoding /Identity-H "
                   "/DescendantFonts [{CF}] >>", None),
            "CF": ("<< /Type /Font /Subtype /CIDFontType2 /BaseFont /HYGothic-Medium /CIDSystemInfo << /Registry (Adobe) "
                   "/Ordering (Identity) /Supplement 0 >> /DW 1000 /FontDescriptor {FD} >>", None),
            "FD": ("<< /Type /FontDescriptor /FontName /HYGothic-Medium /Flags 4 /FontBBox [0 -200 1000 900] /ItalicAngle 0 "
                   "/Ascent 880 /Descent -120 /CapHeight 700 /StemV 80 >>", None)}
    cid = {"content": b"BT /F2 11 Tf 72 700 Td <0C1A0D3E0E5512341235> Tj ET", "resources": "<< /Font << /F2 {F2} >> >>"}
    r = read_pdf(_pdf(tmp_path, [cid, pf.page(BODY)], objs))
    assert r["unread_pages"] == [1] and not any("(cid:" in l["text"] for l in r["lines"])


def test_overprinted_bold_is_deduped(tmp_path):
    bold = pf.text_ops([(72, 700, 11, "Household income 120% or less"), (72.3, 700, 11, "Household income 120% or less")])
    assert [l["text"] for l in read_pdf(_pdf(tmp_path, [pf.page(bold)]))["lines"]] == ["Household income 120% or less"]


def test_two_columns_with_normal_gutter_split():
    k, out = 10.4, []  # 11pt 한글 한 글자 폭, 단 사이 38pt(13mm)

    def row(top, *words):
        out.extend({"text": t, "x0": x, "x1": x + k * len(t), "top": top, "bottom": top + 12} for x, t in words)
    row(61.4, (65.0, "○"), (78.5, "신청자격:"), (126.6, "공고일"), (160.9, "현재"), (184.8, "무주택"), (219.1, "세대구성원"),
        (309.0, "○"), (322.5, "제외:"), (349.9, "주거급여"), (394.5, "수급자는"), (439.2, "제외"))
    row(88.4, (65.0, "○"), (78.5, "소득:"), (105.9, "중위소득"), (174.5, "150%"), (205.4, "이하"),
        (309.0, "○"), (322.5, "자산:"), (349.9, "3억"), (427.4, "이하"))
    got = [" ".join(w["text"] for w in seg) for _, seg in group_words(out)]
    assert got[:2] == ["○ 신청자격: 공고일 현재 무주택 세대구성원", "○ 제외: 주거급여 수급자는 제외"]
    # 한 줄에만 있는 넓은 틈(단 사이가 아니다)은 그대로 둔다
    one = [{"text": t, "x0": x, "x1": x + k * len(t), "top": 10, "bottom": 22} for x, t in ((65, "가구원수"), (140, "소득"))]
    assert len(group_words(one)) == 1


def test_ocr_failure_on_one_page_keeps_text_pages(tmp_path, monkeypatch):
    path = _pdf(tmp_path, [pf.page(BODY), pf.page(b"", "full")], {"Im0": pf.scan_image()})
    calls = []
    _fake_ocr(monkeypatch, calls, fail=True)
    r = read_pdf(path)
    assert r["unread_pages"] == [2] and "HTTP 529" in r["ocr_errors"][0]
    assert [l["text"] for l in r["lines"]] == ["Income 120% or less for all applicants"]
    monkeypatch.setenv("ZINGGUM_OCR", "tesseract")  # 깔리지 않은 tesseract를 고르면 FileNotFoundError 대신 안내
    monkeypatch.setattr(ocr, "ocr_backend", lambda **_: "tesseract")
    monkeypatch.setattr(ocr, "ocr_page", lambda page, **kw: (_ for _ in ()).throw(FileNotFoundError("tesseract")))
    with pytest.raises(UnsupportedDocument, match="글자 인식에 실패"):
        read_pdf(SCAN_PDF)


def _grid(x0, x1, ys, xs) -> bytes:
    """가로선(ys)과 세로선(xs)으로 된 격자."""
    ops = [f"{x0} {y} m {x1} {y} l S" for y in ys] + [f"{x} {ys[0]} m {x} {ys[-1]} l S" for x in xs]
    return ("\n".join(ops) + "\n").encode()


def test_boxed_text_chopped_by_grid_is_not_a_table(tmp_path):
    # 위: 글자 폭(9pt)마다 세로선이 있는 테두리 친 안내문. 아래: 칸 경계가 단어 사이에 있는 진짜 표
    box = _grid(50, 545, [690, 720], range(50, 546, 9))
    table = _grid(50, 350, [560, 580, 600, 620], [50, 150, 350])
    text = pf.text_ops([
        (54, 701, 11, "Applicants must keep the lease and pay rent on time"),
        (54, 605, 10, "Household"), (154, 605, 10, "Income limit"),
        (54, 585, 10, "1 person"), (154, 585, 10, "3,846,357"),
        (54, 565, 10, "2 persons"), (154, 565, 10, "6,307,170"),
    ])
    lines = read_pdf(_pdf(tmp_path, [pf.page(box + table + text)]))["lines"]
    assert [(l["text"], l["table"]) for l in lines] == [
        ("Applicants must keep the lease and pay rent on time", None),
        ("Household | Income limit", "p1-t1"), ("1 person | 3,846,357", "p1-t1"), ("2 persons | 6,307,170", "p1-t1"),
    ]


def test_words_in_unassigned_table_area_are_kept(tmp_path):
    # 표 바깥 상자 안이지만 어느 칸에도 들지 않은 자리(오른쪽 세로선이 위 행에만 있다)의 글자도 줄로 남는다
    grid = _grid(50, 350, [600, 620], [50, 150, 350]) + b"50 560 m 150 560 l S\n50 560 m 50 600 l S\n150 560 m 150 600 l S\n"
    text = pf.text_ops([(54, 605, 10, "Rent"), (154, 605, 10, "40% of market"), (200, 575, 10, "Deposit 20%")])
    got = [l["text"] for l in read_pdf(_pdf(tmp_path, [pf.page(grid + text)]))["lines"]]
    assert "Deposit 20%" in " ".join(got)
