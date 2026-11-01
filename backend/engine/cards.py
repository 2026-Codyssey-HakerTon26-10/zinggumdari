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


# 추천 순서: 이번 단계에 맞는 제도 → 확정에 가까운 것 → 내 지역 제도. 같은 분야(예: 전세대출)가 위를 다 차지하지 않게 섞는다.
BUCKETS = (("주거", ("전세", "주택", "임대", "청약", "대출", "디딤돌", "버팀목", "월세", "보증금", "행복주택", "희망타운")),
           ("출산·육아", ("임신", "출산", "신생아", "아동", "양육", "보육", "육아", "아이", "자녀", "다자녀")),
           ("일자리", ("취업", "구직", "일자리", "고용", "창업", "직업", "훈련", "인턴")),
           ("건강", ("건강", "의료", "진료", "검진", "예방접종", "마음", "치과", "요양", "돌봄")),
           ("자산", ("적금", "저축", "계좌", "자산", "통장", "연금")),
           ("생활·문화", ("문화", "교통", "요금", "감면", "할인", "바우처", "이용권", "여행")))
SPREAD = 4   # 같은 분야 카드가 이미 나온 만큼 이 칸 수만큼 뒤로 민다


NICHE = ("한부모", "장애", "북한이탈", "다문화", "저소득", "국가유공자", "보훈", "군무원", "청소년", "영재", "수급", "차상위",
         "기초생활", "노숙", "미혼모", "탈북", "결혼이민", "농업인", "어업인", "제대군인", "의료급여", "에너지바우처", "농지", "납북", "피해자")


def _niche(name: str, me: dict) -> bool:
    """특정 대상(한부모·장애인 등) 제도. 프로필에 그 표시가 없으면 '모름'일 뿐이라 위로 올리지 않는다."""
    mine = " ".join(str(q.get("qual_code", "")) for q in me.get("qualifications") or []) + \
        (" 장애" if me.get("disability_registered") == "Y" else "") + \
        (" 수급 차상위 저소득 기초생활" if me.get("livelihood_status") not in (None, "해당없음") else "")
    if any(w in name and w not in mine for w in NICHE):
        return True
    return ("아동" in name or "어린이" in name) and not me.get("children_count")


def _bucket(name: str) -> str:
    return next((b for b, words in BUCKETS if any(w in name for w in words)), "기타")


def _rank(cards: list[dict], by_id: dict, me: dict, step: str | None, focus_tags: set, stage_tags) -> list[dict]:
    def key(c):
        rule = by_id.get(c["rule_id"]) or {}
        tags = set(stage_tags(rule))
        stage = 0 if step and step in tags else (1 if tags & focus_tags else 2)
        if rule.get("source") == "upload":
            stage = -1   # 내가 올린 공고는 방금 고른 것이라 맨 위(공고 투입 뒤 카드 합류가 바로 보이게)
        if _niche(c.get("name") or "", me):
            stage = 3
        region = rule.get("region") or {}
        local = 0 if region.get("sigungu") and region.get("sigungu") == me.get("sigungu") else \
            1 if region.get("sido") and region.get("sido") == me.get("sido") else 2
        unknown = sum(1 for x in c["conditions"] if x["ok"] is None) / max(len(c["conditions"]), 1)
        return (stage, SHOWN[c["verdict"]], local, c["ai_extracted"], round(unknown, 1))

    ordered, dupes, names = [], [], set()
    for c in sorted(cards, key=key):   # 이름이 같은 조건표(지자체별 중복 등)는 앞의 것 하나만 위에 두고 나머지는 맨 뒤로
        (dupes if c.get("name") in names else ordered).append(c)
        names.add(c.get("name"))
    out, seen = [], {}
    while ordered:
        i = min(range(len(ordered)), key=lambda j: j + SPREAD * seen.get(_bucket(ordered[j].get("name") or ""), 0))
        card = ordered.pop(i)
        b = _bucket(card.get("name") or "")
        seen[b] = seen.get(b, 0) + 1
        out.append(card)
    return out + dupes


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
    me = profile.get("self", {})
    cards = (_rank([c for c in cards if c["subject"] == "self"], by_id, me, step, focus_tags, planner.stage_tags)
             + _rank([c for c in cards if c["subject"] != "self"], by_id, me, step, focus_tags, planner.stage_tags))
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
