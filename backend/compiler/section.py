"""자격 구간 자르기와 신호어 표시(SPEC §9.2 1~2단계). 규칙만 쓰고 LLM은 부르지 않는다."""

from __future__ import annotations

import re

from backend.compiler.vocab import SECTION_END, SECTION_START, SIGNAL_WORDS

# API 산문은 전체가 자격 구간이다.
API_SOURCES = {"gov24", "local", "central", "api"}

_WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return _WS.sub(" ", text or "").strip()


def _compact(text: str) -> str:
    """띄어쓰기를 지운 글. 자간을 벌린 제목("신 청 자 격")도 잡으려고 쓴다."""
    return _WS.sub("", text or "")


# --- 신호어 표시 ---

# 두 글자 이상 신호어는 띄어쓰기를 지운 글에서 찾는다.
_WORD_RE = re.compile("|".join(sorted({re.escape(_compact(w)) for w in SIGNAL_WORDS if len(w.strip()) > 1}, key=len, reverse=True)))
# "만 ", "세 " 같은 한 글자 신호어는 수에 붙을 때만 본다("만 19세", "19세 ").
_ONE = sorted({w.strip() for w in SIGNAL_WORDS if len(w.strip()) == 1})
# 수 + 단위(19세, 24개월, 2년, 5천만 원, 120%)와 날짜(접수 기간 "2026. 11. 3. ~")도 조건일 가능성이 높아 표시한다.
_NUM_RE = re.compile(
    r"\d[\d,.]*\s*(?:세|개월|년|억|천\s*만|만\s*원|원|%|％|퍼센트)"
    r"|(?<!\d)\d{4}\s*[.\-/]\s*\d{1,2}\s*[.\-/]\s*\d{1,2}(?!\d)"
    + "".join(f"|\\d\\s*{re.escape(c)}|{re.escape(c)}\\s*\\d" for c in _ONE)
)


def is_marked(text: str) -> bool:
    return bool(_WORD_RE.search(_compact(text)) or _NUM_RE.search(_norm(text)))


def mark_lines(lines: list[dict]) -> list[dict]:
    """줄을 복사해 "mark"를 다시 단다. 표의 행도 보통 줄처럼 본다."""
    return [{**l, "mark": is_marked(l.get("text", ""))} for l in lines]


# --- 제목 ---

_HEADING_RE = re.compile(
    r"^(?:"
    r"[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]\s*[.)]?"          # Ⅰ. Ⅱ
    r"|[IVX]{1,4}\s*[.)]"                     # II.
    r"|\d{1,2}\s*[.)](?!\d)"                  # 1. 1)
    r"|[가나다라마바사아자차카타파하]\s*[.)]"  # 가. 나)
    r"|[□■◆◇▣▶▷◈◼◻]"                         # 상자·도형 기호(○ - ※ ●는 항목 기호라 뺀다)
    r"|[<〈《\[【［].{1,30}?[>〉》\]】］]"       # <신청자격> [소득기준] 【제출서류】
    r"|제\s*\d{1,2}\s*[장절편관]"              # 제2장
    r")"
)
_TAIL = re.compile(r"[\s.:;,!?。…)\]】>〉》」』]+$")


def is_heading(text: str) -> bool:
    """짧고(띄어쓰기 빼고 40자 이하) 제목 기호로 시작하며 "~다/~요/~것"으로 끝나는 문장이 아닌 줄."""
    t = _norm(text)
    if not t or len(_compact(t)) > 40 or not _HEADING_RE.match(t):
        return False
    tail = _TAIL.sub("", t)
    return not tail.endswith(("다", "요", "것"))


def _has(text: str, words: list[str]) -> bool:
    c = _compact(text)
    return any(_compact(w) in c for w in words)


# --- 자격 구간 ---

def _info(kept: list[dict], found_by: str) -> dict:
    return {"from": kept[0]["id"] if kept else None, "to": kept[-1]["id"] if kept else None,
            "found_by": found_by, "lines": len(kept)}


def cut_section(lines: list[dict], *, source: str) -> tuple[list[dict], dict]:
    """자격 구간의 줄만 남긴다. 시작 말이 있는 제목에서 열고, 시작 말 없이 끝 말만 있는 제목에서 닫는다.
    구간은 여러 개일 수 있다(트랙이 여럿인 공고). 못 찾으면 전체를 쓰고 found_by "none"."""
    if source in API_SOURCES:
        return list(lines), _info(lines, "api")
    kept, inside = [], False
    for l in lines:
        text = l.get("text", "")
        if is_heading(text):
            if _has(text, SECTION_START):
                inside = True
            elif _has(text, SECTION_END):
                inside = False
        if inside:
            kept.append(l)
    if not kept:
        return list(lines), _info(lines, "none")
    return kept, _info(kept, "heading")


# --- 트랙 ---

# 앞에 있을수록 먼저 본다. 한 제목에 여럿이면 글에서 먼저 나온 것.
TRACKS = {
    "신혼부부": "newlywed", "생애최초": "first_home", "다자녀": "multi_child", "노부모부양": "elderly_parent",
    "신생아": "newborn", "청년": "youth", "기관추천": "institution", "일반공급": "general",
}


def find_tracks(lines: list[dict]) -> list[dict]:
    """공급·지원 트랙 이름이 든 제목 줄. 같은 트랙이 여러 번 나오면 나온 만큼 돌려준다(트랙 구간 나누기용)."""
    out = []
    for l in lines:
        text = l.get("text", "")
        if not is_heading(text):
            continue
        c = _compact(text)
        hits = [(c.find(k), slug) for k, slug in TRACKS.items() if k in c]
        if hits:
            out.append({"track": min(hits)[1], "title": _norm(text), "line": l["id"]})
    return out
