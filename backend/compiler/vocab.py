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
# 한 글자 말("명", "인", "여", "세")은 다른 낱말("세대주") 속에서도 걸려 필드를 가르지 못하므로 쓰지 않는다.
# 나이 조건은 수의 단위 "세"가 신호어를 대신한다(verify).
FIELD_KEYWORDS = {
    "age": ["나이", "연령"],
    "gender": ["남성", "여성", "남자", "여자", "성별"],
    "sido": ["거주", "주소", "주민등록", "전입", "지역", "관내"],
    "sigungu": ["거주", "주소", "주민등록", "전입", "관내"],
    "marital_status": ["혼인", "결혼", "신혼", "예비", "배우자", "미혼", "기혼", "한부모", "이혼", "사별"],
    "marriage_years": ["혼인", "결혼", "신혼"],
    "pregnant": ["임신", "임산부", "태아"],
    "due_month": ["출산", "분만", "예정"],
    "children_count": ["자녀", "아동", "출산", "다자녀"],
    "youngest_child_age": ["자녀", "아동", "영유아", "신생아", "출생", "막내", "아이"],
    "household_size": ["가구원", "세대원", "세대구성원", "인 가구", "인가구", "가구"],
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
    "income_spouse": ["소득", "연봉", "급여"],
    "income_household": ["소득"],
    "income_couple": ["소득", "맞벌이", "합산"],
    "income_recognized": ["소득인정액"],
    "income_band_median": ["중위소득"],
    "income_band_urban": ["도시근로자"],
    "dependents_count": ["부양"],
    "supports_parent_65": ["부양", "직계존속", "노부모"],
    "support_years": ["부양"],
    "has_account": ["청약", "통장", "주택청약종합저축", "청약저축", "청약예금"],
    "subscription_months": ["청약", "통장", "가입", "저축"],
    "payment_count": ["납입", "회차"],
    "deposit_amount": ["예치", "납입금액", "예치금"],
    "homeless_years": ["무주택"],
    "qual_code": [],
    "history": [],
    "relation": ["부모", "아버지", "어머니", "부친", "모친"],
    "lives_alone": ["독거", "홀로", "혼자", "1인"],
    "lives_with_child": ["자녀", "동거"],
    "ltc_grade": ["장기요양", "등급", "인지지원"],
    "disability_registered": ["장애"],
    "basic_pension": ["기초연금"],
    "livelihood_status": ["생계", "의료", "주거급여", "교육급여", "수급", "차상위"],
    "care_wanted": ["돌봄"],
    "apply_date": ["신청", "접수", "모집"],
}
# 이 말이 그 수와 같은 절에 있으면 그 필드가 아니다(자녀·부모 나이를 본인 나이로, 자산을 소득으로, 계약 기간을 접수 기간으로).
_NOT_INCOME = ["자산", "자동차", "차량", "부동산"]
FIELD_NOT_KEYWORDS = {
    "age": ["자녀", "아동", "영유아", "신생아", "막내", "직계존속", "부모", "태아"],
    "income_self": _NOT_INCOME, "income_spouse": _NOT_INCOME, "income_household": _NOT_INCOME,
    "income_couple": _NOT_INCOME, "income_recognized": ["자동차", "차량"],
    "apply_date": ["계약", "입주", "임대차", "사업", "거주", "공고일", "발표", "당첨"],
}
# 소득 주체: 그 수의 절에서 수 앞에 나온 말로 정한다(앞의 것이 먼저). 아무 말도 없으면 본인 소득으로 본다.
# "세대주"·"가구주"는 사람이라 가구 소득이 아니다.
INCOME_OWNER = [
    ("income_couple", r"부부|합산|맞벌이|본인\s*(?:과|와|및)\s*배우자"),
    ("income_spouse", r"배우자"),
    ("income_household", r"가구(?!주)|세대(?!주)"),
    ("income_self", r"본인|신청인|신청자|개인|세대주|가구주"),
]
# 소득 기준(income_basis)을 정하는 말. 근거에 다른 기준의 말만 있으면 떨어뜨린다.
BASIS_WORDS = {
    "median_pct": r"중위",
    "urban_worker_pct": r"도시\s*근로자",
    "recognized": r"소득\s*인정액",
    "absolute_monthly": r"월\s*평균|월\s*소득|월\s*급여|매\s*월|월\s*간|/\s*월|(?:^|[^\d\s.])\s*월\s+\d",
    "absolute_annual": r"연\s*소득|연\s*간|연\s*봉|연\s*평균|연\s*급여|/\s*년|(?:^|[^\d\s.])\s*연\s+\d",
}

# 범주 값(api.md §1·§2). 값이 이 안에 있어야 한다. Y/N 칸은 "Y"|"N".
_YN = ["Y", "N"]
FIELD_VALUES = {
    "gender": ["남", "여"],
    "marital_status": ["미혼", "예비부부", "신혼", "기혼", "이혼·사별"],
    "employment_status": ["재학", "구직", "재직", "자영업", "육아휴직", "기타"],
    "tenure_type": ["자가", "전세", "월세", "보증부월세", "무상거주"],
    "is_householder": ["세대주", "세대원"],
    "employment_type": ["맞벌이", "외벌이", "해당없음"],
    "relation": ["부", "모"],
    "ltc_grade": ["없음", "1등급", "2등급", "3등급", "4등급", "5등급", "인지지원등급"],
    "livelihood_status": ["생계", "의료", "주거", "교육", "차상위", "해당없음"],
    **{f: _YN for f in ["is_homeless", "pregnant", "has_account", "supports_parent_65", "lives_alone", "lives_with_child",
                        "disability_registered", "basic_pension", "care_wanted"]},
}
# 범주 값이 근거에 있다고 볼 말(띄어쓰기 무시). 표에 없으면 값 자체, Y는 그 필드의 신호어를 찾는다.
# 신혼은 기혼의 한 갈래라 "기혼자"도 신혼을 뒷받침한다.
_MARRIED = ["기혼", "혼인한", "혼인중", "혼인 중", "배우자가 있는", "배우자 있는"]
_BASIC = ["기초생활수급", "기초생활 수급"]
VALUE_WORDS = {
    ("is_homeless", "Y"): ["무주택", "주택을 소유하지", "주택을 소유하고 있지 아니", "주택을 보유하지", "주택이 없"],
    ("is_homeless", "N"): ["유주택", "주택 소유자", "주택을 소유한", "주택을 소유하고 있는", "1주택"],
    ("marital_status", "미혼"): ["미혼", "혼인하지", "결혼하지", "혼인한 적이 없", "혼인 이력이 없"],
    ("marital_status", "예비부부"): ["예비부부", "예비신혼", "결혼 예정", "혼인 예정"],
    ("marital_status", "신혼"): ["신혼", "혼인기간", "혼인 기간", *_MARRIED],
    ("marital_status", "기혼"): _MARRIED,
    ("marital_status", "이혼·사별"): ["이혼", "사별"],
    ("gender", "남"): ["남성", "남자"],
    ("gender", "여"): ["여성", "여자"],
    ("employment_status", "재학"): ["재학", "대학생", "학생"],
    ("employment_status", "구직"): ["구직", "미취업", "실업"],
    ("employment_status", "재직"): ["재직", "근로자", "근무", "직장인"],
    ("employment_status", "자영업"): ["자영업", "사업자"],
    ("employment_status", "육아휴직"): ["육아휴직"],
    ("tenure_type", "자가"): ["자가", "자기 소유"],
    ("tenure_type", "보증부월세"): ["보증부월세", "보증부 월세", "반전세"],
    ("tenure_type", "무상거주"): ["무상"],
    ("employment_type", "외벌이"): ["외벌이", "홑벌이"],
    ("relation", "부"): ["부모", "아버지", "부친"],
    ("relation", "모"): ["부모", "어머니", "모친"],
    ("livelihood_status", "생계"): ["생계", *_BASIC],
    ("livelihood_status", "의료"): ["의료급여", *_BASIC],
    ("livelihood_status", "주거"): ["주거급여", *_BASIC],
    ("livelihood_status", "교육"): ["교육급여", *_BASIC],
}
# 시도 정식 이름 → 줄임말. 근거에는 둘 중 하나가 있으면 된다.
SIDO = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주",
    "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원",
    "충청북도": "충북", "충청남도": "충남", "전북특별자치도": "전북", "전라남도": "전남", "경상북도": "경북",
    "경상남도": "경남", "제주특별자치도": "제주",
}
# 시도 조건 값은 17개 시도의 정식 이름이나 줄임말이다("○○시"·"수원시"는 시도가 아니다).
FIELD_VALUES["sido"] = [*SIDO, *SIDO.values()]

# 신호어 표시(SPEC §9.2): 이 말이 있는 줄은 LLM이 근거로 쓰거나 라벨을 달아야 한다.
# 개발용 손 조건표 5개로 맞춘다(시험용은 보지 않는다).
SIGNAL_WORDS = [
    "이하", "이상", "이내", "미만", "초과", "무주택", "세대주", "소득", "자산", "거주", "전입",
    "혼인", "출산", "자녀", "청약", "납입", "제외", "중복", "불가", "만 ", "세 ", "연령", "나이",
    "중위", "도시근로자", "임신", "부양", "장기요양", "기초연금", "수급", "차상위", "장애",
    "보증금", "월세", "전세", "가구원", "세대원", "신혼", "예비", "한부모", "다자녀", "대상",
    # 조건인데 위 말이 없는 흔한 문장: 무주택 정의, 지역 요건, 접수 기간, 제외 문장
    "주택을 소유", "주택소유", "소유하지", "주민등록", "생애최초", "당첨", "접수", "신청기간", "까지", "부터",
    "수 없", "불가능", "제한",
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

# 업로드 원문에서 거부하는 주민등록번호 패턴(SPEC §9.5). lines.has_rrn이 전각 숫자·여러 가지 줄표·표 칸 구분을
# 먼저 고르게 맞춘 글에 쓴다. 하이픈 없이 붙여 쓴 13자리, 줄이나 칸이 나뉜 번호도 잡는다.
# 뒷자리 첫 숫자 5~8은 외국인등록번호다(같은 꼴이고 똑같이 개인을 가리킨다)
RRN_PATTERN = r"(?<!\d)\d{6}\s*-?\s*[1-8]\d{6}(?!\d)"
