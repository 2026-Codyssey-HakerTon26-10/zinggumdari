"""조건 하나, 제도 하나의 판정(SPEC §5.1, §5.2)."""

from datetime import date

from backend.engine.fields import PARENT_CONDITION_FIELDS, SENSITIVE  # 부모님 조건은 부모님이 수집하는 칸만 판정해요.
from backend.engine.values import GROWING, Ask, Check, Period, Values, boundary, months_between, resolve

FINAL = ("reviewed", "auto_verified")   # 확정 판정에 쓰는 조건 상태

# 해둘 일을 하면 풀리는 탈락(요청 33). 시간이 지나 풀리는 탈락처럼 opens_later로 낸다.
#   부모님 장기요양등급이 없음 → 등급 신청, 청약통장이 없음 → 가입
ACTION_FIXABLE = {"ltc_grade": ("없음",), "has_account": ("N",)}

_ISO = len("2026-01-01")


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _iso_date(v) -> bool:
    return isinstance(v, str) and len(v) == _ISO and v[4] == "-" and v[7] == "-"


def compare(have, op: str, want) -> bool | None:
    """True 통과, False 탈락, None 비교할 수 없음(→ 확인 필요). 타입이 다르면 억지로 바꾸지 않는다."""
    if have is None:
        return False
    if op in ("in", "not_in"):
        if not isinstance(want, list):
            return None
        hit = have in want
        return hit if op == "in" else not hit
    if op == "==":
        return have == want
    if op == "!=":
        return have != want
    if op not in ("<=", ">=", "<", ">"):
        return None
    if not ((_number(have) and _number(want)) or (_iso_date(have) and _iso_date(want))):
        return None
    return {"<=": have <= want, ">=": have >= want, "<": have < want, ">": have > want}[op]


def _period(p: Period, op: str, n, today: date) -> bool | None:
    """기간 비교. "7년 이내"(<= 7)는 시작일 + 7년인 날까지 통과한다. 정수로 버리지 않는다."""
    if not _number(n):
        return None
    if op in ("<=", "<", ">=", ">"):
        edge = boundary(p.start, p.unit, n)
        return {"<=": today <= edge, "<": today < edge, ">=": today >= edge, ">": today > edge}[op]
    whole = months_between(p.start, today)
    whole = whole // 12 if p.unit == "years" else whole
    return compare(whole, op, n)


def _quals(known: list, op: str, want) -> bool | None:
    """자격은 물어본 것만 저장한다. 해당함·해당 안 됨을 답한 코드로만 확정하고, 모르면 None(→ 질문)."""
    if not isinstance(want, list):
        return None
    yes = {c for c, has in known if has}
    no = {c for c, has in known if not has}
    hit = bool(yes & set(want))
    all_no = all(c in no for c in want)
    if op == "in":
        return True if hit else False if all_no else None
    if op == "not_in":
        return False if hit else True if all_no else None
    return None


def _other(cond: dict) -> dict:
    reason = cond.get("reason")
    if reason == "unaccounted":
        why = "AI가 조건으로 읽지 못한 원문 줄"
    elif reason == "unread_pages":
        pages = "·".join(str(p) for p in cond.get("pages") or [])
        why = f"{pages}쪽을 읽지 못했어요" if pages else "읽지 못한 쪽이 있어요"
    else:
        why = "시트에 칸이 없는 조건"
    return {"grade": "확인 필요", "ok": None, "why": why}


def _one(person: dict, cond: dict, ctx: dict) -> dict:
    """AND 묶음 안의 조건 한 줄. status는 묶음 단위라 여기서 보지 않는다."""
    field = cond.get("field")
    if field == "other":
        return _other(cond)
    if not field or "op" not in cond:
        return {"grade": "확인 필요", "ok": None, "why": "조건표 형식 오류"}
    if ctx.get("subject") == "parent" and field not in PARENT_CONDITION_FIELDS:  # 본인 전용 칸을 부모님에게 묻거나 본인 값으로 대신 판정하지 않아요.
        why = "소득인정액은 재산 환산이 필요해요" if field == "income_recognized" or cond.get("income_basis") == "recognized" else "부모님에 대해 수집하지 않는 정보라 접수 기관 확인이 필요해요"  # 소득인정액의 재산 환산 안내는 유지해요.
        return {"grade": "확인 필요", "ok": None, "why": why}  # 저장할 수 없는 답변을 요구하지 않고 미확정 상태로 남겨요.
    got = resolve(person, cond, ctx["today"], ctx["year"])
    if isinstance(got, Check):
        return {"grade": "확인 필요", "ok": None, "why": got.why}
    if isinstance(got, Ask):
        if got.field in SENSITIVE and not ctx["sensitive_ok"]:
            return {"grade": "확인 필요", "ok": None, "why": "민감정보 동의가 없어 비어 있는 칸"}
        return {"grade": "질문", "ok": None, "ask": got.field}
    op, want = cond["op"], cond.get("value")
    if isinstance(got, Period):
        results = {_period(got, op, want, ctx["today"])}
    elif field == "qual_code":
        results = {_quals(got.items[0], op, want)}
        if results == {None} and isinstance(want, list):
            return {"grade": "질문", "ok": None, "ask": "qual_code"}
    else:
        results = {compare(v, op, want) for v in got.items}
    if None in results:
        return {"grade": "확인 필요", "ok": None, "why": "값을 비교할 수 없어요"}
    if len(results) > 1:
        return {"grade": "확인 필요", "ok": None, "why": "생일에 따라 달라요"}
    ok = results.pop()
    out = {"grade": "확정", "ok": ok}
    if not ok:
        if field in GROWING and op in (">=", ">"):
            out["fixable"] = True
        elif got.items[0] in ACTION_FIXABLE.get(field, ()) if isinstance(got, Values) else False:
            out["fixable"] = "action"
        else:
            out["fixable"] = False
    return out


def _branch(person: dict, conds: list[dict], ctx: dict) -> dict:
    """AND 묶음. 확정 탈락이 하나라도 있으면 탈락, 전부 확정 통과면 통과, 아니면 첫 미결 줄."""
    rs = [_one(person, c, ctx) for c in conds]
    fails = [r for r in rs if r["ok"] is False]
    if fails:
        return {"grade": "확정", "ok": False, "fixable": _all_fixable(fails)}
    pending = [r for r in rs if r["ok"] is None]
    if pending:
        return next((r for r in pending if r["grade"] == "질문"), pending[0])
    return {"grade": "확정", "ok": True}


def _all_fixable(fails: list[dict]):
    """전부 풀리면 풀리는 방법(해둘 일이 하나라도 있으면 "action", 아니면 True), 하나라도 안 풀리면 False."""
    if not all(r["fixable"] for r in fails):
        return False
    return "action" if any(r["fixable"] == "action" for r in fails) else True


def condition(person: dict, cond: dict, ctx: dict) -> dict:
    """조건 한 줄(또는 any_of 묶음) → {grade, ok, ask?, why?, fixable?}."""
    if cond.get("field") == "other" and not cond.get("any_of"):
        return _other(cond)   # 어휘 밖·미반영·못 읽은 쪽은 상태와 상관없이 그 이유를 보여 준다
    if cond.get("status") not in FINAL:
        return {"grade": "확인 필요", "ok": None, "why": "AI가 읽은 조건 중 검사를 통과하지 못한 것"}
    if not cond.get("any_of"):
        return _one(person, cond, ctx)
    branches = [_branch(person, b, ctx) for b in cond["any_of"]]
    if any(b["ok"] is True for b in branches):
        return {"grade": "확정", "ok": True}
    if all(b["ok"] is False for b in branches):
        # OR은 가지 하나만 열려도 되므로, 풀리는 가지가 하나라도 있으면 나중에 열린다
        ways = [b["fixable"] for b in branches if b["fixable"]]
        return {"grade": "확정", "ok": False, "fixable": (True if True in ways else "action") if ways else False}
    pending = [b for b in branches if b["ok"] is None]
    return next((b for b in pending if b["grade"] == "질문"), pending[0])


def rule_verdict(results: list[dict], rule: dict, ai_eligible: bool) -> tuple[str, str | None]:
    """조건 결과 목록 → (verdict, verdict_why)."""
    fails = [r for r in results if r["ok"] is False]
    if fails:
        return ("opens_later" if _all_fixable(fails) else "ineligible"), None
    if any(r["ok"] is None for r in results):
        return "needs_check", None
    if (rule.get("review") or {}).get("status") == "reviewed":
        return "eligible", None
    clean = all(c.get("field") != "other" for c in rule.get("conditions", []))
    if ai_eligible and clean:
        return "eligible", "ai_unreviewed"   # 열어 줘도 검수 전 AI 조건표라는 사유는 남긴다
    return "needs_check", "ai_unreviewed"


def context(profile: dict, rule: dict, today: date) -> dict:
    updated = str(rule.get("updated") or "")
    year = int(updated[:4]) if updated[:4].isdigit() else today.year
    return {"today": today, "year": year, "subject": rule.get("subject", "self"),  # 같은 이름의 조건도 누구의 정보인지 구분해요.
            "sensitive_ok": bool((profile.get("consents") or {}).get("sensitive"))}
