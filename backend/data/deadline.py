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


def _dates(text: str) -> list[date]:
    out = []
    for y, m, d in _DATE.findall(text):
        try:
            out.append(date(int(y), int(m), int(d)))
        except ValueError:
            continue
    return out


def parse_deadline(text: str | None) -> dict:
    raw = (text or "").strip()
    if not raw:
        return {"type": "미정", "date": None, "text": raw}
    found = _dates(raw)
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
