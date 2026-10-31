"""조건의 field에 맞는 프로필 값 찾기. 계산 칸(나이, 기간, 부부합산 소득, 소득 %)도 여기서 만든다.

resolve()는 셋 중 하나를 돌려준다.
  Values([...])  비교할 값 후보. 출생연도만 있는 나이는 두 값이다.
  Ask(field)     값이 없다. 이 칸을 물으면 된다(계산 칸이면 재료 칸).
  Check(why)     값이 있어도 확정할 수 없다(기준표 없음, 소득인정액 등).
"""

from dataclasses import dataclass
from datetime import date

from backend.engine.constants import STANDARDS

# 시간이 지나면 커지는 칸. >=·> 조건에서 떨어지면 시간이 지나 열릴 수 있다(opens_later).
GROWING = {"age", "marriage_years", "residence_months", "subscription_months", "support_years",
           "homeless_years", "youngest_child_age", "apply_date"}


COUPLE = {"예비부부", "신혼", "기혼"}

# 계산 칸 → (재료 칸, 단위)
_SPAN = {"marriage_years": ("marriage_date", "years"), "residence_months": ("move_in_date", "months"),
         "subscription_months": ("joined_date", "months"), "support_years": ("support_start_date", "years")}


@dataclass
class Values:
    items: list


@dataclass
class Ask:
    field: str


@dataclass
class Check:
    why: str


def months_between(start: str, today: date) -> int | None:
    try:
        d = date.fromisoformat(str(start)[:10])
    except (TypeError, ValueError):
        return None
    return (today.year - d.year) * 12 + today.month - d.month - (today.day < d.day)


def ages(birth_year, today: date) -> list[int] | None:
    """출생연도만 있으므로 만 나이는 (올해 − 출생연도 − 1)과 (올해 − 출생연도) 중 하나다."""
    if birth_year is None:
        return None
    return [today.year - int(birth_year) - 1, today.year - int(birth_year)]


def income_couple(person: dict) -> Values | Ask:
    status = person.get("marital_status")
    if status is None:
        return Ask("marital_status")
    if person.get("income_self") is None:
        return Ask("income_self")
    if status not in COUPLE:
        return Values([person["income_self"]])
    if person.get("income_spouse") is None:
        return Ask("income_spouse")
    return Values([person["income_self"] + person["income_spouse"]])


def _monthly(person: dict, field: str) -> Values | Ask:
    if field == "income_couple":
        return income_couple(person)
    src = "income_household" if field in ("income_band_median", "income_band_urban") else field
    v = person.get(src)
    return Ask(src) if v is None else Values([v])


def _income(person: dict, cond: dict, year: int) -> Values | Ask | Check:
    field = cond["field"]
    basis = {"income_band_median": "median_pct", "income_band_urban": "urban_worker_pct"}.get(field) \
        or cond.get("income_basis")
    if field == "income_recognized" or basis == "recognized":
        return Check("소득인정액은 재산 환산이 필요해요")
    got = _monthly(person, field)
    if not isinstance(got, Values):
        return got
    monthly = got.items[0]
    if basis in (None, "absolute_monthly"):
        return Values([monthly])
    if basis == "absolute_annual":
        return Values([monthly * 12])
    size = person.get("household_size")
    if size is None:
        return Ask("household_size")
    table = STANDARDS.get(basis, {}).get(year)
    if not table or int(size) not in table:
        return Check(f"{year}년 {'기준 중위소득' if basis == 'median_pct' else '도시근로자 소득'} 기준표가 없어요"
                     if not table else "7인 이상 가구는 기준표가 없어요")
    return Values([monthly / table[int(size)] * 100])


def resolve(person: dict, cond: dict, today: date, year: int) -> Values | Ask | Check:
    field = cond["field"]
    if field.startswith("income"):
        return _income(person, cond, year)
    if field == "age":
        a = ages(person.get("birth_year"), today)
        return Ask("birth_year") if a is None else Values(a)
    if field == "apply_date":
        return Values([today.isoformat()])
    if field == "marriage_years" and not person.get("marriage_date"):
        status = person.get("marital_status")
        if status is None:
            return Ask("marital_status")
        if status in ("미혼", "예비부부", "이혼·사별"):
            return Values([None])   # 혼인신고 전이면 혼인 기간 조건은 탈락(api.md §1)
        return Ask("marriage_date")
    if field == "subscription_months" and person.get("has_account") == "N":
        return Values([0])
    if field in _SPAN:
        src, unit = _SPAN[field]
        m = months_between(person.get(src), today)
        if m is None:
            return Ask(src)
        return Values([m // 12 if unit == "years" else m])
    if field == "qual_code":
        quals = person.get("qualifications")
        if not quals:
            return Ask("qual_code")
        return Values([[q.get("qual_code") for q in quals]])
    if field in ("history", "homeless_years"):
        return Check("이력 조건은 아직 판정하지 않아요")
    v = person.get(field)
    return Ask(field) if v is None else Values([v])
