"""PDF 읽기(SPEC §10.1). 글자 층이 있는 쪽은 pdfplumber 단어를 같은 줄끼리 묶고, 표는 행마다 한 줄(칸은 " | ")로 만든다.
글자 층이 없는 쪽(이미지 스캔)은 ocr.py로 글자를 인식하고 그 줄에 src "ocr"을 단다.

쪽 가르기: 이미지가 쪽 대부분을 덮고 본문 자리에 글자가 (거의) 없으면 스캔 쪽(출력 도장·쪽 번호 꼬리말만 있어도),
본문 글자가 있으면 스캔 위에 얹은 글자 인식 층("검색 가능한 PDF")이라 그 줄에도 src "ocr"을 단다.
ToUnicode 없는 글꼴의 "(cid:N)" 글자는 읽은 글자로 치지 않는다.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from statistics import median

import pdfplumber

from backend.compiler.readers import UnsupportedDocument, ocr

MIN_CHARS = 10      # 본문 자리 글자가 이보다 적으면 글자 층이 없는 쪽으로 본다
SCAN_COVER = 0.7    # 이미지가 쪽 넓이의 이 비율 이상을 덮으면 스캔 쪽 후보
MARGIN = 0.08       # 위아래 이 비율 띠 안의 글자는 꼬리말·출력 도장으로 본다
OUTLINE_CURVES = 200  # 글자가 거의 없고 곡선이 이만큼 많으면 글자를 그림으로 바꾼 쪽
CID_SHARE = 0.3     # 글자 중 "(cid:N)"이 이 비율 이상이면 글자 층을 읽지 못한 것으로 본다
GAP = 5             # 같은 높이라도 단어 사이가 글자 폭의 이 배수보다 넓으면 다른 줄
NARROW_GAP = 2.5    # 이 배수보다 넓은 틈이 다른 줄의 틈과 같은 가로 자리에 있으면 단 사이(2단 편집)
CUT_SHARE = 0.3     # 표 행 단어 중 이 비율 이상을 칸 경계가 가로지르면 쪼개진 행(LH 공고 8건: 진짜 표 행 0.2 이하)
NO_OCR = "텍스트 층이 없는 스캔 PDF입니다. 글자 인식(tesseract 또는 네이토 API 키)이 없어 읽을 수 없습니다."
NO_OCR_UPLOAD = ("텍스트 층이 없는 스캔 PDF입니다. 올린 파일은 개인정보 보호를 위해 서버 안의 글자 인식(tesseract)으로만 "
                 "읽는데, 서버에 없어 읽을 수 없습니다. 텍스트를 고를 수 있는 PDF나 HWP를 올려 주세요.")
OCR_FAILED = "스캔 PDF의 글자 인식에 실패했습니다. 잠시 뒤 다시 올리거나 텍스트 층이 있는 PDF를 올려 주세요."
_CID = re.compile(r"\(cid:\d+\)")


def _box(ws: list[dict]) -> list[float]:
    return [round(min(w["x0"] for w in ws), 1), round(min(w["top"] for w in ws), 1),
            round(max(w["x1"] for w in ws), 1), round(max(w["bottom"] for w in ws), 1)]


def group_words(words: list[dict]) -> list[tuple[float, list[dict]]]:
    """단어(x0, x1, top, bottom, text)를 줄로 묶는다. [(줄의 세로 위치, 왼→오른 단어들)], 위→아래 순."""
    if not words:
        return []
    tol = max(2.0, 0.5 * median(w["bottom"] - w["top"] for w in words))
    char_w = median((w["x1"] - w["x0"]) / len(w["text"]) for w in words)
    rows: list[list[dict]] = []
    for w in sorted(words, key=lambda w: w["top"]):
        if rows and w["top"] - rows[-1][0]["top"] <= tol:
            rows[-1].append(w)
        else:
            rows.append([w])
    for row in rows:
        row.sort(key=lambda w: w["x0"])
    # 넓은 틈(글자 폭 × NARROW_GAP 초과)의 (줄 번호, 왼쪽 끝, 오른쪽 끝)
    gaps = [(i, a["x1"], b["x0"]) for i, row in enumerate(rows) for a, b in zip(row, row[1:])
            if b["x0"] - a["x1"] > NARROW_GAP * char_w]

    def split(i: int, a: float, b: float) -> bool:
        """아주 넓은 틈이거나, 다른 줄에도 같은 가로 자리에 틈이 있으면(단 사이) 나눈다."""
        return b - a > GAP * char_w or any(j != i and a2 < b and a < b2 for j, a2, b2 in gaps)

    out = []
    for i, row in enumerate(rows):
        seg = [row[0]]
        for w in row[1:]:
            if w["x0"] - seg[-1]["x1"] > NARROW_GAP * char_w and split(i, seg[-1]["x1"], w["x0"]):
                out.append((row[0]["top"], seg))
                seg = []
            seg.append(w)
        out.append((row[0]["top"], seg))
    return out


def _within(w: dict, box) -> bool:
    x0, top, x1, bottom = box
    return x0 <= (w["x0"] + w["x1"]) / 2 <= x1 and top <= (w["top"] + w["bottom"]) / 2 <= bottom


def _chopped(row, words: list[dict]) -> bool:
    """테두리 친 안내문 상자를 pdfplumber가 글자 폭 칸 수십 개짜리 표로 잡으면 칸 경계가 단어 가운데를 지나
    행이 " | 되며 | , 이 | 자 | …"로 쪼개진다. 진짜 표의 칸 경계는 단어 사이에 있다(붙어 읽힌 머리글 한 단어에 한 번 걸칠 수는 있다).
    경계가 행 단어의 CUT_SHARE 이상을, 모두 합쳐 두 번 이상 가로지르면 쪼개진 행이다."""
    edges = {x for c in row.cells if c for x in (c[0], c[2])}
    hits = [sum(w["x0"] + 1 < x < w["x1"] - 1 for x in edges) for w in words if _within(w, row.bbox)]
    return sum(hits) >= 2 and sum(map(bool, hits)) >= CUT_SHARE * len(hits)


def _text_lines(page, no: int) -> list[dict]:
    items = []  # (세로 위치, x0, 줄)
    words = [{**w, "text": _CID.sub("", w["text"])} for w in page.extract_words(use_text_flow=False, keep_blank_chars=False)]
    words = [w for w in words if w["text"]]
    rows, k = [], 0  # 표 행으로 낸 행 상자
    # 한 칸짜리 열만 있는 격자는 글 상자라 표로 보지 않는다. 쪼개진 행은 일반 줄로 둔다
    for t in (t for t in page.find_tables() if len(t.columns) > 1):
        got = []
        for row, cells in zip(t.rows, t.extract()):
            text = " | ".join(" ".join(_CID.sub("", c or "").split()) for c in cells)
            if text.replace("|", "").strip() and not _chopped(row, words):
                got.append(([round(v, 1) for v in row.bbox], text))
        k += bool(got)
        for bbox, text in got:
            rows.append(bbox)
            items.append((bbox[1], bbox[0], {"page": no, "bbox": bbox, "text": text, "src": "text", "table": f"p{no}-t{k}"}))

    for top, seg in group_words([w for w in words if not any(_within(w, b) for b in rows)]):
        items.append((top, seg[0]["x0"], {"page": no, "bbox": _box(seg), "text": " ".join(w["text"] for w in seg),
                                          "src": "text", "table": None}))
    items.sort(key=lambda i: (i[0], i[1]))
    return [i[2] for i in items]


def _ocr_lines(page, no: int, backend: str, usage: dict, info: dict) -> list[dict]:
    out, k = [], 0
    for l in ocr.ocr_page(page, backend=backend, usage=usage, info=info):
        table = None
        if " | " in l["text"]:  # LLM 전사는 표 한 행을 " | "로 잇는다. 이어진 행끼리 한 표
            if not (out and out[-1]["table"]):
                k += 1
            table = f"p{no}-t{k}"
        out.append({"page": no, "bbox": l["bbox"], "text": l["text"], "src": "ocr", "table": table})
    return out


def _cover(page) -> float:
    """이미지가 덮는 쪽 넓이의 비율(겹침은 무시하고 1에서 자른다)."""
    x0, top, x1, bottom = page.bbox
    area = sum(max(0, min(i["x1"], x1) - max(i["x0"], x0)) * max(0, min(i["bottom"], bottom) - max(i["top"], top))
               for i in page.images)
    return min(1.0, area / max(1.0, (x1 - x0) * (bottom - top)))


def page_kind(page) -> str:
    """"text"(글자 층) | "scan"(글자 인식할 쪽) | "ocr_layer"(스캔 위의 글자 인식 층)."""
    chars = [c for c in page.chars if not c["text"].isspace()]
    real = [c for c in chars if not _CID.fullmatch(c["text"])]
    if len(real) < len(chars) * (1 - CID_SHARE):
        real = []  # ToUnicode 없는 글꼴: 글자 층을 읽지 못한다
    if _cover(page) >= SCAN_COVER:
        _, top, _, bottom = page.bbox
        band = MARGIN * (bottom - top)
        body = [c for c in real if c["top"] > top + band and c["bottom"] < bottom - band]
        return "scan" if len(body) < MIN_CHARS else "ocr_layer"
    if not real and (chars or page.images or page.curves):
        return "scan"
    if len(real) < MIN_CHARS and len(page.curves) >= OUTLINE_CURVES:
        return "scan"
    return "text"


def _load_cache(path: Path | None, sha: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path and path.exists() else {}
    except (OSError, ValueError):
        return {}
    return data if data.get("sha256") == sha else {}


def read_pdf(path: str | Path, *, ocr_cache: Path | None = None, reuse: bool = True, llm_ocr: bool = True) -> dict:
    """PDF → reader 출력(readers/__init__.py).
    스캔 쪽은 글자 인식으로 읽는다. 인식 수단이 없거나 인식이 실패한 쪽은 빼고 unread_pages에 적는다(이유는 ocr_errors).
    읽은 줄이 하나도 없으면 UnsupportedDocument. ocr_cache(JSON 경로)를 주면 인식한 줄을 원문 해시와 함께 남기고,
    reuse면 다음에 다시 부르지 않고 읽는다(캐시 재생). llm_ocr=False면 쪽 이미지를 네이토 API로 보내지 않는다(사용자 업로드)."""
    try:
        pdf = pdfplumber.open(path)
    except Exception as e:  # 암호, 손상
        raise UnsupportedDocument("PDF를 열 수 없습니다. 암호가 걸렸거나 손상된 파일입니다.") from e
    sha = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    cache = _load_cache(ocr_cache, sha) if reuse else {}
    cached = cache.get("pages") or {}
    with pdf:
        pages = [p.dedupe_chars() for p in pdf.pages]  # 겹쳐 찍은 가짜 굵은 글씨("112200%%")
        kinds = {p.page_number: page_kind(p) for p in pages}
        need = [no for no, k in kinds.items() if k == "scan" and str(no) not in cached]
        backend = ocr.ocr_backend(allow_llm=llm_ocr) if need else cache.get("ocr")
        lines: list[dict] = []
        usage, info, unread, errors, done = {}, {}, [], [], {}
        for page in pages:
            no = page.page_number
            if kinds[no] != "scan":
                got = _text_lines(page, no)
                lines += [{**l, "src": "ocr"} for l in got] if kinds[no] == "ocr_layer" else got
            elif str(no) in cached:
                lines += cached[str(no)]
            elif not backend:
                unread.append(no)
            else:
                try:
                    done[str(no)] = _ocr_lines(page, no, backend, usage, info)
                    lines += done[str(no)]
                except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as e:  # LLMError, tesseract
                    unread.append(no)
                    errors.append(f"p{no}: {type(e).__name__}: {e}"[:300])
        scans = [no for no, k in kinds.items() if k != "text"]
        out = {"kind": "pdf", "pages": len(pages), "text_layer": not scans, "ocr": backend if (done or cached) else None,
               "lines": lines}
    if unread:
        if not lines:
            raise UnsupportedDocument(OCR_FAILED if errors else NO_OCR if llm_ocr else NO_OCR_UPLOAD)
        out["unread_pages"] = unread
    if errors:
        out["ocr_errors"] = errors
    if [no for no, k in kinds.items() if k == "ocr_layer"]:
        out["ocr_layer_pages"] = [no for no, k in kinds.items() if k == "ocr_layer"]
    if need:
        out["ocr_calls"] = len(done) + len(errors)
    if out["ocr"] == "llm":
        out["ocr_usage"] = usage
        out["ocr_model"] = info.get("model") or cache.get("model")
    if ocr_cache and done:
        ocr_cache.parent.mkdir(parents=True, exist_ok=True)
        data = {"sha256": sha, "ocr": backend, "model": info.get("model"), "pages": {**cached, **done}}
        ocr_cache.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
    return out
