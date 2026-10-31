"""스캔 PDF 쪽의 글자 인식. tesseract(kor)가 있으면 그것을, 없으면 네이토 API 비전을 쓴다.

- 환경 변수 `ZINGGUM_OCR=tesseract|llm|off`로 고를 수 있다.
- tesseract는 단어 좌표가 있어 줄 상자(bbox)를 PDF 좌표로 낸다. LLM은 좌표가 없어 bbox가 None이다.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

from backend.compiler import llm

DPI = 200  # 쪽을 그릴 해상도. 픽셀 × 72/DPI = PDF 포인트


def _tesseract_kor() -> bool:
    if not shutil.which("tesseract"):
        return False
    try:
        r = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return "kor" in (r.stdout + r.stderr).split()  # 버전에 따라 목록이 stderr로 나온다


def ocr_backend() -> str | None:
    """쓸 글자 인식: "tesseract" | "llm" | None(없음)."""
    forced = llm.setting("ZINGGUM_OCR").strip().lower()
    if forced in ("tesseract", "llm"):
        return forced
    if forced == "off":
        return None
    if _tesseract_kor():
        return "tesseract"
    return "llm" if llm.available() else None


def _png(page) -> bytes:
    buf = io.BytesIO()
    page.to_image(resolution=DPI).original.save(buf, format="PNG")
    return buf.getvalue()


def parse_tesseract_tsv(tsv: str, scale: float) -> list[dict]:
    """tesseract TSV의 단어를 (block, par, line)으로 묶어 줄로. bbox는 픽셀 × scale(PDF 포인트)."""
    rows = tsv.splitlines()
    if not rows:
        return []
    head = rows[0].split("\t")
    groups: dict[tuple, dict] = {}  # 처음 나온 순서 = 읽는 순서
    for raw in rows[1:]:
        cols = raw.split("\t")
        if len(cols) < len(head):
            continue
        r = dict(zip(head, cols))
        text = r["text"].strip()
        if r["level"] != "5" or not text or float(r["conf"]) < 0:
            continue
        x0, top = int(r["left"]), int(r["top"])
        x1, bottom = x0 + int(r["width"]), top + int(r["height"])
        g = groups.setdefault((r["page_num"], r["block_num"], r["par_num"], r["line_num"]), {"words": [], "box": [x0, top, x1, bottom]})
        g["words"].append(text)
        b = g["box"]
        g["box"] = [min(b[0], x0), min(b[1], top), max(b[2], x1), max(b[3], bottom)]
    return [{"bbox": [round(v * scale, 1) for v in g["box"]], "text": " ".join(g["words"])} for g in groups.values()]


def _tesseract(png: bytes) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        img = Path(tmp) / "page.png"
        img.write_bytes(png)
        r = subprocess.run(["tesseract", str(img), "stdout", "-l", "kor+eng", "--psm", "6", "tsv"],
                           capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"tesseract 실패: {r.stderr.strip()[:300]}")
    return r.stdout


def ocr_page(page, *, backend: str, usage: dict | None = None, info: dict | None = None) -> list[dict]:
    """pdfplumber 쪽 하나를 그려 글자를 인식한다. [{"bbox": [...]|None, "text": str}], 읽는 순서.
    usage를 주면 LLM 토큰 사용량을 더해 넣고, info를 주면 응답 모델명을 info["model"]에 적는다."""
    png = _png(page)
    if backend == "tesseract":
        return parse_tesseract_tsv(_tesseract(png), 72 / DPI)
    if backend == "llm":
        res = llm.ocr_page(png)
        if info is not None:
            info["model"] = res.model
        if usage is not None:
            for k, v in res.usage.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    usage[k] = usage.get(k, 0) + v
        return [{"bbox": None, "text": t.strip()} for t in res.data.get("lines", []) if t.strip()]
    raise ValueError(f"모르는 글자 인식 방식: {backend}")
