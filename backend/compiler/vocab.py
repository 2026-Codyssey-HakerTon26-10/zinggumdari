"""조건 JSON의 통제 어휘(docs/api.md §1)와 검증기·신호어 표시가 쓰는 사전.

어휘를 늘리려면 팀 시트와 api.md를 먼저 고치고 여기를 맞춘다.
"""

# 필드 → 대상(self/parent/common). api.md §1 표 그대로.
FIELDS_SELF = [
    "age", "gender", "sido", "sigungu", "marital_status", "marriage_years", "pregnant", "due_month",
    "children_count", "youngest_child_age", "household_size", "employment_status",
    "tenure_type", "is_householder", "is_homeless", "deposit", "monthly_rent", "residence_months",
    "house_price", "employment_type", "income_self", "income_spouse", "income_household", "income_couple",
    "income_band_median", "income_band_urban", "dependents_count", "supports_parent_65", "support_years",
    "has_account", "subscription_months", "payment_count", "deposit_amount",
    "qual_code", "history", "homeless_years", "income_recognized",
]
FIELDS_PARENT = [
    "relation", "lives_alone", "lives_with_child", "ltc_grade", "disability_registered", "basic_pension",
    "livelihood_status", "care_wanted",
]
FIELDS_COMMON = ["apply_date", "other"]
FIELDS = list(dict.fromkeys(FIELDS_SELF + FIELDS_PARENT + FIELDS_COMMON))

OPS = ["==", "!=", "<=", ">=", "<", ">", "in", "not_in"]
INCOME_BASIS = ["median_pct", "urban_worker_pct", "absolute_annual", "absolute_monthly", "recognized"]
AS_OF = ["notice_date", "application_date"]
LABELS = ["definition", "procedure", "exclusive", "out_of_scope", "not_condition"]
DOMAINS = ["housing", "fund_loan", "subscription", "elderly", "welfare"]
BENEFIT_TYPES = ["loan", "rent", "cash", "service", "discount"]
SUBJECTS = ["self", "parent"]

# 수 조건의 단위 종류. normalize가 원문 수에 붙이는 kind와 같은 이름이다.
#   money(만원) percent(%) age(세) months(개월) years(년) count(명·회·인·가구·자녀) date(YYYY-MM-DD)
# 필드마다 받을 수 있는 kind. 값은 조건의 value 단위로 바꾼 뒤 비교한다(years→months는 ×12).
FIELD_UNITS = {
    "age": ["age"],
    "youngest_child_age": ["age", "months"],
    "marriage_years": ["years", "months"],
    "support_years": ["years", "months"],
    "homeless_years": ["years", "months"],
    "residence_months": ["months", "years"],
    "subscription_months": ["months", "years"],
    "payment_count": ["count"],
    "children_count": ["count"],
    "household_size": ["count"],
    "dependents_count": ["count"],
    "deposit": ["money"],
    "monthly_rent": ["money"],
    "house_price": ["money"],
    "deposit_amount": ["money"],
    "income_self": ["money", "percent"],
    "income_spouse": ["money", "percent"],
    "income_household": ["money", "percent"],
    "income_couple": ["money", "percent"],
    "income_recognized": ["money", "percent"],
    "income_band_median": ["percent"],
    "income_band_urban": ["percent"],
    "apply_date": ["date"],
    "due_month": ["date"],
}
# 조건 value의 단위. FIELD_UNITS의 첫 kind가 기본이고, 기간은 필드 이름이 정한다.
VALUE_UNIT = {
    "marriage_years": "years", "support_years": "years", "homeless_years": "years",
    "residence_months": "months", "subscription_months": "months",
    "youngest_child_age": "age",
}
PERCENT_BASIS = {"median_pct", "urban_worker_pct"}
MONEY_BASIS = {"absolute_annual", "absolute_monthly", "recognized"}

# 필드 신호어: 근거 줄(수 조건은 그 수와 같은 절)에 이 중 하나가 있어야 한다.
FIELD_KEYWORDS = {
    "age": ["세", "나이", "연령", "생", "출생"],
    "gender": ["남", "여", "성별"],
    "sido": ["거주", "주소", "시", "도", "지역", "관내"],
    "sigungu": ["거주", "주소", "구", "군", "시", "관내"],
    "marital_status": ["혼인", "결혼", "신혼", "예비", "배우자", "미혼", "기혼", "한부모", "이혼", "사별"],
    "marriage_years": ["혼인", "결혼", "신혼"],
    "pregnant": ["임신", "임산부", "태아"],
    "due_month": ["출산", "분만", "예정"],
    "children_count": ["자녀", "자녀수", "아동", "출산", "다자녀", "명"],
    "youngest_child_age": ["자녀", "아동", "영유아", "신생아", "출생", "막내", "세"],
    "household_size": ["가구원", "세대원", "인 가구", "가구", "인"],
    "employment_status": ["재학", "구직", "재직", "근로", "취업", "자영업", "휴직", "미취업", "실업"],
    "tenure_type": ["전세", "월세", "임차", "자가", "무상", "보증부"],
    "is_householder": ["세대주", "세대원"],
    "is_homeless": ["무주택", "주택을 소유", "주택소유", "주택 소유"],
    "deposit": ["보증금", "전세금", "임차보증금"],
    "monthly_rent": ["월세", "월 임대료", "임대료", "차임"],
    "residence_months": ["거주", "전입", "주소"],
    "house_price": ["주택가격", "주택 가격", "분양가", "매매가", "공시가격", "주택가액"],
    "employment_type": ["맞벌이", "외벌이", "홑벌이"],
    "income_self": ["소득", "연봉", "급여"],
    "income_spouse": ["배우자", "소득"],
    "income_household": ["가구", "세대", "소득"],
    "income_couple": ["부부", "합산", "맞벌이", "소득"],
    "income_recognized": ["소득인정액"],
    "income_band_median": ["중위소득"],
    "income_band_urban": ["도시근로자"],
    "dependents_count": ["부양"],
    "supports_parent_65": ["부양", "직계존속", "노부모"],
    "support_years": ["부양"],
    "has_account": ["청약", "통장", "주택청약종합저축", "청약저축", "청약예금"],
    "subscription_months": ["청약", "통장", "가입", "저축"],
    "payment_count": ["납입", "회차", "회"],
    "deposit_amount": ["예치", "납입금액", "예치금"],
    "homeless_years": ["무주택"],
    "qual_code": [],
    "history": [],
    "relation": ["부", "모", "부모"],
    "lives_alone": ["독거", "홀로", "혼자", "1인"],
    "lives_with_child": ["자녀", "동거"],
    "ltc_grade": ["장기요양", "등급", "인지지원"],
    "disability_registered": ["장애"],
    "basic_pension": ["기초연금"],
    "livelihood_status": ["생계", "의료", "주거급여", "교육급여", "수급", "차상위"],
    "care_wanted": ["돌봄"],
    "apply_date": ["신청", "접수", "기간", "까지", "부터", "모집"],
}

# 신호어 표시(SPEC §9.2): 이 말이 있는 줄은 LLM이 근거로 쓰거나 라벨을 달아야 한다.
# 개발용 손 조건표 5개로 맞춘다(시험용은 보지 않는다).
SIGNAL_WORDS = [
    "이하", "이상", "이내", "미만", "초과", "무주택", "세대주", "소득", "자산", "거주", "전입",
    "혼인", "출산", "자녀", "청약", "납입", "제외", "중복", "불가", "만 ", "세 ", "연령", "나이",
    "중위", "도시근로자", "임신", "부양", "장기요양", "기초연금", "수급", "차상위", "장애",
    "보증금", "월세", "전세", "가구원", "세대원", "신혼", "예비", "한부모", "다자녀", "대상",
]

# 자격 구간 제목(SPEC §9.2). 제목처럼 생긴 줄에 이 말이 있으면 구간이 시작된다.
SECTION_START = [
    "신청자격", "신청 자격", "입주자격", "입주 자격", "공급대상", "공급 대상", "지원대상", "지원 대상",
    "선정기준", "선정 기준", "대출대상", "대출 대상", "소득 및 자산", "소득및자산", "자격요건", "자격 요건",
    "신청대상", "신청 대상", "대상자", "지원요건", "지원 요건", "자산보유기준", "소득기준", "자산기준",
    "제출서류", "구비서류", "제출 서류", "구비 서류",
]
# 제목처럼 생긴 줄에 이 말이 있으면(그리고 시작 말이 없으면) 구간이 끝난다.
SECTION_END = [
    "신청방법", "신청 방법", "접수방법", "접수 방법", "신청절차", "공급일정", "일정", "당첨자", "계약",
    "문의", "유의사항", "기타사항", "입주예정", "공급금액", "분양가격", "임대조건", "사업개요", "단지개요",
]

# 업로드 원문에서 거부하는 주민등록번호 패턴(SPEC §9.5).
RRN_PATTERN = r"(?<!\d)\d{6}\s?-\s?[1-4]\d{6}(?!\d)"
