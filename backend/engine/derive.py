"""프로필 계산 칸(api.md §2 derived). 저장하지 않고 응답할 때 계산한다.

- age: 출생연도만 있어 만 나이는 두 값이다
- income_couple: 미혼·이혼·사별이면 본인, 예비부부·신혼·기혼이면 본인 + 배우자(하나라도 모르면 null)
- tags: 청년(만 19~39세 나이 묶음), 생애 단계(예비부부·신혼·자녀·다자녀), 주거(무주택). 여러 개
- income_band_median·urban: 가구 월소득 ÷ 기준표(가구원 수) × 100. 민감정보 동의가 없거나 기준표가 없으면 null
"""

from datetime import date

from backend.engine.constants import STANDARDS
from backend.engine.values import Values, ages, income_couple

YOUTH = (19, 39)


def _band(me: dict, basis: str, year: int) -> float | None:
    size, monthly = me.get("household_size"), me.get("income_household")
    table = STANDARDS.get(basis, {}).get(year) or {}
    if type(size) is not int or size not in table or not isinstance(monthly, (int, float)) or isinstance(monthly, bool):
        return None
    return round(monthly / table[size] * 100, 1)


def tags(me: dict, today: date) -> list[str]:
    out = []
    try:
        a = ages(me.get("birth_year"), today)
    except (TypeError, ValueError):
        a = None
    if a and a[1] >= YOUTH[0] and a[0] <= YOUTH[1]:
        out.append("youth")
    status = me.get("marital_status")
    if status == "예비부부":
        out.append("marriage_planned")
    if status == "신혼":
        out.append("newlywed")
    kids = me.get("children_count")
    if isinstance(kids, int) and not isinstance(kids, bool):
        if kids == 1:
            out.append("child")
        elif kids >= 2:
            out.append("multi_child")
    if me.get("is_homeless") == "Y":
        out.append("homeless")
    return out


def derive(profile: dict, today: date | None = None) -> dict:
    today = today or date.today()
    me = profile.get("self", profile)
    sensitive_ok = bool((profile.get("consents") or {}).get("sensitive"))
    try:
        age = ages(me.get("birth_year"), today)
    except (TypeError, ValueError):
        age = None
    couple = income_couple(me)
    return {
        "age": age,
        "income_couple": couple.items[0] if isinstance(couple, Values) else None,
        "tags": tags(me, today),
        "income_band_median": _band(me, "median_pct", today.year) if sensitive_ok else None,
        "income_band_urban": _band(me, "urban_worker_pct", today.year) if sensitive_ok else None,
    }
