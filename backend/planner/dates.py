"""조건에서 계산되는 날짜(SPEC §7.3). 시간에 따라 커지는 칸의 조건에서만 나온다.

- 닫히는 날: 지금 통과 중인 <=·< 조건
- 열리는 날: 지금 탈락 중인 >=·> 조건
상태가 reviewed·auto_verified인 조건만 쓴다. 재료 날짜가 없으면 날짜를 만들지 않는다.
"""

from datetime import date

from backend.engine.evaluate import FINAL

# 기간 칸 → (재료 날짜 칸, 단위)
SPAN = {"marriage_years": ("marriage_date", "years"), "residence_months": ("move_in_date", "months"),
        "subscription_months": ("joined_date", "months"), "support_years": ("support_start_date", "years")}


def add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    year, month = d.year + y, m + 1
    days = [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(year, month, min(d.day, days[month - 1]))


def _parse(v) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def flat(rule: dict) -> list[tuple[dict, dict]]:
    """(조건 한 줄, 그 줄이 속한 묶음). any_of 가지 안의 조건도 꺼낸다. 상태는 묶음에 있다."""
    out = []
    for c in rule.get("conditions") or []:
        if c.get("any_of"):
            out += [(x, c) for branch in c["any_of"] for x in branch]
        else:
            out.append((c, c))
    return out


def _final(group: dict) -> bool:
    return group.get("status") in FINAL


def _when(person: dict, cond: dict, closing: bool) -> dict | None:
    f, v = cond["field"], cond.get("value")
    if f == "apply_date":
        return {"field": f, "when": str(v)}
    if f == "age":
        by = person.get("birth_year")
        if by is None or v is None:
            return None
        if closing:
            limit = v if cond["op"] == "<=" else v - 1
            return {"field": f, "from": "birth_year", "max_age": limit, "year": int(by) + limit + 1}
        need = v if cond["op"] == ">=" else v + 1
        return {"field": f, "from": "birth_year", "min_age": need, "year": int(by) + need}
    if f in SPAN:
        src, unit = SPAN[f]
        start = _parse(person.get(src))
        if start is None or v is None:
            return None
        n = v if cond["op"] in ("<=", ">=") else v + (1 if cond["op"] == ">" else -1)
        when = add_months(start, n * 12 if unit == "years" else n).isoformat()
        return {"field": f, "from": src, f"plus_{unit}": n, "when": when}
    return None


def _key(d: dict) -> str:
    return d.get("when") or f"{d['year']}-01-01"


def closes_at(rule: dict, person: dict, rows: list[dict]) -> dict | None:
    """지금 통과 중인 <=·< 조건이 닫히는 가장 이른 날."""
    found = []
    for cond, row in zip(rule.get("conditions") or [], rows):
        if cond.get("any_of") or not _final(cond) or row["ok"] is not True or cond["op"] not in ("<=", "<"):
            continue
        w = _when(person, cond, closing=True)
        if w:
            found.append(w)
    return min(found, key=_key) if found else None


def opens_at(rule: dict, person: dict, rows: list[dict]) -> dict | None:
    """지금 탈락 중인 >=·> 조건이 모두 풀리는 날(가장 늦은 것)."""
    found = []
    for cond, row in zip(rule.get("conditions") or [], rows):
        if cond.get("any_of") or not _final(cond) or row["ok"] is not False or cond["op"] not in (">=", ">"):
            continue
        w = _when(person, cond, closing=False)
        if w is None:
            return None
        found.append(w)
    return max(found, key=_key) if found else None


def deadline(rule: dict) -> str | None:
    ds = [str(c["value"]) for c in rule.get("conditions") or []
          if not c.get("any_of") and _final(c) and c.get("field") == "apply_date" and c.get("op") in ("<=", "<")]
    return min(ds) if ds else None


def apply_from(rule: dict, person: dict) -> str | None:
    """손 조건표의 apply_window(SPEC §7.2). 지금은 만 65세 기준(age65)만 안다. 출생월은 받지 않는다."""
    window = rule.get("apply_window") or {}
    by = person.get("birth_year")
    if window.get("anchor") != "age65" or by is None:
        return None
    year = int(by) + 65
    offset = window.get("offset_months") or 0
    when = f"{-offset}개월 전부터" if offset < 0 else f"{offset}개월 뒤부터" if offset > 0 else "부터"
    return f"{year}년 생일이 속한 달의 {when}(생일 달은 출생연도만 있어 확인 필요)"
