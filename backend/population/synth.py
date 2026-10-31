"""Nemotron 한 사람 → 가상 사용자 한 줄 (SPEC §13.1).

칸은 팀 시트 「복지추천_필드스키마_3단계」의 DB샘플 탭(users, housing, income, subscription)과 같다.
원본 칸(성별, 나이, 지역, 혼인, 가구 형태, 직업)은 그대로 쓴다. 원본에 없는 칸은
글(`family_persona`, `persona`)에 드러나면 글을 따르고, 아니면 ASSUMPTIONS로 뽑는다.
글에서 온 칸은 `from_text`에 남긴다. 칸 사이 모순은 check()가 잡는다.
"""

from __future__ import annotations

import math
import re
from datetime import date, timedelta

import numpy as np
import pandas as pd

AS_OF = date(2026, 10, 31)  # SPEC 기준일. 나이와 혼인 기간은 이 날 기준

# 가정값은 전부 여기 둔다. build가 meta.json과 xlsx 「출처·가정」 탭으로 내보내 화면에 밝힌다
ASSUMPTIONS = {
    "first_marriage_age_mean": {"남": 33.9, "여": 31.6},  # 통계청 2024년 혼인·이혼 통계 평균 초혼연령
    "first_marriage_age_sd": 3.0,
    "min_marriage_age": 20,
    "newlywed_max_years": 7,  # 혼인 7년 이내면 신혼(주택 제도의 신혼부부 정의)
    "text_newlywed_max_years": 2,  # 글에 "신혼"이 있으면 혼인 2년 이내
    "first_child_after_marriage_years": [0.0, 3.0],  # 균등
    "child_gap_years": [1.0, 4.0],  # 균등
    "plural_children_three_share": 0.15,  # 글에 "아이들"만 있으면 2명, 이 비율로 3명
    "engaged_rate": 0.05,  # 미혼·자녀 없음·25~39세 중 예비부부
    "engaged_age": [25, 39],
    "pregnant_rate": 0.07,  # 혼인한 25~39세 여성(막내가 1세 이상이거나 자녀 없음) 중 임신
    "pregnant_age": [25, 39],
    "parental_leave_rate": {"여": 0.30, "남": 0.07},  # 일하는 부모 중 막내 0세면 육아휴직
    "self_employed_rate": 0.07,  # 직업이 있고 글에 단서가 없을 때 자영업
    # 직업이 "무직"이고 글에 단서가 없을 때 나이대별 (재학, 구직, 기타)
    "jobless_split": {"19": [0.70, 0.30, 0.00], "25": [0.15, 0.50, 0.35], "30": [0.00, 0.40, 0.60]},
    # ② 칸
    "tenure_uniform": ["자가", "전세", "월세", "보증부월세"],  # 독립 가구이고 글에 없을 때 균등
    "householder_married_rate": 0.5,  # 부부 중 본인이 세대주
    "dual_income_rate": 0.55,  # 일하는 기혼자 중 맞벌이
    "income_monthly": {  # 만원, 균등
        "재직": [180, 450], "자영업": [100, 500], "육아휴직": [100, 250],
        "재학": [0, 80], "구직": [0, 80], "기타": [0, 80],
        "spouse": [180, 450], "parents": [200, 600],
    },
    "parent_65_rate": 0.15,  # 부모와 사는 30세 이상 중 만 65세 이상 부모 부양
    "parent_65_min_age": 30,
    "subscription_account_rate": 0.70,
}

MARITAL = ("미혼", "예비부부", "신혼", "기혼", "이혼·사별")
EMPLOYMENT = ("재학", "구직", "재직", "자영업", "육아휴직", "기타")
TENURE = ("자가", "전세", "월세", "보증부월세", "무상거주")
WORKING = ("재직", "자영업", "육아휴직")

# 원본 province → 프로필의 시도 줄임말(시트 "서울", "경기"). 표에 없으면 그대로
SIDO = {"경상남": "경남", "경상북": "경북", "충청남": "충남", "충청북": "충북", "전라남": "전남"}
SIDO_ALL = {"서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기",
            "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"}

# family_type → 본인 포함 가구원 수(자녀 제외. 자녀는 children_count로 더한다). 원본의 39종 전부
HOUSEHOLD_BASE = {
    "혼자 거주": 1, "혼자 거주 (배우자 별거)": 1, "배우자와 거주": 2, "배우자·자녀와 거주": 2,
    "부모와 동거": 3, "어머니와 동거": 2, "아버지와 동거": 2, "부 또는 모와 거주": 2,
    "기타1세대": 2, "기타2세대": 3, "기타3세대": 4, "4세대이상": 6,
    "자녀와 거주 (한부모)": 1, "자녀와 거주 (배우자 별거)": 1,
    "자녀·어머니와 거주": 2, "자녀·아버지와 거주": 2,
    "배우자·자녀·어머니와 거주": 3, "배우자·자녀·아버지와 거주": 3, "배우자·자녀·부모와 거주": 4,
    "배우자·자녀·형제자매와 거주": 3, "배우자·편부모와 거주": 3, "배우자·부모와 거주": 4,
    "배우자·친인척과 거주": 3, "배우자·형제자매와 거주": 3, "배우자·미혼 형제자매와 거주": 3,
    "배우자·손자녀와 거주": 3, "손자녀와 거주": 2,
    "부모·조모와 동거": 4, "부모·조부와 동거": 4, "부모·조부모와 동거": 5,
    "부모·형제자매와 동거": 4, "부모·친인척과 동거": 4,
    "조부 또는 조모와 동거": 2, "조부모와 동거": 3,
    "형제자매와 동거 (가구주)": 2, "형제 부부 가구에 동거": 3,
    "친인척과 거주": 2, "가구주+기타친인척": 2, "비친족 동거": 2,
}
# 본인이 남의 집(부모, 조부모, 형제 부부)에 얹혀 사는 가구 형태 → 무상거주·세대원
LIVES_IN_OTHERS_HOME = ("부모", "어머니와", "아버지와", "부 또는 모", "조부", "조모", "형제 부부")
HEAD_OF_HOUSEHOLD = ("혼자 거주", "혼자 거주 (배우자 별거)", "자녀와 거주 (한부모)",
                     "자녀와 거주 (배우자 별거)", "형제자매와 동거 (가구주)", "가구주+기타친인척", "비친족 동거")

KIDS_AT_HOME = re.compile(r"(?<!손)자녀")  # "배우자·손자녀와 거주"는 자녀가 아니다
TWO_PARENTS = re.compile(r"(?<![조편])부모")  # "조부모", "편부모"는 아니다
ONE_PARENT = re.compile(r"어머니|아버지|편부모|부 또는 모")
THREE_KIDS = re.compile(r"세 아이|세 자녀|아이 셋")
PLURAL_KIDS = re.compile(r"아이들|자녀들|두 아이|두 자녀|아이 둘")
NEWLYWED = re.compile(r"신혼")
STUDENT = re.compile(r"대학생|대학원|학생|휴학|복학")
JOBSEEK = re.compile(r"취업 준비|취업준비|취준|구직")
HOMEMAKER = re.compile(r"주부")
SELF_EMPLOYED = re.compile(r"자영업|가게를 운영|가게를 꾸려|사장님|운영하는 (가게|식당|카페|매장)")
# "전·월세", "전월세"는 둘 중 무엇인지 몰라서 어느 패턴에도 걸리지 않는다
TENURE_TEXT = {
    "자가": re.compile(r"자가 (아파트|주택|단독주택|빌라|집)|자가에서"),
    "전세": re.compile(r"(?<![월·])전세"),
    "월세": re.compile(r"(?<![전·])월세"),
}
NAME = re.compile(r"^(\S{2,4}) 씨")  # persona 첫머리 "전기태 씨는" → 닉네임은 이름만("기태")

_NOT_YET_BIRTHDAY = (date(AS_OF.year, 12, 31) - AS_OF).days / 365  # 기준일 뒤에 생일인 비율


def _years(d: date) -> float:
    return (AS_OF - d).days / 365.25


def _add_months(d: date, months: int) -> str:
    y, m = divmod(d.month - 1 + months, 12)
    return f"{d.year + y:04d}-{m + 1:02d}"


def _uniform_int(rng: np.random.Generator, lo_hi) -> int:
    return int(round(rng.uniform(*lo_hi)))


def _parents_at_home(family_type: str) -> int:
    if TWO_PARENTS.search(family_type):
        return 2
    return 1 if ONE_PARENT.search(family_type) else 0


def _person(r, rng: np.random.Generator) -> dict:
    A = ASSUMPTIONS
    age = int(r.age)
    gender = "남" if r.sex == "남자" else "여"
    ft = r.family_type
    text = r.family_persona or ""
    profile = f"{r.persona or ''} {text}"
    from_text: list[str] = []

    if ft not in HOUSEHOLD_BASE:
        raise ValueError(f"표에 없는 family_type: {ft!r}")

    # 자녀: 가구 형태에 자녀가 있을 때만. 수는 글에서
    kids = 0
    if KIDS_AT_HOME.search(ft):
        if THREE_KIDS.search(text):
            kids = 3
            from_text.append("children_count")
        elif PLURAL_KIDS.search(text):
            kids = 3 if rng.random() < A["plural_children_three_share"] else 2
            from_text.append("children_count")
        else:
            kids = 1

    # 혼인. 자녀는 혼인 뒤에 태어난 것으로 놓고, 막내가 혼인 기간 안에 들어오게 혼인 연령을 맞춘다
    marriage_date = None
    youngest = None
    if r.marital_status in ("이혼", "사별"):
        status = "이혼·사별"
    elif r.marital_status == "미혼":
        lo, hi = A["engaged_age"]
        status = "예비부부" if kids == 0 and lo <= age <= hi and rng.random() < A["engaged_rate"] else "미혼"
    else:
        if NEWLYWED.search(text):
            room = max(0, age - A["min_marriage_age"])
            married_for = min(rng.uniform(0, A["text_newlywed_max_years"]), room)
            from_text.append("marital_status")
        else:
            # 이미 혼인했으니 지금 나이보다 늦은 혼인 연령은 다시 뽑는다(잘린 정규분포)
            m_age = rng.uniform(A["min_marriage_age"], max(age, A["min_marriage_age"]))
            for _ in range(20):
                draw = rng.normal(A["first_marriage_age_mean"][gender], A["first_marriage_age_sd"])
                if A["min_marriage_age"] <= draw <= age:
                    m_age = draw
                    break
            married_for = max(0.0, age - m_age)
        if kids:
            since = rng.uniform(*A["first_child_after_marriage_years"])
            since += sum(rng.uniform(*A["child_gap_years"]) for _ in range(kids - 1))
            if since > married_for and "marital_status" not in from_text:
                married_for = min(since + rng.uniform(0, 2), age - A["min_marriage_age"])
            if since > married_for:  # 그래도 안 들어가면 간격을 줄인다
                since = married_for * rng.uniform(0.5, 1.0)
            youngest = math.floor(married_for - since)
        marriage_date = AS_OF - timedelta(days=int(married_for * 365.25))
        status = "신혼" if _years(marriage_date) <= A["newlywed_max_years"] else "기혼"

    if kids and youngest is None:  # 혼인 밖의 자녀(한부모, 이혼·사별)
        room = max(0, age - A["min_marriage_age"] - 2 * (kids - 1))
        youngest = int(rng.integers(0, min(room, 15) + 1))
    married = status in ("신혼", "기혼")

    # 임신
    pregnant, due_month = "N", None
    lo, hi = A["pregnant_age"]
    if (gender == "여" and married and lo <= age <= hi
            and (youngest is None or youngest >= 1) and rng.random() < A["pregnant_rate"]):
        pregnant, due_month = "Y", _add_months(AS_OF, int(rng.integers(1, 10)))

    # 취업 상태
    if r.occupation == "무직":
        if age <= 29 and STUDENT.search(profile):
            job = "재학"
        elif JOBSEEK.search(profile):
            job = "구직"
        elif HOMEMAKER.search(profile):
            job = "기타"
        else:
            job = None
        if job:
            from_text.append("employment_status")
        else:
            band = "30" if age >= 30 else "25" if age >= 25 else "19"
            job = str(rng.choice(["재학", "구직", "기타"], p=A["jobless_split"][band]))
    elif SELF_EMPLOYED.search(profile):
        job = "자영업"
        from_text.append("employment_status")
    elif youngest == 0 and rng.random() < A["parental_leave_rate"][gender]:
        job = "육아휴직"
    else:
        job = "자영업" if rng.random() < A["self_employed_rate"] else "재직"

    # 주거. 남의 집에 사는 사람은 무상거주·세대원(글의 전세·자가는 그 집 이야기라 쓰지 않는다)
    if ft.startswith(LIVES_IN_OTHERS_HOME):
        tenure, householder = "무상거주", "세대원"
    else:
        hits = [k for k, p in TENURE_TEXT.items() if p.search(text)]
        if len(hits) == 1:
            tenure = hits[0]
            from_text.append("tenure_type")
        else:
            tenure = str(rng.choice(A["tenure_uniform"]))
        if ft in HEAD_OF_HOUSEHOLD:
            householder = "세대주"
        elif married:
            householder = "세대주" if rng.random() < A["householder_married_rate"] else "세대원"
        else:
            householder = "세대원"

    # 소득(만원/월)과 부양
    parents = _parents_at_home(ft)
    income_self = _uniform_int(rng, A["income_monthly"][job])
    income_spouse = None
    employment_type = "해당없음"
    if married:
        if job in WORKING:
            employment_type = "맞벌이" if rng.random() < A["dual_income_rate"] else "외벌이"
        else:
            employment_type = "외벌이"  # 본인이 일하지 않으면 배우자가 번다
        works = employment_type == "맞벌이" or job not in WORKING
        income_spouse = _uniform_int(rng, A["income_monthly"]["spouse"]) if works else 0
    income_parents = _uniform_int(rng, A["income_monthly"]["parents"]) if parents else 0
    supports_parent = ("Y" if parents and age >= A["parent_65_min_age"]
                       and rng.random() < A["parent_65_rate"] else "N")

    nickname = NAME.match(r.persona or "")
    return {
        "source_uuid": r.uuid,
        # ① users
        "nickname": nickname.group(1)[1:] if nickname else None,
        "gender": gender,
        "birth_year": AS_OF.year - age - (1 if rng.random() < _NOT_YET_BIRTHDAY else 0),
        "sido": SIDO.get(r.province, r.province),
        "sigungu": r.district.split("-", 1)[1].split()[0],
        "marital_status": status,
        "marriage_date": marriage_date.isoformat() if marriage_date else None,
        "pregnant": pregnant,
        "due_month": due_month,
        "children_count": kids,
        "youngest_child_age": youngest,
        "household_size": HOUSEHOLD_BASE[ft] + kids,
        "employment_status": job,
        # ② user_housing
        "tenure_type": tenure,
        "is_householder": householder,
        "is_homeless": "N" if tenure == "자가" else "Y",
        # ② user_income
        "employment_type": employment_type,
        "income_self": income_self,
        "income_spouse": income_spouse,
        "income_household": income_self + (income_spouse or 0) + income_parents,
        "dependents_count": (1 if married else 0) + kids + (parents if supports_parent == "Y" else 0),
        "supports_parent_65": supports_parent,
        # ② user_subscription
        "has_account": "Y" if rng.random() < A["subscription_account_rate"] else "N",
        # 원본과 출처
        "family_type": ft,
        "occupation": r.occupation,
        "from_text": from_text,
    }


def synthesize(raw: pd.DataFrame, seed: int, holdout: int) -> pd.DataFrame:
    """raw(Nemotron 행) → 사용자 표. 뒤쪽 holdout명은 평가용(split="holdout")."""
    rng = np.random.default_rng(seed)
    rows = [_person(r, rng) for r in raw.itertuples(index=False)]
    df = pd.DataFrame(rows).astype({"youngest_child_age": "Int64", "income_spouse": "Int64"})
    width = max(4, len(str(len(df))))
    df.insert(0, "user_id", [f"U{i + 1:0{width}d}" for i in range(len(df))])
    df.insert(1, "split", ["pool"] * (len(df) - holdout) + ["holdout"] * holdout)
    return df


def check(df: pd.DataFrame) -> list[str]:
    """칸 사이 모순. 빈 목록이면 통과."""
    A = ASSUMPTIONS
    bad: list[str] = []
    due_max = _add_months(AS_OF, 9)
    for r in df.itertuples(index=False):
        def fail(msg: str) -> None:
            bad.append(f"{r.user_id}: {msg}")

        age = AS_OF.year - r.birth_year  # 만 나이는 age 또는 age-1
        married = r.marital_status in ("신혼", "기혼")
        kids = r.children_count
        youngest = None if pd.isna(r.youngest_child_age) else int(r.youngest_child_age)

        for col, allowed in (("marital_status", MARITAL), ("employment_status", EMPLOYMENT),
                             ("tenure_type", TENURE), ("gender", ("남", "여")), ("sido", SIDO_ALL),
                             ("pregnant", ("Y", "N")), ("is_householder", ("세대주", "세대원")),
                             ("is_homeless", ("Y", "N")), ("supports_parent_65", ("Y", "N")),
                             ("has_account", ("Y", "N")),
                             ("employment_type", ("맞벌이", "외벌이", "해당없음"))):
            if getattr(r, col) not in allowed:
                fail(f"{col}={getattr(r, col)!r}는 허용값이 아니다")

        if married != pd.notna(r.marriage_date):
            fail("혼인신고일은 신혼·기혼일 때만 있다")
        if married:
            years = _years(date.fromisoformat(r.marriage_date))
            if (years <= A["newlywed_max_years"]) != (r.marital_status == "신혼"):
                fail(f"혼인 {years:.1f}년인데 {r.marital_status}")
            if int(r.marriage_date[:4]) - r.birth_year < A["min_marriage_age"] - 1:
                fail("혼인 연령이 너무 어리다")
            if youngest is not None and youngest > years:
                fail("막내가 혼인 기간보다 나이가 많다")
        if (kids == 0) != (youngest is None):
            fail("막내 나이는 자녀가 있을 때만 있다")
        if youngest is not None and youngest > age - A["min_marriage_age"]:
            fail("막내 나이가 부모 나이에 비해 많다")
        if r.household_size < 1 + kids:
            fail("가구원 수가 본인 + 자녀보다 적다")
        if r.pregnant == "Y":
            if r.gender != "여" or not married:
                fail("임신은 혼인한 여성만")
            if pd.isna(r.due_month) or not (AS_OF.strftime("%Y-%m") < r.due_month <= due_max):
                fail(f"출산 예정월 {r.due_month}")
        elif pd.notna(r.due_month):
            fail("임신이 아닌데 출산 예정월이 있다")
        if r.employment_status == "육아휴직" and (youngest is None or youngest > 1):
            fail("육아휴직인데 0~1세 자녀가 없다")

        if (r.tenure_type == "자가") != (r.is_homeless == "N"):
            fail("자가면 무주택이 아니고, 아니면 무주택")
        if married == (r.employment_type == "해당없음"):
            fail("맞벌이·외벌이는 신혼·기혼일 때만")
        if r.employment_type == "맞벌이" and r.employment_status not in WORKING:
            fail("맞벌이인데 본인이 일하지 않는다")
        if married == pd.isna(r.income_spouse):
            fail("배우자 소득은 신혼·기혼일 때만")
        if r.income_household < r.income_self + (0 if pd.isna(r.income_spouse) else r.income_spouse):
            fail("가구 소득이 본인 + 배우자보다 적다")
        if r.dependents_count < kids:
            fail("부양가족이 자녀 수보다 적다")
        if r.supports_parent_65 == "Y" and not _parents_at_home(r.family_type):
            fail("부모와 살지 않는데 노부모 부양")
    return bad
