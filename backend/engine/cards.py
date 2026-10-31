"""엔진 결과 → /judge 응답(docs/api.md §3). 카드에 올릴 것을 고르고 근거 줄·중복 불가·서류를 채운다.

날짜·해둘 일·타임라인은 플래너(backend/planner)가, 공고별 질문(ask)은 engine/ask.py가 채운다.
비슷한 가구(similar)는 넘겨받은 함수(라우터가 engine.similar.similar_for를 꽂는다)로 채우고, 없거나 실패하면 null이다.
검수 전 AI 조건표는 프로필이나 다음 단계의 단계 태그와 맞는 것만 카드로 올리고 나머지는 folded에 센다(SPEC §0).
"""

import logging
from collections.abc import Callable
from datetime import date

from backend.engine import documents, judge
from backend.engine.ask import choose_ask
from backend.engine.derive import tags as profile_tags

log = logging.getLogger(__name__)

DISCLAIMER = "참고용 모의 판정, 실제 자격은 접수 기관의 심사로 결정됩니다"
SHOWN = {"eligible": 0, "needs_check": 1, "opens_later": 2}   # ineligible은 카드에 올리지 않는다(SPEC §5.2)


def _no_lines(ids: list[str]) -> list[dict]:
    return [{"id": e, "page": None, "bbox": None, "text": None} for e in ids]


def _foldable(rule: dict) -> bool:
    """검수 전 AI 조건표. 내가 올린 조건표는 직접 고른 것이라 접지 않는다."""
    return (rule.get("review") or {}).get("status") != "reviewed" and rule.get("source") != "upload"


def _focus_tags(profile: dict, today: date) -> set[str]:
    """지금 프로필의 단계 태그와 바로 다음 단계. 제도 태그(planner.stage_tags)와 같은 이름을 쓴다."""
    from backend.planner.steps import upcoming   # planner가 engine을 불러오므로 여기서 가져온다(순환 import)

    me = profile.get("self", {})
    out = set(profile_tags(me, today)) | set(upcoming(me)[:1])
    if profile.get("parents"):
        out.add("parent")
    return out


def _explain(card: dict) -> str:
    grades = [c["grade"] for c in card["conditions"]]
    passed = sum(1 for c in card["conditions"] if c["ok"] is True)
    return (f"조건 {len(grades)}개 중 맞는 것 {passed}개, 확인 필요 {grades.count('확인 필요')}개, "
            f"질문 {grades.count('질문')}개")


def build_judge(profile: dict, rules: list[dict], today: date | None = None,
                evidence: Callable[[list[str]], list[dict]] = _no_lines, step: str | None = None,
                focus: str | None = None, similar: Callable[[dict, dict], dict | None] | None = None) -> dict:
    """step: 단계 넘기기. 그 단계까지 가정한 프로필로 판정한다(SPEC §7.1).
    focus: 사용자가 연 카드의 rule_id. 있으면 그 제도를 막는 칸을 묻는다(SPEC §6).
    similar: (프로필, judge 결과) → api.md §3 similar. 맞춤 추천과 섞지 않는다(SPEC §13)."""
    from backend import planner   # planner가 engine.judge를 쓰므로 여기서 가져온다

    today = today or date.today()
    if step:
        profile = planner.apply_step(profile, step, today)
    results = judge(profile, rules, today)
    plan = planner.timeline(profile, rules, today, results)
    by_id = {r["id"]: r for r in rules}
    doc_map, doc_dict = documents.load_map(), documents.load_dictionary()   # 서류 사전 캐시. 런타임에 새로 맞추지 않는다
    cards, folded = [], []
    next_step = {i for s in plan["self"] for i in s["opens"]}
    focus_tags = _focus_tags(profile, today)
    opens_next = set(plan["self"][0]["opens"]) if plan["self"] else set()
    for rule in rules:
        card = results[rule["id"]]
        if card["verdict"] == "ineligible" and rule["id"] in next_step:
            # 다음 단계(혼인신고·출산)로 가면 열리는 제도는 카드로 올리고 언제 열리는지 단다
            card.update(verdict="opens_later", verdict_why="next_step")
        if card["verdict"] not in SHOWN or card.get("no_subject") or card.get("superseded_by"):
            continue
        if _foldable(rule) and rule["id"] not in opens_next and not focus_tags & set(planner.stage_tags(rule)):
            folded.append({"rule_id": rule["id"], "name": rule.get("name"), "subject": card["subject"],
                           "verdict": card["verdict"]})
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
        card.update(documents=documents.rows(rule, doc_map, doc_dict), explain=_explain(card))
        cards.append(card)
    near = None
    if similar is not None:
        try:
            near = similar(profile, results)
        except Exception:   # 가상 인구 캐시가 깨져도 카드는 내보낸다
            log.exception("비슷한 가구 계산 실패")
    cards.sort(key=lambda c: (c["subject"] != "self", c["ai_extracted"], SHOWN[c["verdict"]]))
    return {
        "user_id": profile.get("user_id"),
        "ask": choose_ask(cards, by_id, profile, focus),
        "cards": cards,
        "step": step,
        "timeline": plan,
        "similar": near,
        "folded": {"count": len(folded), "items": folded},
        "disclaimer": DISCLAIMER,
    }
