"""행안부 혜택 「신청기한」 자유 서술을 조건 JSON의 deadline 모양으로.

{"type": "상시" | "기간" | "미정" | "기타", "date": 마감일 ISO 또는 None, "text": 원문}

형식은 첫 덤프로 확인한다(python -m backend.data.report). 날짜를 못 찾으면 date는 None이고
type은 "기타"다. 원문에 없는 날짜를 만들지 않는다.
"""

from __future__ import annotations

import re
from datetime import date

ALWAYS = ("상시", "연중", "수시")
UNDECIDED = ("미정", "추후", "별도 공지", "별도공지", "예산 소진", "예산소진")

_DATE = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})\s*일?")
# "2026.11.1.~11.30."처럼 끝 날짜에 연도를 빼고 쓴 범위. 연도는 앞 날짜에서 받는다
_RANGE_TAIL = re.compile(r"^\.?\s*(?:\([^)]{0,6}\))?\s*[~∼～〜–—]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})(?!\d)(?!\s*[.\-/년]\s*\d)")
# 날짜 뒤에 이 말이 오면 마감이 아니라 대상 기준일이다("2024.1.1. 이후 출생아", "2026.3.1.부터")
_NOT_DEADLINE = re.compile(r"^\.?\s*\)?\s*(이후|부터|출생|기준)")
# "2026년 상반기"처럼 연도와 반기만 적은 것. 그 반기의 마지막 날을 마감으로 본다("매년 3~4월"은 연도가 없어 읽지 않는다)
_HALF = re.compile(r"(20\d{2})\s*년?\s*(상|하)반기")


def _dates(text: str) -> list[date]:
    out = []
    for m in _DATE.finditer(text):
        try:
            start = date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            continue
        rest = text[m.end():]
        tail = _RANGE_TAIL.match(rest)
        if tail:
            try:
                end = date(start.year, int(tail[1]), int(tail[2]))
            except ValueError:
                end = None
            if end is not None:
                out.append(end if end >= start else end.replace(year=start.year + 1))
                continue
        if _NOT_DEADLINE.match(rest):
            continue
        out.append(start)
    return out


def parse_deadline(text: str | None) -> dict:
    raw = (text or "").strip()
    if not raw:
        return {"type": "미정", "date": None, "text": raw}
    found = _dates(raw)
    found += [date(int(y), 6, 30) if h == "상" else date(int(y), 12, 31) for y, h in _HALF.findall(raw)]
    if found:
        return {"type": "기간", "date": max(found).isoformat(), "text": raw}
    if any(word in raw for word in ALWAYS):
        return {"type": "상시", "date": None, "text": raw}
    if any(word in raw for word in UNDECIDED):
        return {"type": "미정", "date": None, "text": raw}
    return {"type": "기타", "date": None, "text": raw}


def is_closed(deadline: dict | None, today: date) -> bool:
    """마감일이 지났으면 True. 상시·미정·날짜 없음은 열린 것으로 둔다."""
    if not deadline or not deadline.get("date"):
        return False
    return date.fromisoformat(deadline["date"]) < today
