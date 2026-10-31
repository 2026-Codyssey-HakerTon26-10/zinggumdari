"""HWP 5.0·HWPX reader: 테스트 안에서 진짜 파일을 만들어 읽는다(한글·네트워크 없이)."""

import struct

import olefile
import pytest

from backend.compiler.lines import to_lines
from backend.compiler.readers import UnsupportedDocument
from backend.compiler.readers.hwp import HWP3_MESSAGE, _cell_pos, read_hwp
from backend.compiler.readers.hwpx import read_hwpx
from backend.tests.hwp_fixture import (
    CTRL_HEADER, LIST_HEADER, SAMPLE_LINES, TABLE, ctl, hwp_bytes, hwpx_bytes, hx_p, hx_section, hx_tbl, para, rec,
    sample_hwp, sample_hwpx, sample_hwpx_sections, sample_sections, table,
)


def _pairs(doc):
    return [(l["text"], l["table"]) for l in doc["lines"]]


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return p


@pytest.mark.parametrize("compressed", [True, False])
def test_hwp_sample(tmp_path, compressed):
    path = tmp_path / "notice.hwp"
    sample_hwp(path, compressed=compressed)
    assert olefile.isOleFile(str(path))
    with olefile.OleFileIO(str(path)) as ole:
        assert {"/".join(e) for e in ole.listdir()} == {"FileHeader", "DocInfo", "BodyText/Section0", "BodyText/Section1"}
    doc = read_hwp(path)
    assert {k: doc[k] for k in ("kind", "pages", "text_layer", "ocr")} == {"kind": "hwp", "pages": None, "text_layer": True, "ocr": None}
    assert _pairs(doc) == SAMPLE_LINES
    assert all(l["page"] is None and l["bbox"] is None and l["src"] == "text" for l in doc["lines"])
    assert "머리말 글" not in [l["text"] for l in doc["lines"]]


def test_hwp_sections_numeric_order_and_long_record(tmp_path):
    # Section10이 Section2 뒤에 와야 한다. 긴 문단은 크기 0xFFF 확장 헤더와 4096바이트 넘는 OLE 스트림을 쓴다.
    sections = [para(f"구역 {i}") for i in range(11)] + [para("가" * 3000)]
    doc = read_hwp(_write(tmp_path, "a.hwp", hwp_bytes(sections, compressed=False)))
    assert [l["text"] for l in doc["lines"]] == [f"구역 {i}" for i in range(11)] + ["가" * 3000]


def test_hwp_tables_rows_and_ids(tmp_path):
    body = para("앞") + para("", 0, table([[["가"]], [["나"]], [["다"]]], 1)) + para("", 0, table([[["a"], [""], ["b"]]], 1))
    doc = read_hwp(_write(tmp_path, "t.hwp", hwp_bytes([body])))
    assert _pairs(doc) == [("앞", None), ("가", "t1"), ("나", "t1"), ("다", "t1"), ("a |  | b", "t2")]  # 빈 칸도 자리를 지킨다


def test_hwp_cell_address_order(tmp_path):
    # 칸은 저장 순서가 아니라 칸 주소(열)를 따라 놓는다. TABLE 앞 목록(캡션)은 보통 줄이다.
    ctrl = rec(CTRL_HEADER, 1, b"tbl "[::-1]) + rec(LIST_HEADER, 2, struct.pack("<HHI", 1, 0, 0)) + para("표 1. 소득 기준", 2)
    ctrl += rec(TABLE, 2, struct.pack("<IHH", 0, 1, 2))
    for col, text in [(1, "둘"), (0, "하나")]:
        ctrl += rec(LIST_HEADER, 2, struct.pack("<HHIHH", 1, 0, 0, col, 0)) + para(text, 2)
    doc = read_hwp(_write(tmp_path, "c.hwp", hwp_bytes([para(ctl(11, b"tbl "), 0, ctrl)])))
    assert _pairs(doc) == [("표 1. 소득 기준", None), ("하나 | 둘", "t1")]


def test_cell_pos_fallbacks():
    six = [struct.pack("<HIHH", 1, 0, c, 0) for c in (0, 1)]  # 문단 수(2)·속성(4) 바로 뒤에 열·행
    assert _cell_pos(six, 1, 2) == [(0, 0), (0, 1)]
    junk = [struct.pack("<HHIHH", 1, 0, 0, 9, 9)] * 4  # 표 크기를 벗어나면 저장 순서(행 우선)
    assert _cell_pos(junk, 2, 2) == [(0, 0), (0, 1), (1, 0), (1, 1)]


@pytest.mark.parametrize("props, word", [(0b11, "암호"), (0b101, "배포용"), (0b10001, "DRM")])
def test_hwp_protected(tmp_path, props, word):
    path = _write(tmp_path, "p.hwp", hwp_bytes([para("본문")], props=props))
    with pytest.raises(UnsupportedDocument, match=word):
        read_hwp(path)


def test_hwp_distribution_viewtext_only(tmp_path):
    path = _write(tmp_path, "v.hwp", hwp_bytes([para("본문")], storage="ViewText"))
    with pytest.raises(UnsupportedDocument, match="배포용"):
        read_hwp(path)


@pytest.mark.parametrize("data", [b"HWP Document File V3.00 \x1a\x01\x02\x03\x04\x05" + bytes(200), b"not an hwp file at all"])
def test_hwp3_or_not_ole(tmp_path, data):
    with pytest.raises(UnsupportedDocument) as e:
        read_hwp(_write(tmp_path, "old.hwp", data))
    assert str(e.value) == HWP3_MESSAGE


def test_hwp_wrong_signature(tmp_path):
    with pytest.raises(UnsupportedDocument, match="HWP 문서가 아닙니다"):
        read_hwp(_write(tmp_path, "x.hwp", hwp_bytes([para("본문")], signature=b"Something Else")))


def test_hwpx_sample(tmp_path):
    path = tmp_path / "notice.hwpx"
    sample_hwpx(path)
    doc = read_hwpx(path)
    assert {k: doc[k] for k in ("kind", "pages", "text_layer", "ocr")} == {"kind": "hwpx", "pages": None, "text_layer": True, "ocr": None}
    assert _pairs(doc) == SAMPLE_LINES
    assert all(l["page"] is None and l["bbox"] is None and l["src"] == "text" for l in doc["lines"])


def test_hwpx_merged_cell_keeps_columns(tmp_path):
    # 위 칸이 두 행을 덮으면(rowSpan) 아래 행에는 그 칸이 없다 → 열 자리를 ""로 둔다
    tbl = ('<hp:tbl rowCnt="2" colCnt="2"><hp:tr><hp:tc><hp:subList>' + hx_p("구분") + '</hp:subList><hp:cellAddr colAddr="0" rowAddr="0"/></hp:tc>'
           '<hp:tc><hp:subList>' + hx_p("기준") + '</hp:subList><hp:cellAddr colAddr="1" rowAddr="0"/></hp:tc></hp:tr>'
           '<hp:tr><hp:tc><hp:subList>' + hx_p("120%") + '</hp:subList><hp:cellAddr colAddr="1" rowAddr="1"/></hp:tc></hp:tr></hp:tbl>')
    doc = read_hwpx(_write(tmp_path, "m.hwpx", hwpx_bytes([hx_section(hx_p("", tbl))])))
    assert _pairs(doc) == [("구분 | 기준", "t1"), (" | 120%", "t1")]


def test_hwpx_sections_numeric_order(tmp_path):
    doc = read_hwpx(_write(tmp_path, "a.hwpx", hwpx_bytes([hx_section(hx_p(f"구역 {i}")) for i in range(11)])))
    assert [l["text"] for l in doc["lines"]] == [f"구역 {i}" for i in range(11)]


def test_hwp_extension_holding_hwpx(tmp_path):
    sample_hwpx(tmp_path / "x.hwpx")
    doc = read_hwp(_write(tmp_path, "x.hwp", (tmp_path / "x.hwpx").read_bytes()))
    assert doc["kind"] == "hwpx" and _pairs(doc) == SAMPLE_LINES


def test_hwpx_broken(tmp_path):
    with pytest.raises(UnsupportedDocument):
        read_hwpx(_write(tmp_path, "b.hwpx", b"PK\x03\x04 broken"))
    with pytest.raises(UnsupportedDocument, match="본문"):
        read_hwpx(_write(tmp_path, "e.hwpx", hwpx_bytes([])))


# --- 검토 지적 재현 ---

def test_hwpx_table_caption_kept(tmp_path):
    cap = ('<hp:caption side="TOP" fullSz="0" width="8504" gap="850" lastWidth="42520"><hp:subList>'
           + hx_p("<표 1> 맞벌이 가구 소득 기준(중위소득 200% 이하)") + "</hp:subList></hp:caption>")
    tbl = hx_tbl([[["가구원수"], ["소득 기준"]], [["1인"], ["120% 이하"]]])
    tbl = tbl.replace(">", '><hp:sz width="42520" height="2000"/><hp:pos/><hp:outMargin/>' + cap + "<hp:inMargin/>", 1)
    p = tmp_path / "cap.hwpx"
    p.write_bytes(hwpx_bytes([hx_section(hx_p("", tbl))]))
    assert [l["text"] for l in read_hwpx(p)["lines"]] == [
        "<표 1> 맞벌이 가구 소득 기준(중위소득 200% 이하)", "가구원수 | 소득 기준", "1인 | 120% 이하"]


def test_truncated_hwp_is_unsupported(tmp_path):
    data = hwp_bytes(sample_sections())
    p = tmp_path / "trunc.hwp"
    p.write_bytes(data[:2438])  # olefile이 ValueError를 내던 자리
    with pytest.raises(UnsupportedDocument):
        read_hwp(p)
    for n in range(600, len(data), 97):  # 어디서 잘려도 읽거나 안내 문구로 거부한다(날 예외 없음)
        p.write_bytes(data[:n])
        try:
            read_hwp(p)
        except UnsupportedDocument:
            pass


def test_corrupt_hwpx_is_unsupported(tmp_path):
    import random
    data = hwpx_bytes(sample_hwpx_sections())
    rnd = random.Random(1)
    for i in range(30):  # 압축 자료 몇 바이트를 바꾼 파일: zlib.error 등 날 예외가 아니라 안내 문구
        b = bytearray(data)
        for _ in range(rnd.randrange(1, 8)):
            b[rnd.randrange(8, len(b))] = rnd.randrange(256)
        p = tmp_path / f"bad{i}.hwpx"
        p.write_bytes(bytes(b))
        try:
            to_lines("x", p)
        except UnsupportedDocument:
            pass
