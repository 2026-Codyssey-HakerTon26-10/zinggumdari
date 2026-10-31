"""테스트용 HWP 5.0·HWPX 파일 만들기. 작은 OLE(CFB v3) 쓰기 도구를 직접 두어 한글 없이 진짜 파일을 만든다.

sample_hwp(path) / sample_hwpx(path)는 같은 내용(SAMPLE_LINES)의 공고 조각을 쓴다. 다른 테스트도 가져다 쓴다.
"""

from __future__ import annotations

import io
import struct
import zipfile
import zlib
from xml.sax.saxutils import escape

# ---- OLE / CFB v3 (512바이트 섹터, 64바이트 미니 섹터) ----

_FREE, _END, _FATSECT, _NONE = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFF
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _nsec(nbytes: int, size: int = 512) -> int:
    return -(-nbytes // size)


def _dirent(name: str, kind: int, left: int, right: int, child: int, start: int, size: int) -> bytes:
    raw = name.encode("utf-16-le") + b"\0\0" if name else b""
    return struct.pack("<64sHBBIII16sIQQIQ", raw, len(raw), kind, 1, left, right, child, bytes(16), 0, 0, 0, start, size)


def ole_bytes(streams: dict[str, bytes]) -> bytes:
    """{"FileHeader": …, "BodyText/Section0": …} → CFB v3 바이트. 4096바이트 미만 스트림은 미니 스트림에 둔다."""
    entries = [["Root Entry", 5, [], b""]]  # [이름, 종류(1 저장소, 2 스트림, 5 루트), 자식 번호, 자료]
    index = {"": 0}
    for path, data in streams.items():
        parts, parent = path.split("/"), 0
        for k, name in enumerate(parts):
            key, leaf = "/".join(parts[:k + 1]), k == len(parts) - 1
            if key not in index:
                index[key] = len(entries)
                entries.append([name, 2 if leaf else 1, [], data if leaf else b""])
                entries[parent][2].append(index[key])
            parent = index[key]

    mini, minifat, start, big = bytearray(), [], {}, []
    for i, (_, kind, _, data) in enumerate(entries):
        if kind != 2:
            continue
        if len(data) >= 4096:
            big.append(i)
            continue
        n = _nsec(len(data), 64)
        start[i] = len(minifat) if n else _END
        minifat += [len(minifat) + k + 1 for k in range(n - 1)] + [_END] * bool(n)
        mini += data.ljust(n * 64, b"\0")

    # 섹터 배치: FAT | 디렉터리 | 미니 FAT | 미니 스트림 | 큰 스트림들
    runs = [("dir", _nsec(len(entries) * 128)), ("minifat", _nsec(len(minifat) * 4)), ("mini", _nsec(len(mini)))]
    runs += [(i, _nsec(len(entries[i][3]))) for i in big]
    other = sum(n for _, n in runs)
    nfat = 1
    while nfat * 128 < nfat + other:
        nfat += 1
    assert nfat <= 109, "DIFAT 섹터는 지원하지 않는다"
    fat, first = [_FATSECT] * nfat, {}
    for key, n in runs:
        first[key] = len(fat) if n else _END
        fat += [len(fat) + k + 1 for k in range(n - 1)] + [_END] * bool(n)
    for i in big:
        start[i] = first[i]

    # 형제는 (길이, 대문자) 순으로 오른쪽 형제 사슬로 잇는다
    left_right = {}
    for _, _, kids, _ in entries:
        kids.sort(key=lambda j: (len(entries[j][0]), entries[j][0].upper()))
        for a, b in zip(kids, kids[1:] + [_NONE]):
            left_right[a] = b
    dirs = b""
    for i, (name, kind, kids, data) in enumerate(entries):
        child = kids[0] if kids else _NONE
        if kind == 5:
            st, size = first["mini"], len(mini)
        elif kind == 2:
            st, size = start[i], len(data)
        else:
            st, size = 0, 0
        dirs += _dirent(name, kind, _NONE, left_right.get(i, _NONE), child, st, size)
    while len(dirs) % 512:
        dirs += _dirent("", 0, _NONE, _NONE, _NONE, 0, 0)

    header = struct.pack("<8s16sHHHHH6sIIIIIIIII109I", OLE_MAGIC, bytes(16), 0x3E, 3, 0xFFFE, 9, 6, bytes(6),
                         0, nfat, first["dir"], 0, 4096, first["minifat"], _nsec(len(minifat) * 4), _END, 0,
                         *(list(range(nfat)) + [_FREE] * (109 - nfat)))
    fat += [_FREE] * (nfat * 128 - len(fat))
    minifat += [_FREE] * (-len(minifat) % 128)
    body = [struct.pack(f"<{len(fat)}I", *fat), dirs, struct.pack(f"<{len(minifat)}I", *minifat), bytes(mini)]
    body += [entries[i][3] for i in big]
    return header + b"".join(b + bytes(-len(b) % 512) for b in body)


# ---- HWP 5.0 레코드 ----

PARA_HEADER, PARA_TEXT, CTRL_HEADER, LIST_HEADER, PAGE_DEF, TABLE = 66, 67, 71, 72, 73, 77


def rec(tag: int, level: int, data: bytes = b"") -> bytes:
    """레코드 하나. 4095바이트 이상이면 크기 칸을 0xFFF로 두고 다음 DWORD에 쓴다."""
    if len(data) >= 0xFFF:
        return struct.pack("<II", tag | level << 10 | 0xFFF << 20, len(data)) + data
    return struct.pack("<I", tag | level << 10 | len(data) << 20) + data


def w(s: str) -> bytes:
    """글자(문자 컨트롤 10·30 등도 그대로) → UTF-16LE."""
    return s.encode("utf-16-le")


def ctl(code: int, cid: bytes = b"") -> bytes:
    """8 WCHAR 인라인·확장 컨트롤 글자: 코드, 컨트롤 ID(거꾸로 4바이트), 나머지 0, 코드."""
    return struct.pack("<H", code) + (cid[::-1] if cid else bytes(4)) + bytes(8) + struct.pack("<H", code)


def para(text: str | bytes, level: int = 0, children: bytes = b"") -> bytes:
    """문단: PARA_HEADER + PARA_TEXT(끝에 문단 끝 13) + 컨트롤 레코드들(level+1로 만든 것)."""
    raw = (w(text) if isinstance(text, str) else text) + w("\r")
    return (rec(PARA_HEADER, level, struct.pack("<IIHBBHHHI", len(raw) // 2, 0, 0, 0, 0, 1, 0, 1, 0))
            + rec(PARA_TEXT, level + 1, raw) + children)


def ctrl_list(cid: bytes, paras: list[str], level: int) -> bytes:
    """문단 목록을 가진 컨트롤(머리말 'head', 각주 'fn  ' 등): CTRL_HEADER + LIST_HEADER + 문단들."""
    out = rec(CTRL_HEADER, level, cid[::-1] + bytes(8)) + rec(LIST_HEADER, level + 1, struct.pack("<HHI", len(paras), 0, 0))
    return out + b"".join(para(p, level + 1) for p in paras)


def table(rows: list[list[list]], level: int) -> bytes:
    """표 컨트롤. rows[행][열] = 칸 문단 목록(글자, 또는 안쪽 표의 rows)."""
    nrows, ncols = len(rows), len(rows[0])
    out = rec(CTRL_HEADER, level, b"tbl "[::-1] + bytes(44))
    out += rec(TABLE, level + 1, struct.pack(f"<IHHH4H{nrows}HHH", 0, nrows, ncols, 0, 0, 0, 0, 0, *[ncols] * nrows, 1, 0))
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            # 문단 수, 알 수 없음, 속성, 열, 행, 열 병합, 행 병합, 폭, 높이, 안 여백 4, 테두리/배경 ID
            out += rec(LIST_HEADER, level + 1, struct.pack("<HHIHHHHII4HH", len(cell), 0, 0, c, r, 1, 1, 7000, 1000, 0, 0, 0, 0, 1))
            for item in cell:
                out += para(item, level + 1) if isinstance(item, str) else para(ctl(11, b"tbl "), level + 1, table(item, level + 2))
    return out


def file_header(props: int, signature: bytes = b"HWP Document File") -> bytes:
    """FileHeader 스트림(256바이트): 서명 32, 버전 DWORD, 속성 DWORD(bit0 압축, bit1 암호, bit2 배포용, bit4 DRM)."""
    return struct.pack("<32sII", signature, 0x05010100, props).ljust(256, b"\0")


def hwp_bytes(sections: list[bytes], compressed: bool = True, props: int | None = None,
              signature: bytes = b"HWP Document File", storage: str = "BodyText") -> bytes:
    """구역 레코드 바이트들 → HWP 5.0 파일 바이트. 압축이면 각 구역을 raw deflate로 줄인다."""
    def pack(data: bytes) -> bytes:
        if not compressed:
            return data
        z = zlib.compressobj(9, zlib.DEFLATED, -15)
        return z.compress(data) + z.flush()
    streams = {"FileHeader": file_header(int(compressed) if props is None else props, signature),
               "DocInfo": pack(b"")}
    streams |= {f"{storage}/Section{i}": pack(s) for i, s in enumerate(sections)}
    return ole_bytes(streams)


def sample_sections() -> list[bytes]:
    """SAMPLE_LINES가 나오는 두 구역: 구역 정의·머리말, 필드·탭·묶음 빈칸·각주, 줄 나눔, 2x3 표(안쪽 표 포함)."""
    first = para(ctl(2, b"secd") + ctl(16, b"head") + w("신청 자격"), 0,
                 rec(CTRL_HEADER, 1, b"secd"[::-1] + bytes(20)) + rec(PAGE_DEF, 2, bytes(40))
                 + ctrl_list(b"head", ["머리말 글"], 1))
    income = para(ctl(3, b"%clk") + w("무주택 세대구성원") + ctl(9) + w("소득\x1e기준 120% 이하") + ctl(4) + ctl(17, b"fn  "), 0,
                  ctrl_list(b"fn  ", ["※ 전년도 도시근로자 월평균소득 기준"], 1))
    rows = [[["구분"], ["소득 기준"], ["자산 기준"]],
            [["신혼부부", "(예비 포함)"], ["120% 이하"], ["3억 4,500만 원 이하", [[["자동차"], ["3,708만 원"]]]]]]
    return [first + income + para("혼인기간 7년 이내\n만 19세 이상") + para("")
            + para(ctl(11, b"tbl "), 0, table(rows, 1)) + para("제출 서류"),
            para("유의사항") + para("중복 신청 불가")]


SAMPLE_LINES = [
    ("신청 자격", None),
    ("무주택 세대구성원 소득 기준 120% 이하", None),
    ("※ 전년도 도시근로자 월평균소득 기준", None),
    ("혼인기간 7년 이내", None),
    ("만 19세 이상", None),
    ("구분 | 소득 기준 | 자산 기준", "t1"),
    ("신혼부부 (예비 포함) | 120% 이하 | 3억 4,500만 원 이하 자동차 3,708만 원", "t1"),
    ("제출 서류", None),
    ("유의사항", None),
    ("중복 신청 불가", None),
]


def sample_hwp(path, compressed: bool = True) -> None:
    with open(path, "wb") as f:
        f.write(hwp_bytes(sample_sections(), compressed=compressed))


# ---- HWPX ----

_NS = 'xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'


def hx_p(text: str, inner: str = "") -> str:
    """문단 XML. 글자 안 \\t → <hp:tab/>, \\n → <hp:lineBreak/>. inner는 같은 run에 붙일 XML(표·컨트롤)."""
    t = escape(text).replace("\t", '<hp:tab width="4000" leader="0" type="1"/>').replace("\n", "<hp:lineBreak/>")
    return f'<hp:p paraPrIDRef="0" styleIDRef="0"><hp:run charPrIDRef="0">{inner}<hp:t>{t}</hp:t></hp:run></hp:p>'


def hx_tbl(rows: list[list[list]]) -> str:
    """표 XML. rows[행][열] = 칸 문단 목록(글자, 또는 안쪽 표의 rows)."""
    def cell(r: int, c: int, items: list) -> str:
        ps = "".join(hx_p(i) if isinstance(i, str) else hx_p("", hx_tbl(i)) for i in items)
        return (f'<hp:tc header="0"><hp:subList vertAlign="CENTER">{ps}</hp:subList>'
                f'<hp:cellAddr colAddr="{c}" rowAddr="{r}"/><hp:cellSpan colSpan="1" rowSpan="1"/></hp:tc>')
    trs = "".join("<hp:tr>" + "".join(cell(r, c, x) for c, x in enumerate(row)) + "</hp:tr>" for r, row in enumerate(rows))
    return f'<hp:tbl rowCnt="{len(rows)}" colCnt="{len(rows[0])}">{trs}</hp:tbl>'


def hx_section(body: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><hs:sec {_NS}>{body}</hs:sec>'


def hwpx_bytes(sections: list[str]) -> bytes:
    """구역 XML 문자열들 → HWPX(zip) 바이트."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mimetype", "application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        items = "".join(f'<opf:item id="section{i}" href="Contents/section{i}.xml" media-type="application/xml"/>'
                        for i in range(len(sections)))
        z.writestr("Contents/content.hpf", '<?xml version="1.0" encoding="UTF-8"?><opf:package '
                   f'xmlns:opf="http://www.idpf.org/2007/opf/"><opf:manifest>{items}</opf:manifest></opf:package>')
        for i, xml in enumerate(sections):
            z.writestr(f"Contents/section{i}.xml", xml)
    return buf.getvalue()


def sample_hwpx_sections() -> list[str]:
    header = '<hp:secPr/><hp:ctrl><hp:header><hp:subList>' + hx_p("머리말 글") + '</hp:subList></hp:header></hp:ctrl>'
    note = '<hp:ctrl><hp:footNote><hp:subList>' + hx_p("※ 전년도 도시근로자 월평균소득 기준") + '</hp:subList></hp:footNote></hp:ctrl>'
    rows = [[["구분"], ["소득 기준"], ["자산 기준"]],
            [["신혼부부", "(예비 포함)"], ["120% 이하"], ["3억 4,500만 원 이하", [[["자동차"], ["3,708만 원"]]]]]]
    income = hx_p("무주택 세대구성원\t소득 기준 120% 이하").replace("</hp:t></hp:run>", "</hp:t>" + note + "</hp:run>")
    return [hx_section(hx_p("신청 자격", header) + income + hx_p("혼인기간 7년 이내\n만 19세 이상") + hx_p("")
                       + hx_p("", hx_tbl(rows)) + hx_p("제출 서류")),
            hx_section(hx_p("유의사항") + hx_p("중복 신청 불가"))]


def sample_hwpx(path) -> None:
    with open(path, "wb") as f:
        f.write(hwpx_bytes(sample_hwpx_sections()))
