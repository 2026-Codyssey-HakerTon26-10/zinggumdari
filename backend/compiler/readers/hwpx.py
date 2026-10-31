"""HWPX(zip 안 OWPML XML) 읽기. Contents/section{N}.xml을 차례로 읽어 문단은 한 줄씩, 표는 행마다 한 줄(칸은 " | ")로 낸다.

이름공간은 보지 않고 태그 끝 이름(p, run, t, tbl, tr, tc …)만 맞춘다. 머리말·꼬리말은 뺀다.
"""

from __future__ import annotations

import itertools
import re
import xml.etree.ElementTree as ET
import zipfile

from backend.compiler.readers import UnsupportedDocument

_SECTION = re.compile(r"Contents/section(\d+)\.xml$")
_INLINE = {"tab": " ", "lineBreak": "\n", "fwSpace": " ", "nbSpace": " ", "hyphen": "-"}
_SKIP = {"header", "footer"}


def read_hwpx(path) -> dict:
    try:
        with zipfile.ZipFile(path) as z:
            names = sorted((int(m[1]), n) for n in z.namelist() if (m := _SECTION.match(n)))
            roots = [ET.fromstring(z.read(n)) for _, n in names]
    except Exception as e:  # BadZipFile, ParseError, zlib.error, OSError, NotImplementedError(암호·새 압축) …
        raise UnsupportedDocument("HWPX 본문을 읽지 못했습니다. 암호가 걸렸거나 손상된 파일일 수 있습니다.") from e
    if not roots:
        raise UnsupportedDocument("HWPX 본문(Contents/section*.xml)을 찾지 못했습니다.")
    out: list[tuple[str, str | None]] = []
    tables = itertools.count(1)
    for root in roots:
        _walk(root, out, tables)
    return reader_output("hwpx", out)


def reader_output(kind: str, out: list[tuple[str, str | None]]) -> dict:
    """(글자, 표 ID) 목록 → reader 출력. 줄바꿈으로 나누고 앞뒤 빈칸을 떼고 빈 줄은 버린다(hwp.py도 쓴다).
    표 행은 빈 칸 자리(" | 120%")를 지키려고 다듬지 않는다."""
    lines = [{"page": None, "bbox": None, "text": s, "src": "text", "table": table}
             for text, table in out for s in ([text] if table else [p.strip() for p in text.split("\n")]) if s]
    return {"kind": kind, "pages": None, "text_layer": True, "ocr": None, "lines": lines}


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _walk(el, out: list, tables) -> None:
    """문서 순서로 문단·표를 찾아 (글자, 표 ID)를 쌓는다. tables=None이면 표 칸 안이라 안쪽 표도 글자로 펼친다."""
    for c in el:
        name = _local(c.tag)
        if name in _SKIP:
            continue
        if name == "p":
            out.append((_para_text(c), None))
        if name == "tbl" and tables is not None:
            _table(c, out, tables)
        else:
            _walk(c, out, tables)  # 문단 안의 표·글상자·각주 문단은 문단 글자 다음에 나온다


def _para_text(p) -> str:
    """문단 자신의 글자(<run><t>와 그 안의 탭·줄 나눔). 안쪽 표·글상자 문단은 _walk가 따로 낸다."""
    parts = []
    for run in p:
        if _local(run.tag) != "run":
            continue
        for c in run:
            name = _local(c.tag)
            if name == "t":
                parts.append(c.text or "")
                for s in c:
                    parts += _INLINE.get(_local(s.tag), ""), s.tail or ""
            elif name in _INLINE:
                parts.append(_INLINE[name])
    return "".join(parts)


def _table(tbl, out: list, tables) -> None:
    """<tbl><tr><tc> → 행마다 한 줄. 칸은 cellAddr 열 자리에 놓고, 칸 글자는 칸 안 문단(안쪽 표 포함)을 빈칸으로 잇는다."""
    tid = f"t{next(tables)}"
    for cap in (c for c in tbl if _local(c.tag) == "caption"):  # 캡션은 행 앞에(hwp.py와 같다)
        _walk(cap, out, tables)
    rows = []
    for tr in tbl:
        if _local(tr.tag) != "tr":
            continue
        cells = {}
        for i, tc in enumerate(c for c in tr if _local(c.tag) == "tc"):
            addr = next((a.get("colAddr") for a in tc if _local(a.tag) == "cellAddr"), None)
            parts: list = []
            _walk(tc, parts, None)
            cells[int(addr) if addr and addr.isdigit() else i] = " ".join(" ".join(t for t, _ in parts).split())
        rows.append(cells)
    cnt = tbl.get("colCnt") or ""
    width = max([int(cnt) if cnt.isdigit() else 0, *(c + 1 for cells in rows for c in cells)])
    for cells in rows:  # pdf.py처럼 열 자리를 지킨다: 병합으로 가려진 칸은 ""
        row = " | ".join(cells.get(c, "") for c in range(width))
        if row.replace("|", "").strip():
            out.append((row, tid))
