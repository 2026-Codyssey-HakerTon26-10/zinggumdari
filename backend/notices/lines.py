"""원문 → 줄 목록 (docs/api.md §8, SPEC §10.1).

줄 하나: {"id", "page", "bbox", "text", "mark"}
- PDF: pdfplumber 단어를 같은 높이끼리 묶는다. 줄 ID는 p{쪽}-l{줄}, 좌표는 단어 상자를 합친 것.
  좌표는 PDF 포인트, 왼쪽 위가 원점, [x0, top, x1, bottom]. 화면은 쪽 크기로 나눠 비율로 그린다.
- 텍스트(웹 원문, API 산문): 줄바꿈과 항목 기호(○, -, ※) 단위. 줄 ID는 l{줄}, page와 bbox는 None.
- mark: 조건 신호어(signals.json)가 있는 줄. LLM이 표시된 줄마다 근거로 쓰거나 라벨을 단다.

근거 ID는 {doc_id}:{줄 ID}다. 이미지 스캔 PDF(텍스트 층 없음)는 받지 않는다.
"""

from __future__ import annotations

import json
import re
import statistics
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

SIGNALS_PATH = Path(__file__).with_name("signals.json")
SCAN_CHARS_PER_PAGE = 30   # 쪽당 글자가 이보다 적으면 이미지 스캔으로 본다

Line = dict


class ScannedPdf(ValueError):
    """텍스트 층이 없는 PDF. 받지 않는다."""


def signals() -> list[str]:
    return json.loads(SIGNALS_PATH.read_text(encoding="utf-8"))["words"]


def is_marked(text: str, words: list[str] | None = None) -> bool:
    squeezed = re.sub(r"\s+", "", text)
    return any(w in squeezed for w in (words or signals()))


def normalize(text: str) -> str:
    """근거 대조용. NFKC 후 공백을 전부 지운다."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or ""))


# ---- 텍스트 ----------------------------------------------------------------

_BULLET = re.compile(r"\s+(?=[○●◦▪□■※])|\s+(?=-\s)")


def split_text(text: str) -> list[str]:
    out = []
    for raw in unicodedata.normalize("NFC", text or "").splitlines():
        for piece in _BULLET.split(raw):
            piece = re.sub(r"[ \t ]+", " ", piece).strip()
            if piece:
                out.append(piece)
    return out


def text_lines(text: str) -> list[Line]:
    words = signals()
    return [{"id": f"l{i}", "page": None, "bbox": None, "text": t, "mark": is_marked(t, words)}
            for i, t in enumerate(split_text(text), 1)]


class _HtmlText(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "table", "section",
             "article", "ul", "ol", "th"}
    SKIP = {"script", "style", "noscript", "head", "nav", "footer", "header", "button", "form", "iframe"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")
        elif tag in ("td",):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = _HtmlText()
    p.feed(html)
    return "".join(p.parts)


# ---- PDF -------------------------------------------------------------------

def _r(v: float) -> float:
    return round(float(v), 1)


def _union(boxes: list[list[float]]) -> list[float]:
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _group(words: list[dict]) -> list[list[dict]]:
    """같은 높이의 단어를 한 줄로. 표의 같은 행은 한 줄이 된다."""
    rows: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if rows:
            ref = statistics.median(x["top"] for x in rows[-1])
            if abs(w["top"] - ref) <= max(2.0, (w["bottom"] - w["top"]) * 0.5):
                rows[-1].append(w)
                continue
        rows.append([w])
    return [sorted(r, key=lambda w: w["x0"]) for r in rows]


def pdf_lines(path: Path) -> tuple[list[Line], list[dict]]:
    """(줄 목록, 쪽 크기). 텍스트 층이 없으면 ScannedPdf."""
    import pdfplumber   # 의존성은 PDF를 다룰 때만 필요하다

    words_all = signals()
    lines, pages, chars = [], [], 0
    with pdfplumber.open(path) as pdf:
        for no, page in enumerate(pdf.pages, 1):
            pages.append({"page": no, "width": _r(page.width), "height": _r(page.height)})
            # 굵게 보이려고 같은 글자를 겹쳐 찍은 PDF가 있다("시시시시흥흥흥흥"). 겹친 글자는 하나로 친다
            words = page.dedupe_chars().extract_words(x_tolerance=1.5, y_tolerance=3, keep_blank_chars=False)
            chars += sum(len(w["text"]) for w in words)
            for k, row in enumerate(_group(words), 1):
                text = " ".join(w["text"] for w in row)
                box = _union([[_r(w["x0"]), _r(w["top"]), _r(w["x1"]), _r(w["bottom"])] for w in row])
                lines.append({"id": f"p{no}-l{k}", "page": no, "bbox": box, "text": text,
                              "mark": is_marked(text, words_all)})
    if not pages or chars < SCAN_CHARS_PER_PAGE * len(pages):
        raise ScannedPdf("이미지 스캔 PDF(텍스트 층 없음)는 받지 않는다")
    return lines, pages


# ---- 진입점 -----------------------------------------------------------------

def kind_of(path: Path) -> str:
    head = path.read_bytes()[:8]
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\xd0\xcf\x11\xe0") or path.suffix.lower() in (".hwp", ".hwpx"):
        return "hwp"
    return "html" if path.suffix.lower() in (".html", ".htm") else "text"


def to_lines(doc_id: str, src: str) -> list[Line]:
    """원문 → 줄. src는 파일 경로(PDF, HTML, 텍스트)이거나 API 산문 그 자체다.

    이미 등록된 원문은 backend.notices.store.load_lines(doc_id)로 읽는다. 이 함수는 새로 만든다.
    """
    path = Path(src)
    try:
        is_file = len(src) < 1024 and path.is_file()
    except OSError:
        is_file = False
    if not is_file:
        return text_lines(src)
    kind = kind_of(path)
    if kind == "pdf":
        return pdf_lines(path)[0]
    if kind == "hwp":
        raise ValueError("HWP는 받지 않는다")
    raw = path.read_text(encoding="utf-8", errors="replace")
    return text_lines(html_to_text(raw) if kind == "html" else raw)


def find_quote(lines: list[Line], quote: str) -> list[str]:
    """사람이 쓴 원문 문장이 걸친 줄 ID들. 못 찾으면 []. 손 조건표 quote → evidence 변환에 쓴다.

    NFKC와 공백 제거 뒤 부분 일치. 같은 쪽 안에서만 줄을 이어 찾는다.
    """
    target = normalize(quote)
    if not target:
        return []
    groups: dict[object, list[Line]] = {}
    for ln in lines:
        groups.setdefault(ln["page"], []).append(ln)
    for group in groups.values():
        hay, owner = [], []
        for ln in group:
            piece = normalize(ln["text"])
            hay.append(piece)
            owner.extend([ln["id"]] * len(piece))
        at = "".join(hay).find(target)
        if at >= 0:
            return list(dict.fromkeys(owner[at:at + len(target)]))
    return []
