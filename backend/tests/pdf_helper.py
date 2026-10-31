"""테스트용 최소 PDF 만들기(글자 층 있음, ASCII, 612x792 쪽)."""

from pathlib import Path


def make_pdf(path: Path, pages: list[list[tuple[float, float, str]]]) -> Path:
    """쪽마다 (x, 아래에서 잰 y, 글자) 줄들."""
    objs: list[tuple[int, bytes]] = []
    kids = []
    font_no = 3 + 2 * len(pages)
    for i, lines in enumerate(pages):
        page_no, content_no = 3 + 2 * i, 4 + 2 * i
        kids.append(f"{page_no} 0 R")
        stream = "".join(f"BT /F1 12 Tf {x} {y} Td ({t}) Tj ET\n" for x, y, t in lines).encode()
        objs.append((page_no, f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                              f"/Resources << /Font << /F1 {font_no} 0 R >> >> /Contents {content_no} 0 R >>".encode()))
        objs.append((content_no, b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream"))
    objs.append((1, b"<< /Type /Catalog /Pages 2 0 R >>"))
    objs.append((2, f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode()))
    objs.append((font_no, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))
    objs.sort()
    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for no, body in objs:
        offsets[no] = len(out)
        out += f"{no} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for no in range(1, len(objs) + 1):
        out += f"{offsets[no]:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path
