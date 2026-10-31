"""테스트용 작은 PDF를 손으로 만든다(스캔 이미지, 꼬리말, 겹쳐 찍은 글자, 보이지 않는 글자 층, CID 글꼴)."""

from __future__ import annotations

import io
from pathlib import Path

import pdfplumber

HELV = ("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>", None)
SCAN_PDF = Path(__file__).parent / "fixtures" / "notice_scan.pdf"


def build(pages: list[dict], objs: dict | None = None) -> bytes:
    """pages: [{"content": bytes, "resources": str}]. objs: {이름: (사전 글, 스트림 bytes|None)}.
    사전 글·resources의 {이름}은 그 객체 참조로, 스트림 사전의 LEN은 길이로 바꾼다."""
    objs = objs or {}
    ids = {name: i for i, name in enumerate(objs, 3)}  # 1: Catalog, 2: Pages

    def ref(s: str) -> str:
        for name, i in ids.items():
            s = s.replace("{" + name + "}", f"{i} 0 R")
        return s

    bodies = [b"<< /Type /Catalog /Pages 2 0 R >>", b""]
    for d, stream in objs.values():
        d = ref(d)
        bodies.append(d.encode("latin-1") if stream is None
                      else d.replace("LEN", str(len(stream))).encode("latin-1") + b"\nstream\n" + stream + b"\nendstream")
    kids = []
    for p in pages:
        c = p["content"]
        bodies.append(f"<< /Length {len(c)} >>\nstream\n".encode() + c + b"\nendstream")
        bodies.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources {ref(p['resources'])} "
                      f"/Contents {len(bodies)} 0 R >>".encode("latin-1"))
        kids.append(len(bodies))
    bodies[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode()
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, b in enumerate(bodies, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + b + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(bodies) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(bodies) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def text_ops(items: list[tuple[float, float, float, str]], mode: int = 0) -> bytes:
    """[(x, 아래에서 y, 크기, 글자)] → 글자 그리기. mode 3은 보이지 않는 글자(검색 가능한 스캔의 글자 층)."""
    tr = f"{mode} Tr " if mode else ""
    return "\n".join(f"BT {tr}/F1 {size} Tf {x} {y} Td ({s.replace('(', '[').replace(')', ']')}) Tj ET"
                     for x, y, size, s in items).encode("latin-1")


def scan_image() -> tuple:
    """notice_scan.pdf 쪽을 JPEG로 그린 이미지 객체(이름 Im0으로 쓴다)."""
    img = pdfplumber.open(SCAN_PDF).pages[0].to_image(resolution=50).original.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    w, h = img.size
    return (f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace /DeviceRGB /BitsPerComponent 8 "
            "/Filter /DCTDecode /Length LEN >>", buf.getvalue())


def page(content: bytes, image: str | None = None) -> dict:
    """글자(F1)와, image가 "full"이면 쪽 전체, "logo"면 작은 그림을 깐 쪽."""
    draw = {"full": b"q 595 0 0 842 0 0 cm /Im0 Do Q\n", "logo": b"q 60 0 0 80 60 700 cm /Im0 Do Q\n"}.get(image, b"")
    res = "<< /XObject << /Im0 {Im0} >> /Font << /F1 {F1} >> >>" if image else "<< /Font << /F1 {F1} >> >>"
    return {"content": draw + content, "resources": res}
