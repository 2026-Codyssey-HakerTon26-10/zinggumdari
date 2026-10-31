"""조건에서 계산되는 날짜(SPEC §7.3). 시간에 따라 커지는 칸의 조건에서만 나온다.

- 닫히는 날: 지금 통과 중인 <=·< 조건
- 열리는 날: 지금 탈락 중인 >=·> 조건
상태가 reviewed·auto_verified인 조건만 쓴다. 재료 날짜가 없으면 날짜를 만들지 않는다.
"""

from backend.engine.evaluate import FINAL
from backend.engine.values import (
    SPAN,
    add_months,
    birth_date_of,
    birth_year_of,
    birthday_at,
    boundary,
    parse_date,
)


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
        # 생년월일이 있으면 그 나이가 되는 날(when)까지, 출생연도만 있는 옛 데이터는 해(year)만
        try:
            born = birth_date_of(person)
        except ValueError:
            return None
        by = born.year if born else birth_year_of(person)
        if by is None or v is None:
            return None
        src = "birth_date" if born else "birth_year"
        if closing:
            limit = v if cond["op"] == "<=" else v - 1
            out = {"field": f, "from": src, "max_age": limit, "year": by + limit + 1}
            age = limit + 1   # 만 limit+1세 생일부터 해당 안 됨
        else:
            need = v if cond["op"] == ">=" else v + 1
            out = {"field": f, "from": src, "min_age": need, "year": by + need}
            age = need
        if born:
            out["when"] = birthday_at(born, age).isoformat()
        return out
    if f in SPAN:
        # 날짜 기간은 정수 보정 없이 경계일 = 시작일 + N(엔진과 같은 boundary). <=는 그날까지 통과, <는 그날 닫힌다
        src, unit = SPAN[f]
        start = parse_date(person.get(src))
        if start is None or not isinstance(v, (int, float)) or isinstance(v, bool):
            return None
        return {"field": f, "from": src, f"plus_{unit}": v, "when": boundary(start, unit, v).isoformat()}
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
    """손 조건표의 apply_window(SPEC §7.2). 지금은 만 65세 기준(age65)만 안다.
    생년월일이 있으면 신청을 시작하는 달까지, 출생연도만 있는 옛 데이터는 해만 말한다."""
    window = rule.get("apply_window") or {}
    if window.get("anchor") != "age65":
        return None
    offset = window.get("offset_months") or 0
    try:
        born = birth_date_of(person)
    except ValueError:
        born = None
    if born is not None:
        start = add_months(birthday_at(born, 65).replace(day=1), offset)   # 생일이 속한 달 기준
        return f"{start.year}년 {start.month}월부터"
    by = birth_year_of(person)
    if by is None:
        return None
    when = f"{-offset}개월 전부터" if offset < 0 else f"{offset}개월 뒤부터" if offset > 0 else "부터"
    return f"{by + 65}년 생일이 속한 달의 {when}(생일 달은 출생연도만 있어 확인 필요)"
