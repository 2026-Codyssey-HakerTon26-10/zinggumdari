"""검증기(SPEC §9.3). 조건마다 검사를 돌려 checks와 status를 단다. LLM은 부르지 않는다.

검사 값은 "ok", "na"(해당 없음), "fail:사유"다. 수·날짜 조건은 근거 줄의 수를 normalize로 읽어
값·단위(소득 기준 포함)·비교어(제외 문맥 포함)·같은 절 신호어(소득 주체, 다른 필드의 말)·경계 쌍을 본다.
범주 조건(세대주, 무주택, 혼인 상태, 시도 …)은 값이 어휘 안에 있고 근거에 그 말이 있는지(값), ==·in이 제외 문장에서
온 것이 아닌지(비교어)를 본다. 사람이 확인한 조건(reviewed)은 바꾸지 않고 로그에만 남긴다.
"""

from __future__ import annotations

import copy
import re

from backend.compiler import vocab
from backend.compiler.section import is_heading
from backend.compiler.normalize import (Quantity, clause_at, comparator_later, convert, find_quantities, lead_in,
                                        negated)

CHECKS = ["schema", "evidence", "value", "comparator", "unit", "keyword", "pair", "layer"]

_INEQ = ("<", "<=", ">", ">=")
_DATE_RE = re.compile(r"\d{4}-\d{2}(?:-\d{2})?")
_WS = re.compile(r"\s+")
_JOIN = re.compile(r"\s*(?:또는|및|과|와|이나|나|,|·|ㆍ)?\s*")


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_date(v) -> bool:
    return isinstance(v, str) and bool(_DATE_RE.fullmatch(v))


def _numeric(c: dict) -> bool:
    """값·비교어·단위·경계 쌍 검사를 받는 조건(수, 또는 비교하는 날짜)."""
    v = c.get("value")
    return _is_num(v) or (_is_date(v) and c.get("op") in (*_INEQ, "=="))


def _needs_basis(field) -> bool:
    return isinstance(field, str) and field.startswith("income_") and not field.startswith("income_band_")


def _eq(a, b, kind: str | None = None) -> bool:
    if _is_num(a) and _is_num(b):
        return abs(a - b) <= (0.01 if kind == "money" else 1e-9)
    return isinstance(a, str) and a == b


def _fmt(v) -> str:
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)


def _flat(rule: dict):
    """조건표의 모든 단순 조건(any_of 가지 안까지)."""
    for c in rule.get("conditions", []):
        branches = c.get("any_of")
        if not isinstance(branches, list):
            yield c
            continue
        for b in branches:
            if isinstance(b, list):
                yield from (x for x in b if isinstance(x, dict))


# --- 스키마·근거 ---

def _schema(c: dict) -> str:
    f, op, v, basis = c.get("field"), c.get("op"), c.get("value"), c.get("income_basis")
    if f not in vocab.FIELDS:
        return f"fail:unknown_field:{f}"
    if f == "other":
        return "ok" if isinstance(c.get("text"), str) and c["text"].strip() else "fail:other_without_text"
    if op not in vocab.OPS:
        return f"fail:unknown_op:{op}"
    if c.get("as_of") not in (None, *vocab.AS_OF):
        return f"fail:unknown_as_of:{c['as_of']}"
    if basis not in (None, *vocab.INCOME_BASIS):
        return f"fail:unknown_income_basis:{basis}"
    if basis is None and _needs_basis(f):
        return "fail:missing_income_basis"
    if op in ("in", "not_in"):
        if not isinstance(v, list) or not v:
            return "fail:value_not_list"
    elif op in _INEQ:
        if not (_is_num(v) or _is_date(v)):
            return "fail:value_not_number"
    elif v is None or isinstance(v, (list, dict)):
        return "fail:value_not_scalar"
    allowed = vocab.FIELD_VALUES.get(f)
    if allowed and op not in _INEQ:
        bad = [x for x in (v if isinstance(v, list) else [v]) if not (isinstance(x, str) and x in allowed)]
        if bad:
            return f"fail:value_not_in_vocab:{bad[0]}"  # True는 "Y"가 아니다
    return "ok"


def _any_of_shape(c: dict) -> str:
    """any_of는 비지 않은 가지(단순 조건의 목록)의 목록이고 한 단계만이다."""
    branches = c["any_of"]
    if not isinstance(branches, list) or not branches:
        return "fail:empty_any_of"
    for b in branches:
        if not isinstance(b, list) or not b:
            return "fail:empty_branch"
        if not all(isinstance(x, dict) for x in b):
            return "fail:bad_branch"
        if any("any_of" in x for x in b):
            return "fail:nested_any_of"
    return "ok"


def _evidence(ids, lines_by_id: dict) -> tuple[str, list[dict]]:
    """근거 검사 결과와 찾은 근거 줄. 줄은 맨 줄 ID나 "{doc_id}:{줄 ID}" 키로 찾는다."""
    if not isinstance(ids, list) or not ids:
        return "fail:no_evidence", []
    found, bad = {}, None
    for eid in ids:
        if not isinstance(eid, str) or ":" not in eid:
            bad = bad or f"fail:bad_id:{eid}"
            continue
        line = lines_by_id.get(eid.rsplit(":", 1)[1]) or lines_by_id.get(eid)
        if line is None:
            bad = bad or f"fail:unknown_line:{eid}"
        else:
            found[line["id"]] = line
    return bad or "ok", list(found.values())


# --- 수·날짜 ---

def _compatible(q: Quantity, c: dict) -> bool:
    """수의 단위가 필드에 맞나. 소득 필드는 %↔%기준, 금액↔금액기준이어야 한다."""
    f = c.get("field")
    if q.kind not in vocab.FIELD_UNITS.get(f, []):
        return False
    if _needs_basis(f):
        return c.get("income_basis") in (vocab.PERCENT_BASIS if q.kind == "percent" else vocab.MONEY_BASIS)
    return True


def _value_of(q: Quantity, c: dict):
    """맞는 단위면 조건 value 단위로 바꾼 값, 아니면 원래 값."""
    if not _compatible(q, c):
        return q.value
    target = vocab.VALUE_UNIT.get(c["field"], q.kind)
    if target == "age" and q.kind == "months":
        target = "years"  # 아이 나이 "생후 24개월" → 2세
    return convert(q, target)


def _comparator(op, q: Quantity, text: str) -> str:
    """수 뒤 비교어가 op와 맞나. 제외 문장 안의 수는 실패, ==는 뒤에 비교어가 더 없을 때만 통과."""
    if not q.inverted and negated(text, q.start, q.end):
        return "fail:negated_context"  # "…이하인 자 중 수급자는 제외": 어느 쪽을 뺐는지 모른다
    if q.comparator is None:
        if op != "==":
            return "fail:no_comparator"
        return "fail:op_mismatch" if comparator_later(text, q.end) else "ok"
    return "ok" if q.comparator == op else "fail:op_mismatch"


def _basis(c: dict, line: dict, q: Quantity) -> str:
    """소득 기준이 원문과 맞나. 수의 절, 없으면 줄에서 기준을 정하는 말을 찾고, 다른 기준의 말만 있으면 실패."""
    basis = c.get("income_basis")
    if not _needs_basis(c.get("field")) or basis not in vocab.BASIS_WORDS:
        return "ok"
    group = vocab.PERCENT_BASIS if q.kind == "percent" else vocab.MONEY_BASIS
    for text in (clause_at(line["text"], q.start), line["text"]):
        seen = {b for b in group if re.search(vocab.BASIS_WORDS[b], text)}
        if seen:
            return "ok" if basis in seen else "fail:basis_mismatch"
    return "ok"  # 원문이 기준을 말하지 않는다


def _owners(text: str) -> set[str]:
    """글의 마지막 소득 주체 말 묶음. "본인 또는 배우자"처럼 및·또는으로 이은 말은 함께 센다."""
    taken: list[tuple[int, int, str]] = []
    for owner, rx in vocab.INCOME_OWNER:  # 앞의 것이 먼저("본인과 배우자"는 부부)
        taken += [(m.start(), m.end(), owner) for m in re.finditer(rx, text)
                  if not any(s < m.end() and m.start() < e for s, e, _ in taken)]
    taken.sort()
    out: set[str] = set()
    for i in range(len(taken) - 1, -1, -1):
        out.add(taken[i][2])
        if i == 0 or not _JOIN.fullmatch(text, taken[i - 1][1], taken[i][0]):
            break
    return out


def _income_owner(c: dict, text: str, q: Quantity) -> str:
    """소득 필드가 원문의 소득 주체(본인·배우자·가구·부부)와 맞나. 수 앞의 말, 없으면 수의 절에서 찾는다."""
    f = c["field"]
    for part in (lead_in(text, q.start), clause_at(text, q.start)):
        owners = _owners(part)
        if owners:
            return "ok" if f in owners else f"fail:income_owner:{'|'.join(sorted(owners))}"
    # 주체를 말하지 않는 소득("연소득 5천만원 이하", "월평균소득 120% 이하")은 본인·가구 어느 쪽으로도 읽힌다.
    # 부부·배우자 소득은 그 말이 있어야 한다
    return "ok" if f in ("income_self", "income_household") else "fail:income_owner_unknown"


def _keyword_in_clause(c: dict, line: dict, q: Quantity) -> str:
    f = c.get("field")
    kws, nots = vocab.FIELD_KEYWORDS.get(f, []), vocab.FIELD_NOT_KEYWORDS.get(f, [])
    if not kws and not nots:
        return "na"
    clause = clause_at(line["text"], q.start)
    other = next((k for k in nots if k in clause), None)
    if other:
        return f"fail:other_field_word:{other}"  # "만 6세 이하 자녀"의 6은 본인 나이가 아니다
    if kws and not any(k in clause for k in kws) and not (f == "age" and q.kind == "age"):
        # 목록·표 줄은 신호어를 바로 위 제목에만 쓴다("3. 신청기간" 아래 "○ 2026. 11. 3. ~ 11. 27.")
        if not any(k in (line.get("heading") or "") for k in kws):
            return "fail:keyword_not_in_clause"
    if f in ("income_self", "income_spouse", "income_household", "income_couple"):
        return _income_owner(c, line["text"], q)
    return "ok"


def _keyword_anywhere(c: dict, ev_lines: list[dict]) -> str:
    kws = vocab.FIELD_KEYWORDS.get(c.get("field"), [])
    if not kws:
        return "na"
    return "ok" if any(k in l["text"] for l in ev_lines for k in kws) else "fail:keyword_not_in_evidence"


def _pair(c: dict, rule: dict, q: Quantity, line_qs: list[Quantity]) -> str:
    """범위의 한 끝이면 다른 끝도 같은 필드의 조건으로 있어야 한다."""
    if q.range_id is None:
        return "ok"
    for o in line_qs:
        if o.range_id != q.range_id or o.start == q.start:
            continue
        v = _value_of(o, c)
        if not any(x is not c and x.get("field") == c.get("field") and _eq(x.get("value"), v, o.kind)
                   for x in _flat(rule)):
            return f"fail:missing_bound:{o.raw if v is None else _fmt(v)}"
    return "ok"


def _n_fails(checks: dict) -> int:
    return sum(v.startswith("fail") for v in checks.values())


def _numeric_checks(c: dict, rule: dict, ev_lines: list[dict]) -> tuple[dict, set[str]]:
    """(검사, 그 수가 있던 줄 ID)."""
    found = [(l, q, qs) for l in ev_lines for qs in [find_quantities(l["text"])] for q in qs]
    v = c["value"]
    compat = [x for x in found if _compatible(x[1], c) and _eq(_value_of(x[1], c), v, x[1].kind)]
    other = [x for x in found if not _compatible(x[1], c) and _eq(x[1].value, v, x[1].kind)]
    if not compat and not other:
        return {"value": "fail:not_in_evidence", "comparator": "fail:no_value", "unit": "fail:no_value",
                "keyword": _keyword_anywhere(c, ev_lines), "pair": "na"}, set()
    # 같은 수가 여럿이면 검사를 가장 많이 통과하는 자리를 쓴다(맞는 단위가 먼저)
    best, lid = min((({"comparator": _comparator(c.get("op"), q, l["text"]),
                       "unit": _basis(c, l, q) if compat else "fail:unit_mismatch",
                       "keyword": _keyword_in_clause(c, l, q), "pair": _pair(c, rule, q, qs)}, l["id"])
                     for l, q, qs in compat or other), key=lambda x: _n_fails(x[0]))
    return {"value": "ok", **best}, {lid}


def _value_words(f: str, x: str) -> list[str]:
    """범주 값 x가 근거에 있다고 볼 말. Y는 필드 신호어, 표에 없는 N은 찾을 말이 없다."""
    if (f, x) in vocab.VALUE_WORDS:
        return vocab.VALUE_WORDS[(f, x)]
    if x == "Y":
        return vocab.FIELD_KEYWORDS.get(f) or []
    if x == "N":
        return []
    if f == "sido":
        return [x, vocab.SIDO.get(x)] + [k for k, v in vocab.SIDO.items() if v == x]
    if f == "sigungu" and len(x) > 2 and x[-1] in "시군구":
        return [x, x[:-1]]  # 마포구 ↔ 마포
    return [x]


def _categorical_checks(c: dict, ev_lines: list[dict]) -> tuple[dict, set[str]]:
    """범주 조건: 값마다 근거에 그 말(띄어쓰기 무시)이 있어야 한다(value). ==·in은 제외 문장이 아닌 자리가,
    !=·not_in은 "제외·아닌·않" 문장 자리가 있어야 한다(comparator)."""
    f, op, v = c["field"], c.get("op"), c.get("value")
    out = {"keyword": _keyword_anywhere(c, ev_lines)}
    items = v if isinstance(v, list) else [v]
    if f in ("qual_code", "history"):  # 코드표(시트)와 원문의 대응을 검사할 수 없다. 항상 사람이 본다
        return {**out, "value": "fail:unverifiable"}, set()
    if op in _INEQ or not all(isinstance(x, str) for x in items):
        return {**out, "value": "na"}, {l["id"] for l in ev_lines}
    neg = op in ("!=", "not_in")
    used: set[str] = set()
    for x in items:
        hits = [(l, m) for l in ev_lines for w in _value_words(f, x) if w
                for m in re.finditer(r"\s*".join(map(re.escape, _WS.sub("", w))), l["text"])]
        if not hits:
            return {**out, "value": f"fail:not_in_evidence:{x}", "comparator": "na"}, set()
        good = [l["id"] for l, m in hits if negated(l["text"], m.start(), m.end(), broad=neg) == neg]
        if not good:
            return {**out, "value": "ok", "comparator": "fail:not_negated" if neg else "fail:negated_context"}, set()
        used.update(good)
    return {**out, "value": "ok", "comparator": "ok"}, used


def _plain_checks(c: dict, rule: dict, ev_lines: list[dict]) -> tuple[dict, set[str]]:
    """단순 조건 하나의 schema·value·comparator·unit·keyword·pair와, 검사가 실제로 쓴 근거 줄 ID."""
    out = {"schema": _schema(c), "value": "na", "comparator": "na", "unit": "na", "keyword": "na", "pair": "na"}
    if c.get("field") == "other" or c.get("field") not in vocab.FIELDS:
        return out, {l["id"] for l in ev_lines}  # 어휘 밖 필드는 단위·신호어가 없어 스키마에서만 떨어뜨린다
    checks, used = _numeric_checks(c, rule, ev_lines) if _numeric(c) else _categorical_checks(c, ev_lines)
    out.update(checks)
    return out, used


def _merge(key: str, per: list[list[dict]]) -> str:
    """가지별 검사를 묶음 하나로: 하나라도 떨어지면 fail:b가지.조건:사유, 아니면 ok가 있으면 ok."""
    vals = []
    for i, branch in enumerate(per):
        for j, checks in enumerate(branch):
            if checks[key].startswith("fail:"):
                return f"fail:b{i}.{j}:{checks[key][5:]}"
            vals.append(checks[key])
    return "ok" if "ok" in vals else "na"


def _check(cond: dict, rule: dict, lines_by_id: dict) -> tuple[dict, set[str]]:
    """(검사 결과, 검사가 실제로 쓴 근거 줄 ID)."""
    ev, ev_lines = _evidence(cond.get("evidence"), lines_by_id)
    layer = "fail:ocr" if any(l.get("src") == "ocr" for l in ev_lines) else "ok"
    if "any_of" in cond:
        shape = _any_of_shape(cond)
        if shape != "ok":
            return {**{k: "na" for k in CHECKS}, "schema": shape, "evidence": ev, "layer": layer}, set()
        per = [[_plain_checks(c, rule, ev_lines) for c in branch] for branch in cond["any_of"]]
        checks = {k: _merge(k, [[x[0] for x in b] for b in per]) for k in CHECKS if k not in ("evidence", "layer")}
        used = set().union(*(x[1] for b in per for x in b))
    else:
        checks, used = _plain_checks(cond, rule, ev_lines)
        if cond.get("field") == "other":
            layer = "na"
    checks.update(evidence=ev, layer=layer)
    return {k: checks[k] for k in CHECKS}, used


def check_condition(cond: dict, rule: dict, lines_by_id: dict) -> dict:
    """맨 위 조건 하나(또는 any_of 묶음)의 검사 결과. any_of 가지는 묶음의 근거로 검사한다."""
    return _check(cond, rule, lines_by_id)[0]


def used_lines(cond: dict, rule: dict, lines_by_id: dict) -> set[str]:
    """빠짐 검사가 "쓰인 줄"로 셀 근거 줄 ID. auto_verified 조건과 값 검사에서 떨어진 조건은 검사가 실제로 맞춘 줄만
    센다(소득 줄을 무주택 조건이나 원문에 없는 자격 코드의 근거로 대어 그 줄의 조건이 빠진 것을 숨기지 못하게).
    나머지는 근거 줄 전부(사람이 본다)."""
    ids = {e.rsplit(":", 1)[-1] for e in cond.get("evidence") or [] if isinstance(e, str)}
    if cond.get("status") == "reviewed":
        return ids
    checks, used = _check(cond, rule, lines_by_id)
    if cond.get("status") == "auto_verified" or checks["value"].startswith("fail:"):
        return used
    return ids


def _has_other(cond: dict) -> bool:
    if isinstance(cond.get("any_of"), list):
        return any(isinstance(b, list) and any(isinstance(x, dict) and x.get("field") == "other" for x in b)
                   for b in cond["any_of"])
    return cond.get("field") == "other"


def _filter_documents(rule: dict, lines: list[dict]) -> None:
    """AI 조건표의 서류명은 원문 줄에 그대로(띄어쓰기 무시) 있는 것만 남긴다."""
    docs = rule.get("documents")
    if rule.get("source") == "manual" or not isinstance(docs, list):
        return
    texts = [_WS.sub("", l.get("text") or "") for l in lines]
    keep, dropped = [], []
    for name in docs:
        key = _WS.sub("", name) if isinstance(name, str) else ""
        (keep if key and any(key in t for t in texts) else dropped).append(name)
    rule["documents"] = keep
    if dropped:
        rule.setdefault("documents_dropped", []).extend(dropped)


def index_lines(lines: list[dict]) -> dict:
    """줄 ID → 줄. 제목이 아닌 줄은 바로 위 제목 줄의 글을 `heading`에 붙인 사본이다(신호어 검사용)."""
    out, head = {}, None
    for l in lines:
        if is_heading(l.get("text") or ""):
            head = l["text"]
            out[l["id"]] = l
        else:
            out[l["id"]] = {**l, "heading": head} if head else l
    return out


def verify(rule: dict, lines: list[dict], *, log: list | None = None) -> dict:
    """조건표의 사본에 검사 결과(checks)와 상태(status)를 달아 돌려준다.

    reviewed 조건은 그대로 두고, 떨어진 검사가 있는 조건은 log에 {"rule_id", "index", "checks"}로 남긴다.
    """
    out = copy.deepcopy(rule)
    lines_by_id = index_lines(lines)
    for i, c in enumerate(out.get("conditions", [])):
        checks = check_condition(c, out, lines_by_id)
        failed = _n_fails(checks) > 0
        if failed and log is not None:
            log.append({"rule_id": out.get("id"), "index": i, "checks": checks})
        if c.get("status") == "reviewed":
            continue
        c["checks"] = checks
        c["status"] = "needs_review" if failed or _has_other(c) else "auto_verified"
    _filter_documents(out, lines)
    return out
