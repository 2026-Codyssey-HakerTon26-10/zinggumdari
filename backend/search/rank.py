"""검색 2단계: BM25가 뽑은 후보를 정해진 순서의 구간으로 다시 줄 세운다.

학습형 순위는 클릭 기록이 있어야 해서 쓰지 않는다. 기준을 순서대로 보고, 앞 기준이 같을 때만 다음을 본다.

1. 관련도 구간: 이름·별칭에 검색어가 통째로 있음 < 검색어 글자 조각 대부분이 이름에 있음 < 본문에만 있음
2. 마감: 접수가 끝난 제도는 맨 아래(상시·미정·날짜 없음은 열린 것으로 본다)
3. 지역: 내 시군구 < 내 시도 < 전국 < 지역 미상 < 다른 지역(프로필에 지역이 없으면 보지 않는다)
4. 배지(로그인했을 때만): 추천 < 비슷한 가구 < 확인 필요 < 조건표 없음 < 해당 안 됨. 해당 안 됨도 숨기지 않고 내리기만 한다
5. BM25 점수

관련도가 맨 앞이라 추천 가능하다는 이유만으로 엉뚱한 제도가 위로 오지 않는다.
이름이 같은 제도(시군구마다 같은 이름으로 낸 사업)는 하나로 묶고, 남긴 것에 묶인 수를 단다.
조건표가 붙은 제도는 따로 판정되므로 묶지 않는다.
"""

from __future__ import annotations

from datetime import date

from backend.data.deadline import is_closed, parse_deadline
from backend.search.corpus import short_sido
from backend.search.index import ABBREV, _squeeze, bigrams

STRONG, MEDIUM, WEAK = 0, 1, 2
MEDIUM_SHARE = 0.7   # 검색어 2-gram 중 이 비율 이상이 이름에 있으면 중간 구간
BADGE_RANK = {"eligible": 0, "similar": 1, "needs_check": 2, "no_rule": 3, "ineligible": 4}


def _targets(q: str) -> set[str]:
    """검색어 통째(공백 뺀 것)와, 줄임말을 푼 꼴. "신혼 특공"은 "신혼특공"과 "신혼특별공급" 둘 다 본다.
    BM25는 expand_query로 줄임말을 넓히는데 관련도 구간만 원래 글자를 봐서, 줄임말 검색이 별칭에 안 걸렸다."""
    target = _squeeze(q)
    out = {target}
    for short, full in ABBREV.items():
        if short in target:
            out.add(target.replace(short, _squeeze(full)))
    return {t for t in out if t}


def relevance_band(doc: dict, q: str) -> int:
    targets = _targets(q)
    if not targets:
        return WEAK
    names = [_squeeze(doc["name"]), *(_squeeze(a) for a in str(doc["fields"].get("aliases") or "").splitlines())]
    if any(t in n for t in targets for n in names if n):
        return STRONG
    grams = [g for g in bigrams(q) if len(g) == 2]
    if grams:
        name_grams = set(bigrams(doc["name"]))
        if sum(g in name_grams for g in grams) / len(grams) >= MEDIUM_SHARE:
            return MEDIUM
    return WEAK


def closed(doc: dict, rule: dict | None, today: date) -> bool:
    """접수가 끝났나. 덤프의 신청기한 서술, 조건표의 apply_date 상한(접수 마감일) 중 하나라도 지났으면."""
    if is_closed(parse_deadline(doc["fields"].get("deadline")), today):
        return True
    for c in (rule or {}).get("conditions") or []:
        if c.get("field") == "apply_date" and c.get("op") in ("<=", "<") and isinstance(c.get("value"), str):
            if c["value"] < today.isoformat() or (c["op"] == "<" and c["value"] == today.isoformat()):
                return True
    return False


def region_rank(doc: dict, sido: str | None, sigungu: str | None) -> int:
    """0 내 시군구, 1 내 시도(시도 전체 제도 포함), 2 전국, 3 지역 미상, 4 다른 지역(같은 시도의 다른 시군구 포함)."""
    if not sido:
        return 0
    region = doc.get("region")
    if region is None:
        return 2
    if not isinstance(region, dict) or region.get("unknown"):
        return 3
    if short_sido(region.get("sido")) != short_sido(sido):
        return 4
    if not region.get("sigungu") or not sigungu:
        return 1
    return 0 if region["sigungu"] == sigungu else 4


from backend.engine.cards import _niche   # noqa: E402 — 추천 카드와 같은 특정 대상 기준


def rerank(hits: list[tuple[dict, float]], q: str, *, rules: dict[str, dict], badges: dict[str, str | None],
           sido: str | None = None, sigungu: str | None = None, today: date | None = None) -> list[tuple[dict, int]]:
    """(문서, 같은 이름으로 묶인 다른 문서 수)를 순위대로. badges는 service_id → 배지(로그인 전이면 None)."""
    today = today or date.today()

    def key(item: tuple[dict, float]):
        doc, score = item
        badge = badges.get(doc["service_id"])
        return (relevance_band(doc, q), closed(doc, rules.get(doc["rule_id"] or ""), today),
                _niche(doc["name"] or "", {}), region_rank(doc, sido, sigungu), BADGE_RANK.get(badge, 3) if badge is not None else 0, -score)

    ordered = sorted(hits, key=key)
    kept: list[list] = []
    seen: dict[str, int] = {}
    for doc, _ in ordered:
        if doc["rule_id"]:   # 조건표가 붙은 제도는 따로 판정되므로 이름이 같아도 묶지 않는다(전국 「청년월세 지원」이 시군구 사업 밑으로 숨지 않게)
            kept.append([doc, 0])
            continue
        name = _squeeze(doc["name"])
        if name and name in seen:
            kept[seen[name]][1] += 1
            continue
        seen[name] = len(kept)
        kept.append([doc, 0])
    # 같은 사업의 공급 유형별 조건표(「국민임대주택공급 일반공급 전용 50㎡ 미만」 등)는 첫 하나만 위에 두고 나머지는 뒤로
    first, rest, families = [], [], set()
    for doc, n in kept:
        family = " ".join((doc["name"] or "").split()[:2]) if doc["rule_id"] else None
        (rest if family and family in families else first).append((doc, n))
        if family:
            families.add(family)
    return first + rest
