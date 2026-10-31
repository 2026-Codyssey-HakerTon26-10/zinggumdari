"""단계 플래너(SPEC §7). 열리고 닫히는 제도, 해둘 일, 날짜, 부모님 줄, 단계 태그를 전부 조건표에서 계산한다.

LLM이 쓴 값은 없다. 근거 줄이 없는 해둘 일은 만들지 않고, 날짜가 계산되지 않으면 날짜를 만들지 않는다.
"""

from datetime import date

from backend.engine import judge
from backend.planner import dates
from backend.planner.steps import STEPS, apply_step, assume, upcoming
from backend.planner.todo import ltc_todos, todos

__all__ = ["STEPS", "apply_step", "stage_tags", "annotate", "timeline"]

AVAILABLE = ("eligible", "needs_check")   # 카드에 "지금 받을 수 있는 쪽"으로 올라가는 판정
RELATION = {"모": "어머니", "부": "아버지"}


def stage_tags(rule: dict) -> list[str]:
    """제도의 단계 태그(api.md §1). any_of 가지 안의 조건도 본다."""
    tags = set()
    if rule.get("subject") == "parent":
        tags.add("parent")
    for c, _ in dates.flat(rule):
        f, op, v = c.get("field"), c.get("op"), c.get("value")
        vs = v if isinstance(v, list) else [v]
        if f == "age" and op in ("<=", "<") and isinstance(v, (int, float)) and v <= 39 and rule.get("subject") != "parent":
            tags.add("youth")
        if f == "marital_status" and "예비부부" in vs:
            tags.add("marriage_planned")
        if f == "marriage_years" or (f == "marital_status" and "신혼" in vs):
            tags.add("newlywed")
        if f in ("youngest_child_age", "pregnant", "due_month") or (f == "children_count" and v == 1):
            tags.add("child")
        if f == "children_count" and isinstance(v, (int, float)) and v >= 2:
            tags.add("multi_child")
    order = ["youth", "marriage_planned", "newlywed", "child", "multi_child", "parent"]
    return [t for t in order if t in tags]


def _available(card: dict | None) -> bool:
    return bool(card) and card["verdict"] in AVAILABLE and not card.get("no_subject") and not card.get("superseded_by")


def _self_steps(profile: dict, rules: list[dict], today: date, now: dict) -> list[dict]:
    out, prev, cur = [], now, profile
    for step in upcoming(cur.get("self", {})):
        change = assume(cur["self"], step, today)
        cur = apply_step(cur, step, today)
        nxt = judge(cur, rules, today)
        self_ids = [r["id"] for r in rules if r.get("subject", "self") == "self"]
        opens = [i for i in self_ids if _available(nxt[i]) and not _available(prev[i])]
        closes = [i for i in self_ids if _available(prev[i]) and not _available(nxt[i])]
        by_id = {r["id"]: r for r in rules}
        todo = [t for i in opens for t in todos(by_id[i], nxt[i]["conditions"], cur["self"], today)]
        out.append({"step": step, "assume": change, "opens": opens, "closes": closes, "todo": todo})
        prev = nxt
    return out


def _has(rule: dict, field: str, ops: tuple[str, ...] | None = None) -> bool:
    return any(c.get("field") == field and (ops is None or c.get("op") in ops) and g.get("status") in dates.FINAL
               for c, g in dates.flat(rule))


def _parent_steps(profile: dict, rules: list[dict], today: date, now: dict) -> list[dict]:
    out = []
    parent_rules = [r for r in rules if r.get("subject") == "parent"]
    for p in profile.get("parents") or []:
        if p.get("care_wanted") == "Y" and p.get("ltc_grade") in (None, "없음"):
            ltc = [r for r in parent_rules if _has(r, "ltc_grade") and not _available(now.get(r["id"]))]
            out.append({"step": "ltc_apply", "now": True, "relation": p.get("relation"),
                        "why": "돌봄 희망 + 장기요양등급 없음", "opens": [r["id"] for r in ltc],
                        "todo": [t for r in ltc for t in ltc_todos(r)]})
        by = p.get("birth_year")
        if by is not None and today.year - int(by) < 65:
            later = [r for r in parent_rules if _has(r, "age", (">=", ">")) and now[r["id"]]["verdict"] == "opens_later"]
            if later:
                step = {"step": "age65", "relation": p.get("relation"), "year": int(by) + 65,
                        "opens": [r["id"] for r in later]}
                step["apply_from"] = next((a for r in later if (a := dates.apply_from(r, p))), None)
                out.append(step)
    return out


def _dated(profile: dict, rules: list[dict], today: date, now: dict) -> list[dict]:
    me, out = profile.get("self", {}), []
    by = me.get("birth_year")
    for r in rules:
        if r.get("subject", "self") != "self" or not _available(now[r["id"]]) or by is None:
            continue
        for c, g in dates.flat(r):
            if c.get("field") == "age" and c.get("op") in ("<=", "<") and g.get("status") in dates.FINAL \
                    and isinstance(c.get("value"), (int, float)) and c["value"] <= 39:
                limit = c["value"] if c["op"] == "<=" else c["value"] - 1
                # 카드 closes_at과 같은 해: 만 limit+1세가 되는 해(그해 생일부터 해당 안 됨)
                out.append({"what": f"청년 나이 상한(만 {limit}세) 지남", "year": int(by) + limit + 1, "from": "birth_year",
                            "note": f"만 {limit + 1}세 생일부터 해당 안 됨"})
        if (d := dates.deadline(r)) and d >= today.isoformat():
            out.append({"what": f"{r.get('name')} 접수 마감", "date": d, "from": "apply_date"})
        closing = dates.closes_at(r, me, now[r["id"]]["conditions"])
        if closing and closing["field"] == "marriage_years":
            out.append({"what": f"{r.get('name')} 신혼 기간 끝", "date": closing["when"], "from": "marriage_date"})
    if me.get("pregnant") == "Y" and me.get("due_month"):
        out.append({"what": "출산 예정월", "date": str(me["due_month"]), "from": "due_month"})
    for p in profile.get("parents") or []:
        pb = p.get("birth_year")
        if pb is not None and today.year - int(pb) < 65 and any(
                _has(r, "age", (">=", ">")) for r in rules if r.get("subject") == "parent"):
            who = RELATION.get(p.get("relation"), "부모님")
            out.append({"what": f"{who} 만 65세", "year": int(pb) + 65, "from": "parents.birth_year"})
    uniq = {tuple(sorted(d.items())): d for d in out}
    return sorted(uniq.values(), key=lambda d: d.get("date") or f"{d['year']}-01-01")


def timeline(profile: dict, rules: list[dict], today: date, now: dict) -> dict:
    """now: 지금 프로필의 judge() 결과."""
    return {"self": _self_steps(profile, rules, today, now),
            "parent": _parent_steps(profile, rules, today, now),
            "dated": _dated(profile, rules, today, now)}


def annotate(card: dict, rule: dict, profile: dict, today: date, steps: list[dict]) -> None:
    """카드에 날짜·해둘 일·태그를 붙인다. steps는 timeline()["self"]."""
    person = profile.get("self", {})
    if rule.get("subject") == "parent":
        parents = profile.get("parents") or []
        person = parents[0] if parents else {}
    rows = card["conditions"]
    opening = next((s["step"] for s in steps if rule["id"] in s["opens"]), None)
    if card["verdict"] == "opens_later":
        card["opens_at"] = dates.opens_at(rule, person, rows)
    elif card["verdict"] != "eligible" and opening:
        card["opens_at"] = {"step": opening}
    else:
        card["opens_at"] = None
    card["closes_at"] = dates.closes_at(rule, person, rows)
    card["deadline"] = dates.deadline(rule)
    card["apply_from"] = dates.apply_from(rule, person)
    card["prerequisites"] = [] if rule.get("subject") == "parent" else todos(rule, rows, person, today)
    card["stage_tags"] = stage_tags(rule)
