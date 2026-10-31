"""공고별 확인 질문(SPEC §6). 판정을 막고 있는 빈 칸 중 한 칸만 묻는다. LLM을 쓰지 않는다.

- 카드를 열었을 때(focus): 그 제도를 막고 있는 칸을 묻는다.
- 전체: 확인 필요 후보 제도들을 가장 많이 가르는 칸 하나. 후보가 5개 이하면 묻지 않는다.
- 이미 값이 있는 칸은 엔진이 막는 칸으로 내지 않으므로 다시 묻지 않는다.
- 민감정보는 동의가 없으면 묻지 않는다(엔진도 그 칸을 확인 필요로 둔다).
"""

from backend.engine.fields import PARENT_PROFILE_FIELDS, is_sensitive_qual  # 저장 가능한 부모님 칸과 민감 자격 여부를 함께 확인해요.

MIN_CANDIDATES = 6   # 남은 후보가 5개 이하면 묻지 않는다

# 막는 칸을 묻는 순서가 같을 때 앞에 오는 칸(가입 → 알림 설정 → 공고별 확인 순)
ORDER = ["birth_date", "marital_status", "marriage_date", "children_count", "youngest_child_age", "household_size",
         "employment_status", "pregnant", "due_month", "sido", "sigungu", "tenure_type", "is_householder",
         "is_homeless", "move_in_date", "deposit", "monthly_rent", "house_price", "employment_type", "income_self",
         "income_spouse", "income_household", "dependents_count", "supports_parent_65", "support_start_date",
         "has_account", "joined_date", "payment_count", "deposit_amount", "qual_code",
         "relation", "lives_alone", "lives_with_child", "ltc_grade", "disability_registered", "basic_pension",
         "livelihood_status", "care_wanted"]

YES_NO = [{"label": "예", "value": "Y"}, {"label": "아니오", "value": "N"}]
DATE = [{"label": "날짜 입력", "value": "date"}]
MONTH = [{"label": "월 입력", "value": "month"}]
NUMBER = [{"label": "숫자 입력", "value": "number"}]
MONEY = [{"label": "금액 입력(만 원)", "value": "number", "unit": "만원"}]
TEXT = [{"label": "입력", "value": "text"}]


def _choices(*values: str) -> list[dict]:
    return [{"label": v, "value": v} for v in values]


# 칸 → (질문, 선택지). 선택지는 값으로 바로 매핑한다(SPEC §6). 값은 api.md §2 프로필 값 그대로
QUESTIONS = {
    "birth_date": ("생년월일이 언제인가요?", DATE),
    "marital_status": ("지금 혼인 상태가 어떻게 되나요?", _choices("미혼", "예비부부", "신혼", "기혼", "이혼·사별")),
    "marriage_date": ("혼인신고를 하셨나요? 했다면 언제인가요?",
                      [{"label": "안 함", "value": None, "set": {"marital_status": "예비부부"}}, *DATE]),
    "children_count": ("자녀가 몇 명인가요?", NUMBER),
    "youngest_child_age": ("막내 자녀는 몇 살인가요?", NUMBER),
    "household_size": ("함께 사는 가구원은 본인 포함 몇 명인가요?", NUMBER),
    "employment_status": ("지금 하시는 일이 무엇인가요?", _choices("재학", "구직", "재직", "자영업", "육아휴직", "기타")),
    "pregnant": ("지금 임신 중이신가요?", YES_NO),
    "due_month": ("출산 예정월이 언제인가요?", MONTH),
    "sido": ("사는 곳(시·도)이 어디인가요?", TEXT),
    "sigungu": ("사는 곳(시·군·구)이 어디인가요?", TEXT),
    "tenure_type": ("지금 집은 어떤 형태인가요?", _choices("자가", "전세", "월세", "보증부월세", "무상거주")),
    "is_householder": ("세대주이신가요?", _choices("세대주", "세대원")),
    "is_homeless": ("세대원 모두 집이 없나요(무주택)?", YES_NO),
    "move_in_date": ("지금 주소로 전입신고한 날이 언제인가요?", DATE),
    "deposit": ("보증금이 얼마인가요?", MONEY),
    "monthly_rent": ("월세가 얼마인가요?", MONEY),
    "house_price": ("집 가격이 얼마인가요?", MONEY),
    "employment_type": ("맞벌이인가요?", _choices("맞벌이", "외벌이", "해당없음")),
    "income_self": ("본인 월 소득이 얼마인가요?", MONEY),
    "income_spouse": ("배우자(예정 포함) 월 소득이 얼마인가요?", MONEY),
    "income_household": ("가구 전체 월 소득이 얼마인가요?", MONEY),
    "dependents_count": ("부양가족이 몇 명인가요?", NUMBER),
    "supports_parent_65": ("만 65세 이상 부모님을 부양하고 계신가요?", YES_NO),
    "support_start_date": ("부모님 부양을 시작한 날이 언제인가요?", DATE),
    "has_account": ("청약통장이 있나요?", YES_NO),
    "joined_date": ("청약통장에 가입한 날이 언제인가요?", DATE),
    "payment_count": ("청약통장 납입 횟수가 몇 회인가요?", NUMBER),
    "deposit_amount": ("청약통장 예치금이 얼마인가요?", MONEY),
    # 부모님
    "relation": ("어느 분인가요?", _choices("부", "모")),
    "lives_alone": ("부모님이 혼자 사시나요?", YES_NO),
    "lives_with_child": ("부모님이 자녀와 함께 사시나요?", YES_NO),
    "ltc_grade": ("부모님 장기요양등급이 있나요?", _choices("없음", "1등급", "2등급", "3등급", "4등급", "5등급", "인지지원등급")),
    "disability_registered": ("부모님이 장애 등록이 되어 있나요?", YES_NO),
    "basic_pension": ("부모님이 기초연금을 받고 계신가요?", YES_NO),
    "livelihood_status": ("부모님이 기초생활수급이나 차상위에 해당하나요?",
                          _choices("생계", "의료", "주거", "교육", "차상위", "해당없음")),
    "care_wanted": ("부모님께 돌봄 서비스가 필요하신가요?", YES_NO),
}
PARENT_BIRTH_DATE = ("부모님 생년월일이 언제인가요?", DATE)


def _qual_to_ask(rule: dict, me: dict, sensitive_ok: bool) -> str | None:
    """이 조건표의 자격 코드 중 아직 답하지 않은 첫 코드. 민감 자격은 동의가 있을 때만."""
    known = {q.get("qual_code") for q in me.get("qualifications") or [] if (q or {}).get("target") in (None, "본인")}
    for c in rule.get("conditions") or []:
        branches = c["any_of"] if c.get("any_of") else [[c]]
        for cond in (x for b in branches for x in b):
            if cond.get("field") != "qual_code" or not isinstance(cond.get("value"), list):
                continue
            for code in cond["value"]:
                if code not in known and (sensitive_ok or not is_sensitive_qual(code)):
                    return code
    return None


def _question(subject: str, field: str, rule: dict, profile: dict) -> dict | None:
    if subject == "parent" and field not in PARENT_PROFILE_FIELDS:  # 예전 카드나 다른 경로에서도 부모님 저장 불가 질문을 내보내지 않아요.
        return None  # 부모님 소득이나 본인 전용 가구원 수는 질문 대신 확인 필요로 남겨요.
    me = profile.get("self", profile)
    sensitive_ok = bool((profile.get("consents") or {}).get("sensitive"))
    if field == "qual_code":
        code = _qual_to_ask(rule, me, sensitive_ok)
        if code is None:
            return None
        line = {"qual_code": code, "target": "본인", "verified": "자기신고"}
        return {"question": f"‘{code}’에 해당하시나요?", "qual_code": code,
                "options": [{"label": "예", "value": "Y", "add_qualification": dict(line)},
                            {"label": "아니오", "value": "N", "add_qualification": {**line, "has": "N"}}]}
    if subject == "parent" and field == "birth_date":
        q, opts = PARENT_BIRTH_DATE
    elif field in QUESTIONS:
        q, opts = QUESTIONS[field]
    else:
        return None
    return {"question": q, "options": [dict(o) for o in opts]}


def choose_ask(cards: list[dict], by_id: dict[str, dict], profile: dict, focus: str | None = None) -> dict | None:
    """cards: 화면에 올릴 수 있는 카드(엔진 결과). by_id: rule_id → 조건표."""
    candidates = [c for c in cards if c["verdict"] == "needs_check" and not c.get("no_subject")
                  and not c.get("superseded_by")]
    if focus is not None:
        pool = [c for c in candidates if c["rule_id"] == focus]
    elif len(candidates) >= MIN_CANDIDATES:
        pool = candidates
    else:
        return None

    count: dict[tuple[str, str], list[dict]] = {}
    for c in pool:
        for field in c.get("blocking_fields") or []:
            count.setdefault((c["subject"], field), []).append(c)
    rank = {f: i for i, f in enumerate(ORDER)}
    for (subject, field), cs in sorted(count.items(), key=lambda kv: (-len(kv[1]), rank.get(kv[0][1], 999), kv[0])):
        asked = _question(subject, field, by_id[cs[0]["rule_id"]], profile)
        if asked is None:
            continue
        why = "이 제도는 이 칸을 알아야 판정돼요" if focus else f"후보 {len(candidates)}개 중 {len(cs)}개가 이 칸으로 갈려요"
        return {"subject": subject, "field": field, **asked, "why": why,
                "rule_id": cs[0]["rule_id"] if focus else None}
    return None
