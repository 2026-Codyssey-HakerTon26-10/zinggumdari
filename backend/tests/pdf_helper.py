"""테스트용 최소 PDF 만들기(글자 층 있음, ASCII, 612x792 쪽)."""

from pathlib import Path


def make_pdf(path: Path, pages: list[list[tuple[float, float, str]]], image_pages: tuple[int, ...] = ()) -> Path:
    """쪽마다 (x, 아래에서 잰 y, 글자) 줄들. image_pages(1부터)에는 회색 그림 하나를 그린다(스캔한 쪽 흉내)."""
    objs: list[tuple[int, bytes]] = []
    kids = []
    font_no = 3 + 2 * len(pages)
    image_no = font_no + 1
    for i, lines in enumerate(pages):
        page_no, content_no = 3 + 2 * i, 4 + 2 * i
        kids.append(f"{page_no} 0 R")
        stream = "".join(f"BT /F1 12 Tf {x} {y} Td ({t}) Tj ET\n" for x, y, t in lines).encode()
        xobj = ""
        if i + 1 in image_pages:
            stream += b"q 400 0 0 500 100 150 cm /Im1 Do Q\n"
            xobj = f" /XObject << /Im1 {image_no} 0 R >>"
        objs.append((page_no, f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                              f"/Resources << /Font << /F1 {font_no} 0 R >>{xobj} >> /Contents {content_no} 0 R >>".encode()))
        objs.append((content_no, b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream"))
    objs.append((1, b"<< /Type /Catalog /Pages 2 0 R >>"))
    objs.append((2, f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode()))
    objs.append((font_no, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))
    if image_pages:
        objs.append((image_no, b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray "
                               b"/BitsPerComponent 8 /Length 1 >>\nstream\n\x80\nendstream"))
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
