"""검색 한 번(docs/api.md §7). 라우터는 backend/app/routers/search.py."""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import date

from backend.search.corpus import build_corpus, short_sido
from backend.search.index import SearchIndex, snippet
from backend.search.rank import rerank
from backend.search.ports import LIFE_STAGES, ports, profile_tags

CANDIDATES = 100   # 2단계로 넘길 BM25 후보 수
BADGE = {"eligible": "eligible", "needs_check": "needs_check", "opens_later": "needs_check", "ineligible": "ineligible"}

_MARRIAGE = {
    "question": "혹시 결혼 준비 중이거나 신혼이세요? 정보를 바꾸면 맞는 제도를 다시 찾아드릴게요",
    "options": [{"label": "결혼 준비 중", "set": {"marital_status": "예비부부"}},
                {"label": "신혼(혼인신고 함)", "set": {"marital_status": "신혼"}},
                {"label": "아니요", "set": None}],
    "why": "결혼 준비·신혼 단계 제도",
}
NUDGE = {
    "marriage_planned": _MARRIAGE,
    "newlywed": _MARRIAGE,
    "child": {
        "question": "혹시 출산을 앞두고 있거나 자녀가 있으세요? 정보를 바꾸면 맞는 제도를 다시 찾아드릴게요",
        "options": [{"label": "임신 중", "set": {"pregnant": "Y"}}, {"label": "자녀 있음", "set": {"children_count": 1}},
                    {"label": "아니요", "set": None}],
        "why": "임신·출산·자녀 단계 제도",
    },
    "multi_child": {
        "question": "혹시 자녀가 둘 이상이세요? 정보를 바꾸면 맞는 제도를 다시 찾아드릴게요",
        "options": [{"label": "둘 이상", "set": {"children_count": 2}}, {"label": "아니요", "set": None}],
        "why": "다자녀 단계 제도",
    },
}

_index: SearchIndex | None = None


def get_index() -> SearchIndex:
    global _index
    if _index is None:
        docs, rules = build_corpus()
        _index = SearchIndex(docs, rules)
    return _index


def reset_index() -> None:
    """조건표가 늘면 부른다(공고 투입이 부른다)."""
    global _index
    _index = None


def nudge_for(top: list[dict], profile: dict, today: date) -> dict | None:
    """상위 5개 중 2개 이상이 내 프로필에 없는 생애 단계 태그면 묻는다. 프로필은 바꾸지 않는다.
    한 세션에 한 번만 띄우는 것은 화면이 맡는다."""
    mine = profile_tags(profile, today)
    counts = Counter(t for d in top[:5] for t in set(d["stage_tags"]) if t in LIFE_STAGES and t not in mine)
    if not counts:
        return None
    tag, n = counts.most_common(1)[0]
    if n < 2:
        return None
    spec = NUDGE[tag]
    return {"missing_tag": tag, "question": spec["question"], "options": spec["options"],
            "why": f"상위 5개 중 {n}개가 {spec['why']}"}


def search(q: str, profile_id: str | None = None, tag: str | None = None, subject: str | None = None,
           region: str | None = None, limit: int = 20, today: date | None = None) -> dict:
    """profile_id는 로그인 세션에서 정한 본인 프로필이다. None이면 개인화 배지를 달지 않는다(badge None)."""
    today = today or date.today()
    index = get_index()
    profile = (ports.load_profile(profile_id) if profile_id else None) or {}
    similar = ports.similar_rule_ids(profile_id) if profile_id else set()
    # 1단계: BM25로 후보를 넉넉히 뽑는다. 2단계: 관련도·마감·지역·배지 구간으로 다시 줄 세우고 같은 이름을 묶는다
    candidates = index.search(q, limit=CANDIDATES, tag=tag, subject=subject,
                              sido=short_sido(region) if region else None)
    docs = [d for d, _ in candidates]
    rules = [index.rules[d["rule_id"]] for d in docs if d["rule_id"] in index.rules]
    verdicts = ports.verdicts(profile, rules, today) if rules and profile_id else {}

    def badge(doc: dict) -> str | None:
        if not doc["rule_id"] or doc["rule_id"] not in index.rules:
            return "no_rule"
        if not profile_id:
            return None
        v = verdicts[doc["rule_id"]]
        return "similar" if v == "needs_check" and doc["rule_id"] in similar else BADGE.get(v, "needs_check")

    badges = {d["service_id"]: badge(d) for d in docs}
    me = profile.get("self") or {}
    ranked = rerank(candidates, q, rules=index.rules, badges=badges if profile_id else {},
                    sido=me.get("sido"), sigungu=me.get("sigungu"), today=today)[:limit]
    hits = [d for d, _ in ranked]
    results = [{
        "service_id": d["service_id"], "rule_id": d["rule_id"], "name": d["name"], "org": d["org"],
        "region": d["region"], "subject": d["subject"], "snippet": snippet(d, q), "stage_tags": d["stage_tags"],
        "badge": badges[d["service_id"]], "detail_url": d["detail_url"], "updated": d["updated"],
        "same_name": n,
    } for d, n in ranked]
    return {"q": q, "results": results, "nudge": nudge_for(hits, profile, today) if profile_id and profile else None,
            "judge": "engine" if ports.engine_connected else "fake"}


_SEARCH_PATH = re.compile(r"/search/?\?", re.IGNORECASE)   # /search/?q=… 는 307로 /search?q=… 가 되는데 둘 다 로그에 찍힌다


class _HideSearchQuery(logging.Filter):
    """검색어를 서버 로그에 남기지 않는다(uvicorn 접근 로그의 /search 쿼리를 지운다)."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str) and _SEARCH_PATH.match(args[2]):
            record.args = (*args[:2], "/search?…", *args[3:])
        return True


logging.getLogger("uvicorn.access").addFilter(_HideSearchQuery())
