"""규칙 엔진. 다른 모듈(검색 배지, 가상 인구 전수 판정)은 `judge()`만 쓴다.

같은 프로필과 같은 조건표면 결과가 항상 같다. LLM을 부르지 않는다.
"""

import os
from datetime import date

from backend.engine.evaluate import condition, context, rule_verdict
from backend.engine.read_as import read_as

RANK = {"eligible": 0, "opens_later": 1, "needs_check": 2, "ineligible": 3}


def _ai_eligible() -> bool:
    return os.environ.get("AI_ELIGIBLE", "").lower() in ("1", "true", "yes", "on")


def _card(rule: dict, subject_profile: dict, profile: dict, today: date, ai_eligible: bool) -> dict:
    ctx = context(profile, rule, today)
    conds = rule.get("conditions") or []
    results = [condition(subject_profile, c, ctx) for c in conds]
    verdict, why = rule_verdict(results, rule, ai_eligible)
    rows = []
    for c, r in zip(conds, results):
        row = {"read_as": read_as(c), "grade": r["grade"], "ok": r["ok"], "status": c.get("status"),
               "evidence": [{"id": e, "page": None, "bbox": None, "text": None} for e in c.get("evidence") or []]}
        for key in ("ask", "why"):
            if key in r:
                row[key] = r[key]
        if "checks" in c:
            row["checks"] = c["checks"]
        rows.append(row)
    review = (rule.get("review") or {}).get("status", "unreviewed")
    return {
        "rule_id": rule["id"], "subject": rule.get("subject", "self"), "name": rule.get("name"),
        "domain": rule.get("domain"), "verdict": verdict, "verdict_why": why,
        "ai_extracted": review != "reviewed", "conditions": rows,
        "exclusive_with": [{"rule_id": rid} for rid in rule.get("exclusive_with") or []],
        "exclusive_evidence": rule.get("exclusive_evidence") or [],
        "detail_url": rule.get("detail_url"), "updated": rule.get("updated"), "review": review,
    }


def judge(profile: dict, rules: list[dict], today: date | None = None,
          ai_eligible: bool | None = None) -> dict[str, dict]:
    """프로필 하나를 조건표 전부로 판정한다. 반환: {rule_id: 카드}. 모든 제도가 들어간다(ineligible 포함).

    profile: docs/api.md §2 모양({"self": {...}, "parents": [...], "consents": {...}}). "self"가 없으면 profile 자체를 나로 본다.
    rules: docs/api.md §1 조건 JSON 목록. today: None이면 오늘(?today=로 바꾼다).
    ai_eligible: None이면 환경변수 AI_ELIGIBLE(기본 끔). 꺼져 있으면 검수 전 AI 조건표는 eligible이 되지 않는다.

    카드에 추가로 붙는 키(화면용 /judge가 거른다):
      "no_subject": True  부모님 조건표인데 부모님 정보가 없다(부모님 탭을 안 열었다)
      "superseded_by"     같은 제도의 손 조건표가 있어 판정·검색·알림에 쓰지 않는다(SPEC §9.4)
    """
    today = today or date.today()
    ai_eligible = _ai_eligible() if ai_eligible is None else ai_eligible
    me = profile.get("self", profile)
    parents = profile.get("parents") or []
    superseded = {sid: r["id"] for r in rules if r.get("source") == "manual" for sid in r.get("same_as") or []}

    out = {}
    for rule in rules:
        if rule.get("subject") == "parent":
            cards = [_card(rule, p, profile, today, ai_eligible) for p in parents]
            if cards:
                card = min(cards, key=lambda c: RANK[c["verdict"]])
            else:
                card = _card(rule, {}, profile, today, ai_eligible)
                card.update(verdict="needs_check", no_subject=True)
        else:
            card = _card(rule, me, profile, today, ai_eligible)
        if rule["id"] in superseded:
            card["superseded_by"] = superseded[rule["id"]]
        out[rule["id"]] = card
    return out
