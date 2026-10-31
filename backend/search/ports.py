"""검색 배지가 다른 담당 모듈에 붙는 자리.

- 판정: backend.engine에 judge(profile, rules, today=None)가 생기면 자동으로 그것을 쓴다(docs/roles.md).
  today는 검색의 ?today=를 그대로 넘긴다(날짜 재현이 배지까지 맞게).
  돌려주는 값은 판정 결과(docs/api.md §3, {"cards": [...]})나 카드 목록 둘 다 받는다.
  카드에 없는 제도는 ineligible로 본다(§5.2: 확정 탈락은 카드에 올리지 않는다).
  엔진이 없으면 fake_judge(아래)로 돈다. 검색 응답의 "judge"가 engine인지 fake인지 알려준다.
- 로그인 세션: 백엔드1이 connect(session_user=…)로 꽂는다. session_user(request)는 로그인했으면
  {"account_id", "profile_id"}, 아니면 None. 프로필 내용은 connect(load_profile=…)로 profile_id에서 읽는다.
  docs/api.md 「인증·소유권 계약」: 검색은 로그인 없이 되지만 개인화 배지는 로그인한 본인 프로필로만 단다.
  사용자 업로드(/ingest)는 로그인이 필수다. 세션이 아직 연결되지 않았으면 로그인하지 않은 것으로 본다.
- 비슷한 가구: backend.engine.similar.similar_for가 있으면 자동으로 그것을 쓴다. 판정 카드와 함께
  검색 색인의 조건표 전부를 넘겨서, /judge의 비슷한 가구 묶음과 같은 제도에 배지가 붙는다.
  가상 인구 캐시(data/population/)가 없으면 배지를 달지 않는다. connect(similar_rule_ids=…)로 꽂으면
  그것이 우선이다(인자는 profile_id).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable

log = logging.getLogger(__name__)

VERDICTS = ("eligible", "needs_check", "ineligible", "opens_later")
FINAL = ("reviewed", "auto_verified")   # 확정 판정에 쓰는 조건 상태
_COMPUTED = {"marriage_years": "marriage_date", "residence_months": "move_in_date",
             "subscription_months": "joined_date", "support_years": "support_start_date"}


def _span(start: Any, today: date, unit: str) -> int | None:
    try:
        d = date.fromisoformat(str(start)[:10])
    except (TypeError, ValueError):
        return None
    months = (today.year - d.year) * 12 + today.month - d.month - (today.day < d.day)
    return months if unit == "months" else months // 12


def values_of(person: dict, field: str, today: date) -> list | None:
    """조건의 field에 대응하는 값 후보. 출생연도만 있는 나이는 두 값이다(만 나이 경계)."""
    if field == "age":
        by = person.get("birth_year")
        return [today.year - int(by) - 1, today.year - int(by)] if by else None
    if field == "apply_date":
        return [today.isoformat()]
    if field == "marriage_years" and not person.get("marriage_date") and person.get("marital_status") in ("미혼", "예비부부"):
        return [None]   # 혼인신고 전이면 혼인 기간 조건은 탈락
    if field in _COMPUTED:
        v = _span(person.get(_COMPUTED[field]), today, "years" if field.endswith("years") else "months")
        return None if v is None else [v]
    v = person.get(field)
    return None if v is None else [v]


def _cmp(have: Any, op: str, want: Any) -> bool:
    if have is None:
        return False
    try:
        if op == "==":
            return have == want
        if op == "!=":
            return have != want
        if op == "in":
            return have in want
        if op == "not_in":
            return have not in want
        if isinstance(want, str):
            a, b = str(have), want
        else:
            a, b = float(have), float(want)
        return {"<=": a <= b, ">=": a >= b, "<": a < b, ">": a > b}[op]
    except (TypeError, ValueError, KeyError):
        return False


def _one(person: dict, cond: dict, today: date) -> bool | None:
    """True 통과, False 확정 탈락, None 모름(확인 필요나 질문)."""
    field = cond.get("field", "")
    if field == "other" or field.startswith("income") or field in ("qual_code", "history"):
        return None
    cands = values_of(person, field, today)
    if cands is None:
        return None
    results = {_cmp(v, cond.get("op", "=="), cond.get("value")) for v in cands}
    return results.pop() if len(results) == 1 else None


def _cond(person: dict, cond: dict, today: date) -> bool | None:
    if cond.get("status") not in FINAL:
        return None
    if cond.get("any_of"):
        branches = []
        for branch in cond["any_of"]:
            rs = [_one(person, c, today) for c in branch]
            branches.append(False if False in rs else (None if None in rs else True))
        return True if True in branches else (None if None in branches else False)
    return _one(person, cond, today)


def fake_judge(profile: dict, rule: dict, today: date | None = None) -> str:
    """규칙 엔진이 오기 전까지 쓰는 가짜 판정. 소득·other·needs_review는 늘 모름으로 둔다."""
    today = today or date.today()
    if rule.get("subject") == "parent":
        parents = profile.get("parents") or []
        if not parents:
            return "needs_check"
        person = parents[0]
    else:
        person = profile.get("self") or {}
    results = [_cond(person, c, today) for c in rule.get("conditions") or []]
    if False in results:
        return "ineligible"
    if None in results or (rule.get("review") or {}).get("status") != "reviewed":
        return "needs_check"   # 검수 전 AI 조건표로는 eligible이 나오지 않는다
    return "eligible"


def _engine_judge() -> Callable | None:
    try:
        from backend.engine import judge   # type: ignore[attr-defined]
    except ImportError:
        return None
    return judge


def _engine_similar() -> Callable | None:
    try:
        from backend.engine.similar import similar_for
    except ImportError:
        return None
    return similar_for


def _cards(out: Any) -> list[dict]:
    """엔진 결과를 카드 목록으로. 세 모양을 받는다.

    {rule_id: 카드}(#12의 judge), {"cards": [...]}(api.md §3 /judge 응답), 카드 목록.
    """
    if isinstance(out, dict):
        if isinstance(out.get("cards"), list):
            items = out["cards"]
        else:
            items = [{**c, "rule_id": c.get("rule_id") or rid} for rid, c in out.items() if isinstance(c, dict)]
    else:
        items = out or []
    return [c for c in items if isinstance(c, dict) and c.get("rule_id")]


class Ports:
    def __init__(self) -> None:
        self._judge: Callable | None = None
        self.session_user: Callable[[Any], dict | None] = lambda request: None
        self.load_profile: Callable[[str], dict | None] = lambda profile_id: None
        self.similar_rule_ids: Callable[[str], set[str]] | None = None   # connect로 꽂으면 엔진 대신 이것

    @property
    def engine_connected(self) -> bool:
        return self._judge is not None or _engine_judge() is not None

    def verdicts(self, profile: dict, rules: list[dict], today: date | None = None) -> dict[str, str]:
        fn = self._judge or _engine_judge()
        if fn is None:
            return {r["id"]: fake_judge(profile, r, today) for r in rules}
        out = fn(profile, rules, today=today)
        got = {}
        for c in _cards(out):
            if c.get("no_subject"):   # 부모님 탭을 열지 않았다. 탈락이 아니라 모름
                got[c["rule_id"]] = "needs_check"
            else:
                got[c["rule_id"]] = c.get("verdict")
        result = {}
        for r in rules:
            v = got.get(r["id"])
            if v is None:
                v = "needs_check" if r.get("subject") == "parent" and not profile.get("parents") else "ineligible"
            result[r["id"]] = v if v in VERDICTS else "needs_check"
        return result

    def similar(self, profile_id: str, profile: dict, rules: list[dict], today: date | None = None) -> set[str]:
        """비슷한 가구 배지를 달 rule_id. rules는 색인의 조건표 전부(검색 후보만 넘기면 /judge와 고르는 제도가 달라진다)."""
        if self.similar_rule_ids is not None:
            return set(self.similar_rule_ids(profile_id))
        judge, similar_for = self._judge or _engine_judge(), _engine_similar()
        if judge is None or similar_for is None or not profile:
            return set()
        try:
            cards = {c["rule_id"]: c for c in _cards(judge(profile, rules, today=today))}
            out = similar_for(profile, cards, rules, today=today)
        except Exception:   # 비슷한 가구는 덤이라 검색을 막지 않는다. 프로필·검색어는 남기지 않는다
            log.warning("비슷한 가구 계산 실패, 배지 없이 검색", exc_info=True)
            return set()
        return {item["rule_id"] for item in (out or {}).get("items", [])}


ports = Ports()


def connect(*, judge=None, session_user=None, load_profile=None, similar_rule_ids=None) -> None:
    if judge is not None:
        ports._judge = judge
    if session_user is not None:
        ports.session_user = session_user
    if load_profile is not None:
        ports.load_profile = load_profile
    if similar_rule_ids is not None:
        ports.similar_rule_ids = similar_rule_ids


LIFE_STAGES = ("marriage_planned", "newlywed", "child", "multi_child")


def profile_tags(profile: dict, today: date | None = None) -> set[str]:
    """docs/api.md §7의 프로필 태그. derived.tags가 있으면 그것(백엔드1 계산)이 정본."""
    derived = (profile.get("derived") or {}).get("tags")
    if derived is not None:
        return set(derived)
    today = today or date.today()
    me = profile.get("self") or {}
    tags = set()
    ages = values_of(me, "age", today)
    if ages and any(19 <= a <= 39 for a in ages):
        tags.add("youth")
    status, kids = me.get("marital_status"), me.get("children_count") or 0
    if status == "예비부부":
        tags.add("marriage_planned")
    if status in ("신혼", "기혼") and kids == 0:
        tags.add("newlywed")
    if kids == 1:
        tags.add("child")
    if kids >= 2:
        tags.add("multi_child")
    if me.get("is_homeless") == "Y":
        tags.add("homeless")
    if profile.get("parents"):
        tags.add("parent")
    return tags
