"""해둘 일(카드 prerequisites, 타임라인 todo). 아래 칸에 걸린 조건에서만 나온다(api.md §1). 근거 줄은 조건의 것."""

from backend.engine.read_as import read_as
from backend.engine.values import months_between
from backend.planner.dates import flat

ACTION = {
    "has_account": "subscription_account", "subscription_months": "subscription_account",
    "payment_count": "subscription_account", "deposit_amount": "subscription_account",
    "sido": "move_in", "sigungu": "move_in", "residence_months": "move_in",
    "marital_status": "marriage_registration", "marriage_years": "marriage_registration",
    "ltc_grade": "ltc_grade_apply",
}
STATUS = {True: "met", False: "unmet", None: "unknown"}


def todos(rule: dict, rows: list[dict], person: dict, today) -> list[dict]:
    """나의 해둘 일. rows는 이 조건표를 판정한 카드의 조건 줄(조건과 같은 순서)."""
    groups = rule.get("conditions") or []
    ok_of = {id(g): r["ok"] for g, r in zip(groups, rows)}
    out = []
    for cond, group in flat(rule):
        action = ACTION.get(cond.get("field"))
        if not action or action == "ltc_grade_apply" or not cond.get("evidence", group.get("evidence")):
            continue
        if cond["field"] in ("sido", "sigungu") and person.get(cond["field"]) and cond.get("op") in ("==", "in"):
            want = cond["value"] if isinstance(cond["value"], list) else [cond["value"]]
            if person[cond["field"]] not in want:
                continue   # 다른 지역 주민용 조건(가지)이다. 이사하라는 해둘 일로 내지 않는다
        item = {"action": action, "read_as": read_as(cond), "status": STATUS[ok_of.get(id(group))],
                "evidence": group.get("evidence") or []}
        if cond.get("as_of"):
            item["as_of"] = cond["as_of"]
        if cond["field"] == "subscription_months" and cond["op"] in (">=", ">"):
            item["min_months"] = cond["value"]
            have = 0 if person.get("has_account") == "N" else months_between(person.get("joined_date"), today)
            item["have_months"] = have
        out.append(item)
    return dedupe(out)


def ltc_todos(rule: dict) -> list[dict]:
    return dedupe([{"action": "ltc_grade_apply", "evidence": group.get("evidence") or []}
                   for cond, group in flat(rule) if cond.get("field") == "ltc_grade" and group.get("evidence")])


def dedupe(items: list[dict]) -> list[dict]:
    seen, out = set(), []
    for it in items:
        key = (it["action"], it.get("read_as"), tuple(it["evidence"]))
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out
