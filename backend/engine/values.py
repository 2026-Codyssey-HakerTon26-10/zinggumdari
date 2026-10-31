"""조건의 field에 맞는 프로필 값 찾기. 계산 칸(나이, 기간, 부부합산 소득, 소득 %)도 여기서 만든다.

resolve()는 넷 중 하나를 돌려준다.
  Values([...])  비교할 값 후보. 출생연도만 있는 나이는 두 값이다.
  Period(start)  기간 칸. 정수로 버리지 않고 "시작일 + N"과 오늘을 날짜로 비교한다(경계가 정확하다).
  Ask(field)     값이 없다. 이 칸을 물으면 된다(계산 칸이면 재료 칸).
  Check(why)     값이 있어도 확정할 수 없다(기준표 없음, 소득인정액, 읽을 수 없는 값 등).
"""

from dataclasses import dataclass
from datetime import date

from backend.compiler.vocab import FIELDS
from backend.engine.constants import STANDARDS

# 시간이 지나면 커지는 칸. >=·> 조건에서 떨어지면 시간이 지나 열릴 수 있다(opens_later).
GROWING = {"age", "marriage_years", "residence_months", "subscription_months", "support_years",
           "homeless_years", "youngest_child_age", "apply_date"}


COUPLE = {"예비부부", "신혼", "기혼"}

# 계산 칸 → (재료 칸, 단위). 플래너도 같은 표를 쓴다.
SPAN = {"marriage_years": ("marriage_date", "years"), "residence_months": ("move_in_date", "months"),
         "subscription_months": ("joined_date", "months"), "support_years": ("support_start_date", "years")}


@dataclass
class Values:
    items: list


@dataclass
class Period:
    start: date
    unit: str   # "years" | "months"


@dataclass
class Ask:
    field: str


@dataclass
class Check:
    why: str


def parse_date(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def add_months(d: date, n: int) -> date:
    """d에서 n개월 뒤. 그 달에 같은 날이 없으면 그 달 마지막 날(8/31 + 6개월 = 2/28). 엔진과 플래너가 같이 쓴다."""
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    last = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(d.day, last))


def boundary(start: date, unit: str, n) -> date:
    """시작일에서 기간 n(단위 unit)이 꽉 차는 날."""
    return add_months(start, round(n * 12) if unit == "years" else round(n))


def months_between(start, today: date) -> int | None:
    """꽉 찬 개월 수. add_months와 같은 달력 규칙이다(boundary(start, months, k) <= today인 가장 큰 k)."""
    d = parse_date(start)
    if d is None:
        return None
    m = (today.year - d.year) * 12 + today.month - d.month
    while m > 0 and add_months(d, m) > today:
        m -= 1
    return m


def ages(birth_year, today: date) -> list[int] | None:
    """출생연도만 있으므로 만 나이는 (올해 − 출생연도 − 1)과 (올해 − 출생연도) 중 하나다."""
    if birth_year is None:
        return None
    by = int(birth_year)   # 숫자가 아니면 ValueError → resolve가 확인 필요로
    return [today.year - by - 1, today.year - by]


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
    if type(size) is not int or not isinstance(monthly, (int, float)) or isinstance(monthly, bool):
        return Check("값을 비교할 수 없어요")
    table = STANDARDS.get(basis, {}).get(year)
    if not table or int(size) not in table:
        return Check(f"{year}년 {'기준 중위소득' if basis == 'median_pct' else '도시근로자 소득'} 기준표가 없어요"
                     if not table else "7인 이상 가구는 기준표가 없어요")
    return Values([monthly / table[int(size)] * 100])


def resolve(person: dict, cond: dict, today: date, year: int) -> Values | Period | Ask | Check:
    field = cond["field"]
    if field not in FIELDS:
        return Check("조건표 어휘 밖 칸이에요")
    try:
        return _resolve(person, cond, field, today, year)
    except (TypeError, ValueError):
        return Check("값을 비교할 수 없어요")


def _resolve(person: dict, cond: dict, field: str, today: date, year: int) -> Values | Period | Ask | Check:
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
    if field == "youngest_child_age" and person.get("children_count") == 0:
        return Values([None])   # 자녀가 없으면 막내 나이 조건은 탈락(자녀 단계에서 열린다)
    if field == "subscription_months" and person.get("has_account") == "N":
        return Values([0])
    if field in SPAN:
        src, unit = SPAN[field]
        if person.get(src) is None:
            return Ask(src)
        start = parse_date(person[src])
        if start is None:
            return Check("날짜를 읽을 수 없어요")
        if start > today:
            return Check("날짜가 오늘보다 뒤예요")
        return Period(start, unit)
    if field == "qual_code":
        quals = person.get("qualifications") or []
        # 물어본 자격만 저장한다. 본인 대상 자격만 본인 조건에 쓴다(배우자 대상은 세지 않는다)
        return Values([[q.get("qual_code") for q in quals if (q or {}).get("target") in (None, "본인")]])
    if field in ("history", "homeless_years"):
        return Check("이력 조건은 아직 판정하지 않아요")
    v = person.get(field)
    return Ask(field) if v is None else Values([v])
