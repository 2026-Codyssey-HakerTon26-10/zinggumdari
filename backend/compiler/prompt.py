"""자격 구간 → 조건 JSON 추출 프롬프트, 출력 스키마, 응답 해석(SPEC §9.2 3단계).

모델은 줄 ID만 근거로 쓰고, parse_output이 `{doc_id}:` 접두어를 붙여 api.md §1 조건 모양으로 바꾼다.
프롬프트를 고치면 PROMPT_VERSION을 올린다(조건표의 compiled.prompt에 남는다).
"""

from __future__ import annotations

from backend.compiler.vocab import (
    AS_OF, BENEFIT_TYPES, DOMAINS, FIELDS, FIELDS_COMMON, FIELDS_PARENT, FIELDS_SELF, INCOME_BASIS, LABELS, OPS,
    SUBJECTS,
)

PROMPT_VERSION = "v1"

# 필드의 한국어 뜻(api.md §1). 괄호 안은 값 또는 단위.
FIELD_HELP = {
    "age": "나이(만 나이, 세)",
    "gender": "성별(남|여)",
    "sido": "거주 시도(예: 서울특별시)",
    "sigungu": "거주 시군구(예: 마포구)",
    "marital_status": "혼인 상태(미혼|예비부부|신혼|기혼|이혼·사별)",
    "marriage_years": "혼인 기간(년)",
    "pregnant": "임신 중(Y|N)",
    "due_month": "출산 예정월(YYYY-MM)",
    "children_count": "자녀 수(명, 태아 포함 여부는 원문대로)",
    "youngest_child_age": "막내 자녀 나이(세)",
    "household_size": "가구원 수(명)",
    "employment_status": "취업 상태(재학|구직|재직|자영업|육아휴직|기타)",
    "tenure_type": "점유 형태(자가|전세|월세|보증부월세|무상거주)",
    "is_householder": "세대주 여부(세대주|세대원)",
    "is_homeless": "무주택(Y|N)",
    "deposit": "임차보증금(만원)",
    "monthly_rent": "월세(만원)",
    "residence_months": "해당 지역 거주 기간(개월)",
    "house_price": "주택 가격(만원)",
    "employment_type": "맞벌이 여부(맞벌이|외벌이|해당없음)",
    "income_self": "본인 소득",
    "income_spouse": "배우자 소득",
    "income_household": "가구(세대) 전체 소득",
    "income_couple": "부부 합산 소득",
    "income_band_median": "기준 중위소득 구간(계산 값, 쓰지 않는다)",
    "income_band_urban": "도시근로자 소득 구간(계산 값, 쓰지 않는다)",
    "dependents_count": "부양가족 수(명)",
    "supports_parent_65": "만 65세 이상 직계존속 부양(Y|N)",
    "support_years": "부양 기간(년)",
    "has_account": "청약통장 보유(Y|N)",
    "subscription_months": "청약통장 가입 기간(개월)",
    "payment_count": "청약통장 납입 횟수(회)",
    "deposit_amount": "청약 예치금(만원)",
    "qual_code": "우선 자격(in|not_in, 예: 기초생활수급자, 한부모가족, 장애인, 국가유공자)",
    "history": "이력(예: 과거 주택 소유, 당첨 이력)",
    "homeless_years": "무주택 기간(년)",
    "income_recognized": "소득인정액",
    "relation": "부모 관계(부|모)",
    "lives_alone": "혼자 사는 노인(Y|N)",
    "lives_with_child": "자녀와 동거(Y|N)",
    "ltc_grade": "장기요양등급(없음|1등급|2등급|3등급|4등급|5등급|인지지원등급)",
    "disability_registered": "장애 등록(Y|N)",
    "basic_pension": "기초연금 수급(Y|N)",
    "livelihood_status": "기초생활보장 수급 종류(생계|의료|주거|교육|차상위|해당없음)",
    "care_wanted": "돌봄 희망(Y|N)",
    "apply_date": "신청일(접수 기간은 apply_date >= 시작일, apply_date <= 마감일 두 조건)",
    "other": "목록 밖 조건(자산, 자동차가액 등). text에 원문 요지",
}


def _field_list() -> str:
    groups = [("본인", FIELDS_SELF), ("부모(subject parent일 때, age·sido·sigungu도 부모 것)", FIELDS_PARENT), ("공통", FIELDS_COMMON)]
    return "\n".join(f"[{name}]\n" + "\n".join(f"- {f}: {FIELD_HELP[f]}" for f in fields) for name, fields in groups)


SYSTEM = f"""너는 한국 공공 주거·복지 공고문의 자격 조건을 규칙 엔진용 조건 JSON으로 옮기는 추출기다.
입력은 공고 하나의 자격 구간이고, 한 줄에 "줄ID<TAB>표시<TAB>본문"이다. 표시가 *인 줄은 조건 신호어가 있는 줄이다.

# 조건표
- 공급 유형·지원 트랙(신혼부부 특별공급, 생애최초 특별공급, 청년, 일반공급 …)마다 조건표(rules의 원소)를 하나씩 낸다. 대상이 하나뿐이면 track "main"인 조건표 하나만 낸다.
- track: 신혼부부 newlywed, 생애최초 first_home, 다자녀 multi_child, 노부모부양 elderly_parent, 신생아 newborn, 청년 youth, 기관추천 institution, 일반공급 general. 그 밖의 트랙은 짧은 영어 소문자(예: student, elderly).
- 여러 트랙에 걸리는 공통 자격은 트랙마다 다시 적는다. 조건표는 따로 판정된다.
- 조건은 원문에 적힌 것만 쓴다. 짐작하거나 상식으로 보태지 않는다. 혜택 내용(대출 한도, 지원 금액, 임대료)은 조건이 아니다.

# 조건 한 줄
- field는 아래 필드 목록의 이름만 쓴다. 맞는 칸이 없으면(자산, 자동차가액 등) field "other", text에 원문 요지를 짧게 쓰고 op·value는 null.
- op: == != <= >= < > in not_in. in·not_in의 value는 문자열 배열.
- 범위는 두 조건이다. "만 19세 이상 39세 이하" → age >= 19, age <= 39.
- as_of: 원문이 "공고일 현재·기준"이라고 하면 "notice_date", "신청일·접수일 현재·기준"이면 "application_date". 그 말이 걸린 조건에만 달고, 없으면 null.
- evidence: 그 조건이 나온 줄 ID를 입력에 적힌 그대로(예: "p7-l23", "l14") 쓴다. 인용문을 쓰지 않는다. 모든 조건과 any_of 묶음에 하나 이상.
- text: other의 요지. 다른 field에서는 null.

# 단위
- 금액은 만원 숫자: "5천만 원" → 5000, "3억 4,500만 원" → 34500, "6,458,330원" → 645.833.
- %는 숫자: "120%" → 120, "100분의 120" → 120.
- 기간은 필드 단위로: 이름이 _months로 끝나는 필드는 개월("2년" → 24, "6개월" → 6), marriage_years·support_years·homeless_years는 년. 나이는 세.
- 날짜는 "YYYY-MM-DD", 달만 있으면 "YYYY-MM".
- 소득 조건에는 income_basis가 반드시 있다: 기준 중위소득 % → median_pct, 도시근로자 (가구당) 월평균소득 % → urban_worker_pct, 연소득 금액 → absolute_annual, 월소득 금액 → absolute_monthly. 소득인정액은 field income_recognized이고 금액이면 recognized, 기준 중위소득 %면 median_pct. 소득이 아닌 조건은 null.
- 누구의 소득인지로 field를 고른다: 본인 income_self, 배우자 income_spouse, 가구·세대 전체 income_household, 부부 합산 income_couple.

# 값
- is_homeless "Y", is_householder "세대주"(또는 "세대원"), marital_status는 미혼|예비부부|신혼|기혼|이혼·사별 중에서, 예·아니오 칸은 "Y"·"N".

# 또는(any_of)
- 둘 중 하나만 맞으면 되는 조건("A 또는 B", 괄호 속 대안, "다만 …인 경우 …")은 any_of 묶음 하나로 쓴다. 묶음의 field·op·value·income_basis·as_of·text는 null이고, any_of는 가지 목록이다. 가지 하나는 AND로 묶인 조건 목록이고 한 단계만 둔다.
- 괄호 밖의 기본 조건도 가지 하나로 넣는다. 그래서 가지는 둘 이상이다.
- 예: "부부합산 연소득 7,500만 원 이하(신혼부부는 본인 또는 배우자 연소득 5,000만 원 이하도 가능)"
  → any_of [[income_couple <= 7500 absolute_annual], [marital_status in [신혼], income_self <= 5000 absolute_annual], [marital_status in [신혼], income_spouse <= 5000 absolute_annual]]
- 대안이 없는 조건은 any_of를 null로 둔다.

# 라벨
*가 붙은 줄 중 어느 조건표의 evidence에도 쓰지 않은 줄은 제목 줄, 서류 줄까지 하나도 빠짐없이 labels에 라벨을 단다. evidence로 쓴 줄과 *가 없는 줄에는 달지 않는다.
- definition: 용어 정의("무주택세대구성원이란 …")
- procedure: 신청·접수·심사 절차, 일정, 방법. 제출서류 이름을 적은 줄도 여기다
- exclusive: 중복 수혜 불가·중복 신청 불가처럼 다른 제도·공급과 함께 받을 수 없다는 줄
- out_of_scope: 이 공고 어느 트랙의 자격도 아닌 내용(다른 공급 안내, 입주 뒤 의무, 계약 조건)
- not_condition: 신호어가 있지만 자격 조건이 아닌 줄(제목 줄, 혜택 내용, 금액 안내)

# 그 밖의 칸
- documents: 제출서류 이름을 원문 글자 그대로. 없으면 [].
- name: 제도 이름. 트랙이 여럿이면 트랙 이름을 붙인다("… 신혼부부 특별공급").
- subject: 사용자 본인 대상이면 self, 사용자의 부모(노인) 대상이면 parent.
- domain: housing(임대주택, 주거급여, 월세 지원) | fund_loan(주택도시기금 대출) | subscription(분양 청약, 특별공급) | elderly(노인 복지) | welfare(그 밖의 복지).
- benefit_type: loan(대출) | rent(임대주택 입주, 임차료 지원) | cash(현금, 바우처) | service(돌봄, 상담 등) | discount(감면, 우선 공급, 분양).
- aliases: 사람들이 검색할 만한 한국어 동의어 3개 이하.

# 필드 목록
{_field_list()}
"""


# --- 출력 스키마(structured outputs: 모든 객체에 additionalProperties false, 모든 칸 required) ---

def _obj(props: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "properties": props, "required": list(props)}


def _enum(values: list[str]) -> dict:
    return {"type": "string", "enum": list(values)}


def _nullable(schema: dict) -> dict:
    return {"anyOf": [schema, {"type": "null"}]}


_STRS = {"type": "array", "items": {"type": "string"}}
_SUB_PROPS = {
    "field": _enum(FIELDS),
    "op": _nullable(_enum(OPS)),
    "value": {"anyOf": [{"type": "number"}, {"type": "string"}, _STRS, {"type": "null"}]},  # 예·아니오는 "Y"|"N"
    "income_basis": _nullable(_enum(INCOME_BASIS)),
    "as_of": _nullable(_enum(AS_OF)),
    "text": _nullable({"type": "string"}),
}
_SUB_COND = _obj(_SUB_PROPS)
_COND = _obj({
    **_SUB_PROPS,
    "field": _nullable(_enum(FIELDS)),
    "evidence": _STRS,
    "any_of": _nullable({"type": "array", "items": {"type": "array", "items": _SUB_COND}}),
})
_RULE = _obj({
    "track": {"type": "string"},
    "name": {"type": "string"},
    "subject": _enum(SUBJECTS),
    "domain": _enum(DOMAINS),
    "benefit_type": _enum(BENEFIT_TYPES),
    "aliases": _STRS,
    "conditions": {"type": "array", "items": _COND},
    "documents": _STRS,
})
OUTPUT_SCHEMA = _obj({
    "rules": {"type": "array", "items": _RULE},
    "labels": {"type": "array", "items": _obj({"line": {"type": "string"}, "label": _enum(LABELS)})},
})


# --- 입력 ---

def _one_line(text: str) -> str:
    return " ".join((text or "").split())


def build_user_content(section_lines: list[dict], *, title: str | None = None) -> str:
    """자격 구간 줄을 "줄ID<TAB>표시<TAB>본문"으로 한 줄씩 적는다."""
    head = [f"공고 제목: {_one_line(title)}"] if title else []
    head.append('자격 구간 줄 목록. 한 줄에 "줄ID<TAB>표시<TAB>본문"이다. 표시 *는 신호어가 있는 줄로, 근거로 쓰거나 라벨을 단다. '
                '표의 행은 칸을 " | "로 이었다.')
    body = [f"{l['id']}\t{'*' if l.get('mark') else ' '}\t{_one_line(l.get('text', ''))}" for l in section_lines]
    return "\n".join([*head, "", *body])


# --- 출력 해석 ---

_SUB_KEYS = ("field", "op", "value", "income_basis", "as_of", "text")
_RULE_KEYS = ("track", "name", "subject", "domain", "benefit_type", "aliases", "documents")


def _bare(line_id) -> str:
    """모델이 doc_id를 붙여 돌려줘도 줄 ID만 남긴다. 줄 ID와 doc_id에는 ":"가 없다."""
    return str(line_id).strip().rsplit(":", 1)[-1]


def _clean(cond: dict, keys: tuple[str, ...]) -> dict:
    out = {}
    for k in keys:
        v = cond.get(k)
        if v is None or v == "":
            continue
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        out[k] = v
    return out


def _evidence(ids, doc_id: str) -> list[str]:
    return list(dict.fromkeys(f"{doc_id}:{_bare(i)}" for i in ids or [] if str(i).strip()))


def parse_output(data: dict, doc_id: str) -> tuple[list[dict], dict[str, str]]:
    """모델 출력 → (조건표 초안 목록, {줄 ID: 라벨}). 초안의 조건은 api.md §1 모양이고 null 칸은 뺀다."""
    drafts = []
    for r in data.get("rules") or []:
        conds = []
        for c in r.get("conditions") or []:
            ev = _evidence(c.get("evidence"), doc_id)
            if c.get("any_of"):
                groups = [[_clean(s, _SUB_KEYS) for s in branch] for branch in c["any_of"] if branch]
                conds.append({"any_of": groups, "evidence": ev})
            else:
                conds.append({**_clean(c, _SUB_KEYS), "evidence": ev})
        draft = {k: r[k] for k in _RULE_KEYS if r.get(k) is not None}
        draft["aliases"] = list(draft.get("aliases") or [])[:3]
        draft["documents"] = list(draft.get("documents") or [])
        draft["conditions"] = conds
        drafts.append(draft)
    labels = {_bare(l["line"]): l["label"] for l in data.get("labels") or [] if l.get("line") and l.get("label")}
    return drafts, labels
