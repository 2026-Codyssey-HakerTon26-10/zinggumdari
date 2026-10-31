"""원문 → 줄 목록(api.md §8, SPEC §10.1). 형식을 가려 reader를 부르고 줄 ID와 신호어 표시(mark)를 붙인다.

- PDF: 줄 ID는 p{쪽}-l{n}(쪽마다 1부터, 읽는 순서). 스캔 쪽은 글자 인식 줄이고 src "ocr"을 단다.
- HWP·HWPX·텍스트·HTML: 줄 ID는 l{n}. 줄바꿈과 줄 가운데서 새 항목을 여는 기호(○ ※ ▶ …) 앞에서 나눈다.
- 표 행은 칸을 " | "로 잇고 table(표 ID)을 단다.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path

from backend.compiler.readers import UnsupportedDocument
from backend.compiler.readers.hwp import read_hwp
from backend.compiler.readers.hwpx import read_hwpx, reader_output
from backend.compiler.readers.pdf import read_pdf
from backend.compiler.section import mark_lines
from backend.compiler.vocab import RRN_PATTERN

REPO_ROOT = Path(__file__).resolve().parents[2]
UNSUPPORTED = "지원하지 않는 형식입니다. PDF, HWP, HWPX, 텍스트만 받습니다."

_SUFFIX = {".pdf": "pdf", ".hwp": "hwp", ".hwpx": "hwpx", ".txt": "text", ".md": "text", ".html": "html", ".htm": "html"}
_READERS = {"hwp": read_hwp, "hwpx": read_hwpx}
_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
# 줄 가운데서 새 항목을 여는 기호. ○◦•□■는 뒤에 빈칸이 있을 때만("○○시" 같은 가림 글자는 안 나눈다)
_BULLET = re.compile(r"\s+(?=[○◦•□■]\s|[※▶])")
_HTML_HEAD = re.compile(r"\s*<(?:!doctype\s+html|html)[\s>]", re.I)
_RRN = re.compile(RRN_PATTERN)
_PDF_META = ("unread_pages", "ocr_calls", "ocr_usage", "ocr_model", "ocr_errors", "ocr_layer_pages")
_WS = re.compile(r"\s+")


# --- 공개 함수 ---

def read_document(doc_id: str, src: str | Path, *, ocr_cache: Path | None = None,
                  reuse_ocr: bool = True, llm_ocr: bool = False) -> tuple[dict, list[dict]]:
    """원문 → (meta, 줄 목록). src가 Path면 파일, str이면 언제나 원문 텍스트다(파일 경로처럼 보여도 열지 않는다).
    읽을 수 없는 원문이면 UnsupportedDocument. ocr_cache·reuse_ocr는 PDF 글자 인식 캐시(readers/pdf.py).
    llm_ocr: 스캔 쪽을 네이토 API로 글자 인식해도 되나. 사용자 업로드는 False(기본, tesseract만), 우리가 넣는 공고 원문만 True."""
    _check_id(doc_id)
    if isinstance(src, Path):
        if not src.is_file():
            raise FileNotFoundError(src)
        data = src.read_bytes()
        doc = _read_file(src, data, ocr_cache, reuse_ocr, llm_ocr)
    else:
        data = src.encode("utf-8")
        doc = _text_doc(src)
    lines = _number(doc)
    meta = {"doc_id": doc_id, "kind": doc["kind"], "pages": doc["pages"], "text_layer": doc["text_layer"],
            "ocr": doc["ocr"], "sha256": hashlib.sha256(data).hexdigest(), "n_lines": len(lines)}
    # PDF: 못 읽은 스캔 쪽, 글자 인식 호출 수·토큰·모델·실패 이유, 글자 인식 층 쪽
    meta |= {k: doc[k] for k in _PDF_META if k in doc}
    return meta, lines


def to_lines(doc_id: str, src: str | Path, *, llm_ocr: bool = False) -> list[dict]:
    return read_document(doc_id, src, llm_ocr=llm_ocr)[1]


def save_lines(doc_id: str, lines: list[dict], meta: dict | None = None,
               out_dir: Path = REPO_ROOT / "data/notices") -> Path:
    """{doc_id}.lines.json(한 줄에 한 요소)과, meta가 있으면 {doc_id}.meta.json을 쓴다. lines 파일 경로를 돌려준다."""
    _check_id(doc_id)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{doc_id}.lines.json"
    body = ",\n".join("  " + json.dumps(l, ensure_ascii=False) for l in lines)
    path.write_text(f"[\n{body}\n]\n" if lines else "[]\n", encoding="utf-8")
    if meta is not None:
        (out_dir / f"{doc_id}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _birth_date_like(front: str) -> bool:
    """주민등록번호 앞 6자리는 생년월일(YYMMDD)이다. 월과 일이 될 수 없는 숫자는 주민등록번호가 아니다."""
    return 1 <= int(front[2:4]) <= 12 and 1 <= int(front[4:6]) <= 31


def has_rrn(lines: list[dict]) -> bool:
    """주민등록번호 꼴이 있는 줄이 있는가(/ingest가 거부한다).

    LH 행복주택 공고문에는 「(주민등록번호 표시 예시) 123456-1234567」이 들어 있다. 앞자리가 날짜가 될 수 없는
    이런 예시 번호로 공고 전체를 거부하지 않게, 앞 6자리가 생년월일 꼴일 때만 주민등록번호로 본다.
    """
    return any(_birth_date_like(m.group()[:6]) for l in lines for m in _RRN.finditer(l.get("text") or ""))


# --- 형식 가리기 ---

def _check_id(doc_id: str) -> None:
    # ":"는 근거 ID({doc_id}:{줄 ID})의 구분자다. "/"·"\"·앞 "."은 저장 경로를 벗어나지 않게 막는다
    if not doc_id or doc_id.startswith(".") or any(c in doc_id for c in ":/\\"):
        raise ValueError(f"doc_id에 쓸 수 없는 글자가 있습니다: {doc_id!r}")


def _sniff(data: bytes) -> str | None:
    """앞 바이트로 가린다. 확장자가 틀린 파일(.hwp인 HWPX 등)도 맞는 reader로 간다."""
    if b"%PDF-" in data[:1024]:
        return "pdf"
    if data.startswith((_OLE, b"HWP Document File")):  # HWP 5.0, HWP 3.x(read_hwp가 안내 문구로 거부)
        return "hwp"
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(BytesIO(data)) as z:
                return "hwpx" if b"hwp" in z.read("mimetype").lower() else None
        except Exception:  # 깨진 zip은 zlib.error·OSError·NotImplementedError 등 여러 가지로 터진다
            return None
    return None


def _read_file(path: Path, data: bytes, ocr_cache: Path | None = None, reuse_ocr: bool = True,
               llm_ocr: bool = False) -> dict:
    kind = _sniff(data) or _SUFFIX.get(path.suffix.lower())
    if kind == "pdf":
        return read_pdf(path, ocr_cache=ocr_cache, reuse=reuse_ocr, llm_ocr=llm_ocr)
    if kind in _READERS:
        return _READERS[kind](path)
    if b"\0" in data:
        raise UnsupportedDocument(UNSUPPORTED)
    for enc in ("utf-8-sig", "cp949"):  # 공공기관 텍스트는 EUC-KR(CP949)도 많다
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnsupportedDocument(UNSUPPORTED)
    return _html_doc(text) if kind == "html" else _text_doc(text)


# --- 텍스트·HTML ---

def _text_doc(text: str) -> dict:
    if _HTML_HEAD.match(text):
        return _html_doc(text)
    return reader_output("text", [(text, None)])


def _html_doc(html: str) -> dict:
    p = _HTMLText()
    p.feed(html)
    p.close()
    p.flush()
    return reader_output("text", p.out)


_BLOCK = {"address", "article", "aside", "blockquote", "br", "caption", "dd", "div", "dl", "dt", "fieldset", "figcaption",
          "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav", "ol", "p",
          "pre", "section", "table", "td", "th", "title", "tr", "ul"}  # 안쪽 표의 칸·행은 칸 글자 안 빈칸
_SKIP = {"script", "style", "noscript", "template", "svg"}


class _HTMLText(HTMLParser):
    """HTML → (글자, 표 ID) 목록. script·style은 버리고 블록 태그는 줄바꿈으로, 바깥 표는 행마다 한 줄(칸은 " | ")로.
    표 안의 표는 칸 글자로 펼친다(hwp.py·hwpx.py와 같다). 원본의 줄바꿈은 <pre> 밖에서는 빈칸이다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[tuple[str, str | None]] = []
        self.buf: list[str] = []
        self.skip = self.depth = self.tables = self.pre = 0
        self.cells: list[list[str]] | None = None  # 바깥 표의 지금 행

    def flush(self) -> None:
        if self.buf:
            self.out.append(("".join(self.buf), None))
            self.buf = []

    def _row(self) -> None:
        self.flush()  # 행 앞의 칸 밖 글자(캡션)가 먼저
        if self.cells:
            row = " | ".join(" ".join("".join(c).split()) for c in self.cells)
            if row.replace("|", "").strip():
                self.out.append((row, f"t{self.tables}"))
        self.cells = None

    def _break(self) -> None:
        if self.cells:
            self.cells[-1].append(" ")
        elif self.depth == 0:
            self.buf.append("\n")

    def handle_starttag(self, tag, attrs):
        if tag in ("pre", "textarea"):
            self.pre += 1
        if tag in _SKIP:
            self.skip += 1
        elif tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.flush()
                self.tables += 1
        elif self.depth == 1 and tag == "tr":
            self._row()
            self.cells = []
        elif self.depth == 1 and tag in ("td", "th"):
            if self.cells is None:  # <tr> 없이 바로 칸
                self.cells = []
            self.cells.append([])
        elif tag in _BLOCK:
            self._break()

    def handle_endtag(self, tag):
        if tag in ("pre", "textarea"):
            self.pre = max(0, self.pre - 1)
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag == "table" and self.depth:
            self.depth -= 1
            if self.depth == 0:
                self._row()
        elif self.depth == 1 and tag == "tr":
            self._row()
        elif tag in _BLOCK:
            self._break()

    def handle_data(self, data):
        if self.skip:
            return
        if not self.pre:
            data = _WS.sub(" ", data)  # 들여 쓴 소스의 줄바꿈이 문장을 자르지 않게
        if self.cells:
            self.cells[-1].append(data)
        elif self.depth == 0 or data.strip():  # 표의 칸 밖 글자(캡션 등)는 보통 줄
            self.buf.append(data)


# --- 줄 ID ---

def _split(text: str) -> list[str]:
    """줄바꿈과 새 항목 기호 앞에서 나누고 빈칸을 하나로 줄인다. 빈 줄은 버린다."""
    return [s for part in text.splitlines() for piece in _BULLET.split(part) if (s := " ".join(piece.split()))]


def _number(doc: dict) -> list[dict]:
    """reader 줄 → api.md §8 줄. PDF 줄과 표 행은 그대로 두고 나머지는 _split으로 나눈다."""
    pdf = doc["kind"] == "pdf"
    out, count = [], {}
    for l in doc["lines"]:
        page, table = l.get("page"), l.get("table")
        for text in [l["text"]] if pdf or table else _split(l["text"]):
            n = count[page] = count.get(page, 0) + 1
            line = {"id": f"p{page}-l{n}" if pdf else f"l{n}", "page": page, "bbox": l.get("bbox"), "text": text, "mark": False}
            if l.get("src") == "ocr":
                line["src"] = "ocr"
            if table:
                line["table"] = table
            out.append(line)
    return mark_lines(out)
