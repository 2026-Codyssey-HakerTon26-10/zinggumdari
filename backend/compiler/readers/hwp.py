"""HWP 5.0(OLE 복합 파일) 읽기. 「한글 문서 파일 형식 5.0」을 따라 BodyText/Section{N}의 레코드를 직접 푼다.

문단은 한 줄씩(강제 줄 나눔이면 나눈다), 표는 행마다 한 줄(칸은 열 자리대로 " | ")로 낸다. 머리말·꼬리말은 뺀다.
OLE 컨테이너만 olefile로 연다.
"""

from __future__ import annotations

import itertools
import re
import struct
import zlib

import olefile

from backend.compiler.readers import UnsupportedDocument
from backend.compiler.readers.hwpx import read_hwpx, reader_output

HWP3_MESSAGE = "HWP 3.x 이하 형식은 읽지 못합니다. 한글에서 HWP 5.0 또는 HWPX로 저장해 올려 주세요."

# 레코드 태그(HWPTAG_BEGIN = 0x10 기준)
PARA_HEADER, PARA_TEXT, CTRL_HEADER, LIST_HEADER, TABLE = 0x10 + 50, 0x10 + 51, 0x10 + 55, 0x10 + 56, 0x10 + 61

# 글자 안 컨트롤: 인라인·확장 컨트롤은 8 WCHAR(16바이트)를 차지하고, 나머지 0~31(문자 컨트롤)은 1 WCHAR다.
_WIDE = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}
_CHAR = {9: " ", 10: "\n", 24: "-", 30: " ", 31: " "}  # 탭, 강제 줄 나눔, 하이픈, 묶음·고정폭 빈칸
_SECTION = re.compile(r"Section(\d+)$")


def read_hwp(path) -> dict:
    with open(path, "rb") as f:
        head = f.read(32)
    if head.startswith(b"PK\x03\x04"):  # 확장자만 .hwp인 HWPX
        return read_hwpx(path)
    if head.startswith(b"HWP Document File V3") or head[:8] != olefile.MAGIC:
        raise UnsupportedDocument(HWP3_MESSAGE)
    try:
        with olefile.OleFileIO(str(path)) as ole:
            out = _read_ole(ole)
    except UnsupportedDocument:
        raise
    except Exception as e:  # 잘리거나 깨진 컨테이너·레코드는 OSError·ValueError·struct.error 등 여러 가지로 터진다
        raise UnsupportedDocument("HWP 파일을 열지 못했습니다. 손상된 파일일 수 있습니다.") from e
    return reader_output("hwp", out)


def _read_ole(ole) -> list[tuple[str, str | None]]:
    fh = ole.openstream("FileHeader").read() if ole.exists("FileHeader") else b""
    if fh.startswith(b"HWP Document File V3"):
        raise UnsupportedDocument(HWP3_MESSAGE)
    if not fh.startswith(b"HWP Document File"):
        raise UnsupportedDocument("HWP 문서가 아닙니다. 한글(HWP 5.0·HWPX) 파일이나 PDF를 올려 주세요.")
    props = struct.unpack_from("<I", fh, 36)[0] if len(fh) >= 40 else 0
    if props & 0b10:
        raise UnsupportedDocument("암호가 걸린 HWP 문서는 읽지 못합니다. 한글에서 암호를 풀고 저장해 올려 주세요.")
    if props & 0b10000:
        raise UnsupportedDocument("DRM 보안이 걸린 HWP 문서는 읽지 못합니다. 보안을 푼 파일이나 PDF를 올려 주세요.")
    sections = sorted((int(m[1]), "/".join(e)) for e in ole.listdir()
                      if len(e) == 2 and e[0] == "BodyText" and (m := _SECTION.match(e[1])))
    if props & 0b100 or (not sections and ole.exists("ViewText")):
        raise UnsupportedDocument("배포용 HWP 문서는 읽지 못합니다. 배포용이 아닌 원본 파일이나 PDF를 올려 주세요.")
    if not sections:
        raise UnsupportedDocument("HWP 본문(BodyText)을 찾지 못했습니다. 손상된 파일일 수 있습니다.")
    out: list[tuple[str, str | None]] = []
    tables = itertools.count(1)
    for _, name in sections:
        data = ole.openstream(name).read()
        if props & 1:  # 압축: zlib 헤더 없는 raw deflate
            try:
                data = zlib.decompressobj(-15).decompress(data)
            except zlib.error as e:
                raise UnsupportedDocument("HWP 본문을 풀지 못했습니다. 손상된 파일일 수 있습니다.") from e
        _walk(_tree(data), out, tables)
    return out


def _records(data: bytes):
    """레코드 헤더(32비트: 태그 0-9, 수준 10-19, 크기 20-31; 크기 0xFFF면 다음 DWORD가 크기) → (태그, 수준, 자료)."""
    i = 0
    while i + 4 <= len(data):
        (h,) = struct.unpack_from("<I", data, i)
        i += 4
        tag, level, size = h & 0x3FF, (h >> 10) & 0x3FF, h >> 20
        if size == 0xFFF and i + 4 <= len(data):
            (size,) = struct.unpack_from("<I", data, i)
            i += 4
        yield tag, level, data[i:i + size]
        i += size


def _tree(data: bytes) -> list:
    """수준으로 레코드 나무를 만든다. 마디 = (태그, 자료, 자식들)."""
    root: list = []
    stack = [(-1, root)]
    for tag, level, body in _records(data):
        while stack[-1][0] >= level:
            stack.pop()
        node = (tag, body, [])
        stack[-1][1].append(node)
        stack.append((level, node[2]))
    return root


def _walk(nodes: list, out: list, tables) -> None:
    """나무를 문서 순서로 돌며 (글자, 표 ID)를 쌓는다. tables=None이면 표 칸 안이라 안쪽 표도 글자로 펼친다.

    문단의 컨트롤(표, 각주, 글상자 …)은 PARA_TEXT 다음 자식이라 문단 글자 뒤에 나온다.
    """
    for tag, data, kids in nodes:
        cid = data[:4][::-1] if tag == CTRL_HEADER else b""
        if tag == PARA_TEXT:
            out.append((_para_text(data), None))
        elif cid in (b"head", b"foot"):
            continue
        elif cid == b"tbl " and tables is not None:
            _table(kids, out, tables)
        else:
            _walk(kids, out, tables)


def _para_text(data: bytes) -> str:
    """PARA_TEXT(UTF-16LE). 컨트롤 글자는 자리만큼 건너뛰고 탭·줄 나눔·빈칸류만 글자로 바꾼다."""
    n = len(data) // 2
    codes = struct.unpack(f"<{n}H", data[:2 * n])
    out, start, i = [], 0, 0
    while i < n:
        ch = codes[i]
        if ch >= 32:
            i += 1
            continue
        out += data[2 * start:2 * i].decode("utf-16-le", "replace"), _CHAR.get(ch, "")
        i += 8 if ch in _WIDE else 1
        start = i
    out.append(data[2 * start:2 * n].decode("utf-16-le", "replace"))
    return "".join(out)


def _table(kids: list, out: list, tables) -> None:
    """표 컨트롤의 자식(TABLE, 칸마다 LIST_HEADER와 그 뒤 문단들) → 행마다 한 줄. TABLE 앞 목록(캡션)은 보통 줄."""
    tid = f"t{next(tables)}"
    nrows = ncols = 0
    caption, cells, seen = [], [], False
    for node in kids:
        tag, data, sub = node
        if tag == TABLE:
            seen = True
            if len(data) >= 8:
                nrows, ncols = struct.unpack_from("<HH", data, 4)
        elif not seen:
            caption.append(node)
        elif tag == LIST_HEADER:
            cells.append((data, list(sub)))
        elif cells:
            cells[-1][1].append(node)
    _walk(caption, out, tables)
    rows: dict[int, dict[int, str]] = {}
    for (r, c), (_, nodes) in zip(_cell_pos([d for d, _ in cells], nrows, ncols), cells):
        parts: list = []
        _walk(nodes, parts, None)
        rows.setdefault(r, {})[c] = " ".join(" ".join(t for t, _ in parts).split())
    width = max([ncols, *(c + 1 for row in rows.values() for c in row)])
    for r in sorted(rows):  # pdf.py처럼 열 자리를 지킨다: 병합으로 가려진 칸은 ""
        row = " | ".join(rows[r].get(c, "") for c in range(width))
        if row.replace("|", "").strip():
            out.append((row, tid))


def _cell_pos(heads: list[bytes], nrows: int, ncols: int) -> list[tuple[int, int]]:
    """칸의 (행, 열). LIST_HEADER의 문단 수(2)·알 수 없음(2)·속성(4) 뒤에 열, 행(UINT16)이 온다.
    표 크기를 벗어나면 6바이트 뒤를 보고, 그래도 안 맞으면 저장 순서(행 우선)로 놓는다."""
    for off in (8, 6):
        pos = [struct.unpack_from("<HH", h, off)[::-1] for h in heads if len(h) >= off + 4]
        if len(pos) == len(heads) and all((not nrows or r < nrows) and (not ncols or c < ncols) for r, c in pos):
            return pos
    return [divmod(i, ncols or 1) for i in range(len(heads))]
