"""엔진 결과 → /judge 응답(docs/api.md §3). 카드에 올릴 것을 고르고 근거 줄·중복 불가·서류를 채운다.

날짜·해둘 일·타임라인은 플래너(backend/planner)가 채운다. 공고별 질문(ask), 비슷한 가구(similar)는 아직 비어 있다.
"""

import logging
from collections.abc import Callable
from datetime import date

from backend.engine import judge

log = logging.getLogger(__name__)

DISCLAIMER = "참고용 모의 판정, 실제 자격은 접수 기관의 심사로 결정됩니다"
SHOWN = {"eligible": 0, "needs_check": 1, "opens_later": 2}   # ineligible은 카드에 올리지 않는다(SPEC §5.2)


def _no_lines(ids: list[str]) -> list[dict]:
    return [{"id": e, "page": None, "bbox": None, "text": None} for e in ids]


def _documents(rule: dict) -> list[dict]:
    """서류 사전 매핑 전이라 전부 "발급처 확인 필요"(status unknown)다. 발급처를 지어내지 않는다."""
    docs = [{"name": n, "doc_id": None, "who_provides": "applicant", "status": "unknown"}
            for n in rule.get("documents") or []]
    docs += [{"name": n, "doc_id": None, "who_provides": "official", "status": "unknown"}
             for n in rule.get("documents_official") or []]
    return docs


def _explain(card: dict) -> str:
    grades = [c["grade"] for c in card["conditions"]]
    passed = sum(1 for c in card["conditions"] if c["ok"] is True)
    return (f"조건 {len(grades)}개 중 맞는 것 {passed}개, 확인 필요 {grades.count('확인 필요')}개, "
            f"질문 {grades.count('질문')}개")


def build_judge(profile: dict, rules: list[dict], today: date | None = None,
                evidence: Callable[[list[str]], list[dict]] = _no_lines, step: str | None = None) -> dict:
    """step: 단계 넘기기. 그 단계까지 가정한 프로필로 판정한다(SPEC §7.1)."""
    from backend import planner   # planner가 engine.judge를 쓰므로 여기서 가져온다

    today = today or date.today()
    if step:
        profile = planner.apply_step(profile, step, today)
    results = judge(profile, rules, today)
    plan = planner.timeline(profile, rules, today, results)
    by_id = {r["id"]: r for r in rules}
    cards = []
    next_step = {i for s in plan["self"] for i in s["opens"]}
    for rule in rules:
        card = results[rule["id"]]
        if card["verdict"] == "ineligible" and rule["id"] in next_step:
            # 다음 단계(혼인신고·출산)로 가면 열리는 제도는 카드로 올리고 언제 열리는지 단다
            card.update(verdict="opens_later", verdict_why="next_step")
        if card["verdict"] not in SHOWN or card.get("no_subject") or card.get("superseded_by"):
            continue
        planner.annotate(card, rule, profile, today, plan["self"])
        for row in card["conditions"]:
            row["evidence"] = evidence([e["id"] for e in row["evidence"]])
            missing = [e["id"] for e in row["evidence"] if e.get("text") is None]
            if missing:   # 원문이 등록되지 않은 근거 줄(SPEC §8). 줄 ID만 남긴다
                log.warning("근거 줄 원문 없음: %s", ", ".join(missing))
        card["exclusive_with"] = [
            {"rule_id": x["rule_id"], "name": (by_id.get(x["rule_id"]) or {}).get("name"),
             "both_eligible": card["verdict"] == "eligible"
             and (results.get(x["rule_id"]) or {}).get("verdict") == "eligible"}
            for x in card["exclusive_with"]]
        card["exclusive_evidence"] = evidence(card["exclusive_evidence"]) if card["exclusive_evidence"] else []
        card.update(documents=_documents(rule), explain=_explain(card))
        cards.append(card)
    cards.sort(key=lambda c: (c["subject"] != "self", SHOWN[c["verdict"]]))
    return {
        "user_id": profile.get("user_id"),
        "ask": None,
        "cards": cards,
        "step": step,
        "timeline": plan,
        "similar": None,
        "disclaimer": DISCLAIMER,
    }
