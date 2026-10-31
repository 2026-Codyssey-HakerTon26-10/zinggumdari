"""조건 → "우리가 읽은 조건" 문장(카드의 read_as). 템플릿만 쓰고 LLM을 쓰지 않는다."""

LABEL = {
    "age": "나이", "gender": "성별", "sido": "거주 시도", "sigungu": "거주 시군구", "marital_status": "혼인 상태",
    "marriage_years": "혼인 기간", "pregnant": "임신", "due_month": "출산 예정월", "children_count": "자녀 수",
    "youngest_child_age": "막내 나이", "household_size": "가구원 수", "employment_status": "취업 상태",
    "tenure_type": "주거 형태", "is_householder": "세대주 여부", "is_homeless": "무주택", "deposit": "보증금",
    "monthly_rent": "월세", "residence_months": "거주 기간", "house_price": "주택 가격", "employment_type": "맞벌이 여부",
    "income_self": "본인 소득", "income_spouse": "배우자 소득", "income_household": "가구 소득",
    "income_couple": "부부합산 소득", "income_band_median": "가구 소득", "income_band_urban": "가구 소득",
    "income_recognized": "소득인정액", "dependents_count": "부양가족 수", "supports_parent_65": "만 65세 이상 부모 부양",
    "support_years": "부양 기간", "has_account": "청약통장", "subscription_months": "청약통장 가입 기간",
    "payment_count": "청약 납입 횟수", "deposit_amount": "청약 예치금", "qual_code": "자격", "history": "이력",
    "homeless_years": "무주택 기간", "relation": "관계", "lives_alone": "혼자 사는지", "lives_with_child": "자녀와 사는지",
    "ltc_grade": "장기요양등급", "disability_registered": "장애 등록", "basic_pension": "기초연금 수급",
    "livelihood_status": "수급·차상위", "care_wanted": "돌봄 희망", "apply_date": "신청일",
}
OP = {"<=": "이하", ">=": "이상", "<": "미만", ">": "초과", "!=": "아님", "==": "", "in": "중 하나", "not_in": "제외"}
AS_OF = {"application_date": "신청일 기준", "notice_date": "공고일 기준"}
BASIS = {"median_pct": "기준 중위소득", "urban_worker_pct": "도시근로자 월평균소득"}
YES_NO = {"Y": "예", "N": "아니오"}


def _value(cond: dict) -> str:
    f, v, basis = cond["field"], cond.get("value"), cond.get("income_basis")
    if isinstance(v, list):
        return "·".join(map(str, v))
    if f.startswith("income") and basis in BASIS:
        return f"{BASIS[basis]} {v:g}%"
    if f.startswith("income") or f in ("deposit", "monthly_rent", "house_price", "deposit_amount"):
        unit = "연 " if basis == "absolute_annual" else "월 " if f.startswith("income") else ""
        return f"{unit}{v:,g}만 원"
    if f == "age":
        return f"만 {v}세"
    if f.endswith("_years"):
        return f"{v}년"
    if f.endswith("_months"):
        return f"{v}개월"
    if f == "youngest_child_age":
        return f"{v}세"
    if f in ("children_count", "household_size", "dependents_count"):
        return f"{v}명"
    if f == "payment_count":
        return f"{v}회"
    return YES_NO.get(v, str(v))


def read_as(cond: dict) -> str:
    if cond.get("any_of"):
        return ", 또는 ".join(" 그리고 ".join(read_as(c) for c in branch) for branch in cond["any_of"])
    if cond.get("field") == "other":
        return cond.get("text") or "원문 조건"
    text = " ".join(s for s in (LABEL.get(cond["field"], cond["field"]), _value(cond), OP.get(cond["op"], cond["op"])) if s)
    return f"{text}({AS_OF[cond['as_of']]})" if cond.get("as_of") in AS_OF else text
