"""조건 하나, 제도 하나의 판정(SPEC §5.1, §5.2)."""

from datetime import date

from backend.engine.values import GROWING, SENSITIVE, Ask, Check, Values, resolve

FINAL = ("reviewed", "auto_verified")   # 확정 판정에 쓰는 조건 상태
PASS, FAIL = "pass", "fail"


def compare(have, op: str, want) -> bool:
    if have is None:
        return False
    if isinstance(have, list):   # qual_code: 내 자격 코드 목록
        hit = any(h in want for h in have)
        return hit if op == "in" else not hit if op == "not_in" else False
    if op == "==":
        return have == want
    if op == "!=":
        return have != want
    if op == "in":
        return have in want
    if op == "not_in":
        return have not in want
    try:
        a, b = (str(have), str(want)) if isinstance(want, str) else (float(have), float(want))
    except (TypeError, ValueError):
        return False
    return {"<=": a <= b, ">=": a >= b, "<": a < b, ">": a > b}[op]


def _one(person: dict, cond: dict, ctx: dict) -> dict:
    """AND 묶음 안의 조건 한 줄. status는 묶음 단위라 여기서 보지 않는다."""
    field = cond.get("field")
    if field == "other":
        why = "AI가 조건으로 읽지 못한 원문 줄" if cond.get("reason") == "unaccounted" else "시트에 칸이 없는 조건"
        return {"grade": "확인 필요", "ok": None, "why": why}
    got = resolve(person, cond, ctx["today"], ctx["year"])
    if isinstance(got, Check):
        return {"grade": "확인 필요", "ok": None, "why": got.why}
    if isinstance(got, Ask):
        if got.field in SENSITIVE and not ctx["sensitive_ok"]:
            return {"grade": "확인 필요", "ok": None, "why": "민감정보 동의가 없어 비어 있는 칸"}
        return {"grade": "질문", "ok": None, "ask": got.field}
    results = {compare(v, cond["op"], cond.get("value")) for v in got.items}
    if len(results) > 1:
        return {"grade": "확인 필요", "ok": None, "why": "생일에 따라 달라요"}
    ok = results.pop()
    out = {"grade": "확정", "ok": ok}
    if not ok:
        out["fixable"] = field in GROWING and cond["op"] in (">=", ">")
    return out


def _branch(person: dict, conds: list[dict], ctx: dict) -> dict:
    """AND 묶음. 확정 탈락이 하나라도 있으면 탈락, 전부 확정 통과면 통과, 아니면 첫 미결 줄."""
    rs = [_one(person, c, ctx) for c in conds]
    fails = [r for r in rs if r["ok"] is False]
    if fails:
        return {"grade": "확정", "ok": False, "fixable": all(r["fixable"] for r in fails)}
    pending = [r for r in rs if r["ok"] is None]
    if pending:
        return next((r for r in pending if r["grade"] == "질문"), pending[0])
    return {"grade": "확정", "ok": True}


def condition(person: dict, cond: dict, ctx: dict) -> dict:
    """조건 한 줄(또는 any_of 묶음) → {grade, ok, ask?, why?, fixable?}."""
    if cond.get("status") not in FINAL:
        return {"grade": "확인 필요", "ok": None, "why": "AI가 읽은 조건 중 검사를 통과하지 못한 것"}
    if not cond.get("any_of"):
        return _one(person, cond, ctx)
    branches = [_branch(person, b, ctx) for b in cond["any_of"]]
    if any(b["ok"] is True for b in branches):
        return {"grade": "확정", "ok": True}
    if all(b["ok"] is False for b in branches):
        return {"grade": "확정", "ok": False, "fixable": all(b["fixable"] for b in branches)}
    pending = [b for b in branches if b["ok"] is None]
    return next((b for b in pending if b["grade"] == "질문"), pending[0])


def rule_verdict(results: list[dict], rule: dict, ai_eligible: bool) -> tuple[str, str | None]:
    """조건 결과 목록 → (verdict, verdict_why)."""
    fails = [r for r in results if r["ok"] is False]
    if fails:
        return ("opens_later" if all(r["fixable"] for r in fails) else "ineligible"), None
    if any(r["ok"] is None for r in results):
        return "needs_check", None
    if (rule.get("review") or {}).get("status") == "reviewed":
        return "eligible", None
    clean = all(c.get("field") != "other" for c in rule.get("conditions", []))
    if ai_eligible and clean:
        return "eligible", None
    return "needs_check", "ai_unreviewed"


def context(profile: dict, rule: dict, today: date) -> dict:
    updated = str(rule.get("updated") or "")
    year = int(updated[:4]) if updated[:4].isdigit() else today.year
    return {"today": today, "year": year,
            "sensitive_ok": bool((profile.get("consents") or {}).get("sensitive"))}
