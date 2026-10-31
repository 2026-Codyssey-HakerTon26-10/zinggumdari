# 데이터 형식 (팀 계약)

> 백엔드, AI, 프론트가 주고받는 데이터 모양이다. 맞춘 뒤에는 팀 합의 없이 바꾸지 않는다. 코드보다 이 문서를 먼저 고친다.
> 아홉 모양이다. ① 조건 JSON(규칙표 한 행) ② 프로필(폼 결과, 나, 부모) ③ 판정 결과 ④ 서류 사전 ⑤ 알림 ⑥ 공고 투입. ①이 핵심이다: AI 공고 읽기의 출력, 손 조건표의 양식, 규칙 엔진의 입력, 공고 투입의 출력이 전부 이 모양이다. ⑦ 비슷한 가구(`data/population/`) ⑧ 검색 결과(`GET /search`) ⑨ 원문과 줄(`GET /notices/…`, `data/notices/*.lines.json`).
> AI 공고 읽기 진입점(스텁을 먼저 커밋해 다른 사람이 붙을 수 있게): `to_lines(doc_id: str, src: str | Path) -> list[Line]`(원문 → 줄, §8. `str`은 언제나 원문 텍스트, 파일은 `Path`로 준다. `llm_ocr=True`는 우리가 넣는 공고 원문만: 스캔 쪽을 네이토로 글자 인식한다), `compile(doc_id: str, lines: list[Line], source: str) -> list[Rule]`(자격 구간 → LLM 1회 → 검증기 → 빠짐 검사), `verify(rule: Rule, lines: list[Line]) -> Rule`(검증기만. 손 조건표에도 돌린다).

## 1. 조건 JSON (`rules/compiled/*.json`, `rules/manual/*.json`)

제도 하나 = 파일 하나. 자동 추출과 손 작성이 같은 모양이어야 규칙 수 비교와 평가가 선다. 아래 숫자와 원문 줄은 모양을 보이는 예시다. 손 조건표의 값은 원문에서만 옮긴다.

```jsonc
{
  "id": "manual:hug-newlywed-jeonse",       // 소스 접두어 + ID. gov24:WII…, local:…, central:…, upload:…
  "source": "manual",                       // gov24 | local | central | manual | upload
  "name": "신혼부부전용 전세자금",
  "org": "주택도시기금",
  "region": null,                           // null = 전국, {"sido": "서울특별시", "sigungu": null} = 시도 전체, {"unknown": true} = 미상. API 메타데이터(시도·시군구, 소관기관)에서 채우고 없으면 sido 조건에서 계산한다. LLM이 쓰지 않는다. 엔진은 대상자(나 또는 부모님)의 `sido`·`sigungu`와 비교해(시도 이름은 `search.corpus.short_sido`로 맞춤) 다르면 탈락, 모르면 질문, 미상이면 확인 필요로 카드 조건 줄 끝에 "거주지 …" 줄을 단다
  "domain": "fund_loan",                    // housing(임대, 주거급여, 월세) | fund_loan(기금 대출은 항상 이것) | subscription(청약) | elderly | welfare
  "subject": "self",                        // self | parent, 어느 대상자의 프로필에 매칭하나
  "benefit_type": "loan",                   // loan | rent | cash | service | discount. 검색 필터 전용, 판정에 쓰지 않는다
  "aliases": ["신혼 전세대출", "신혼부부 버팀목"],   // 검색어 확장 전용. LLM이 뽑아도 검증하지 않는다
  "same_as": ["gov24:WII…"],                // 손 조건표만. 같은 제도의 API 서비스 ID. 그 서비스의 AI 조건표는 판정·검색·알림에 쓰지 않는다(평가에는 쓴다)
  "conditions": [                           // 규칙 엔진은 이 배열만 본다. 줄끼리는 AND
    {"field": "marriage_years", "op": "<=", "value": 7, "as_of": "application_date",
     "quote": "…혼인기간 7년 이내…", "evidence": ["nhuf-newlywed-jeonse:l14"], "status": "reviewed"},
    {"any_of": [                            // OR. 가지 하나는 AND 묶음, 한 단계만. 예: 결혼 페널티 해소(Background §2.3)
       [{"field": "income_couple", "op": "<=", "value": 7500, "income_basis": "absolute_annual"}],
       [{"field": "marital_status", "op": "in", "value": ["신혼", "기혼"]}, {"field": "income_self",   "op": "<=", "value": 5000, "income_basis": "absolute_annual"}],
       [{"field": "marital_status", "op": "in", "value": ["신혼", "기혼"]}, {"field": "income_spouse", "op": "<=", "value": 5000, "income_basis": "absolute_annual"}]
     ], "quote": "…", "evidence": ["nhuf-newlywed-jeonse:l18", "nhuf-newlywed-jeonse:l19"], "status": "reviewed"},
    {"field": "is_homeless",    "op": "==", "value": "Y",      "quote": "무주택 세대주", "evidence": ["nhuf-newlywed-jeonse:l15"], "status": "reviewed"},
    {"field": "is_householder", "op": "==", "value": "세대주", "quote": "무주택 세대주", "evidence": ["nhuf-newlywed-jeonse:l15"], "status": "reviewed"},
    {"field": "subscription_months", "op": ">=", "value": 6, "as_of": "application_date", "quote": "…", "evidence": ["nhuf-newlywed-jeonse:l16"], "status": "reviewed"},
                                            // 원문 확인 전 예시. 원문에 없으면 지운다. 해둘 일 "청약통장 가입"은 이 조건에서 계산된다
    {"field": "other", "text": "순자산 기준 이하", "quote": "…", "evidence": ["nhuf-newlywed-jeonse:l21"], "status": "reviewed"}
                                            // 시트에 칸이 없는 조건. 거부하지 않고 판정에서 항상 확인 필요
  ],
  "exclusive_with": ["manual:hug-buttimok-youth"],   // 손 조건표만. 엔진은 1차 판정 뒤 "둘 중 하나"로 표시만
  "apply_window": null,                     // 손 조건표만, 선택. 예: 기초연금 {"anchor": "age65", "offset_months": -1, "evidence": ["…"]}, 원문 "생일이 속한 달의 1개월 전부터 신청"
  "benefit_text": "…",                      // 원문 그대로
  "apply_text": "…",
  "documents": ["혼인관계증명서", "임대차계약서"],       // 원문 문자열. AI 조건표는 원문 줄에 그대로 있는 이름만 남는다. 사전 매핑은 오프라인
  "documents_official": ["주민등록등본"],              // gov24 공무원확인구비서류 → who_provides: official
  "detail_url": "https://nhuf.molit.go.kr/…",         // 카드에 반드시 표시. 지자체 건은 복지로 검색 링크 폴백
  "updated": "2026-10-31",                  // 기준일, 카드에 반드시 표시
  "review": {"status": "reviewed", "by": "C", "at": "2026-10-31"},   // reviewed | unreviewed. 손 조건표는 reviewed만. AI 조건표는 사람이 조건표 전체를 확인하기 전까지 unreviewed
  "compiled": null                          // AI 조건표만. 아래 예시
}
```

AI 조건표에는 조건마다 검사 결과가 붙고, 조건표에 빠짐 검사 결과와 기록이 붙는다.

```jsonc
{
  "id": "upload:lh-2026-11-mapo:newlywed", "source": "upload", "review": {"status": "unreviewed"},
  "conditions": [
    {"field": "subscription_months", "op": ">=", "value": 6, "as_of": "notice_date", "evidence": ["lh-2026-11-mapo:p7-l23"],
     "status": "auto_verified", "checks": {"schema": "ok", "evidence": "ok", "value": "ok", "comparator": "ok", "unit": "ok", "keyword": "ok", "pair": "ok", "layer": "ok"}},
    {"field": "income_couple", "op": "<=", "value": 120, "income_basis": "urban_worker_pct", "evidence": ["lh-2026-11-mapo:p8-l4"],
     "status": "needs_review", "checks": {"schema": "ok", "evidence": "ok", "value": "ok", "comparator": "fail:no_comparator", "unit": "ok", "keyword": "ok", "pair": "ok", "layer": "ok"}},
    {"field": "other", "text": "원문 조건 미반영", "reason": "unaccounted", "evidence": ["lh-2026-11-mapo:p8-l9"], "status": "needs_review"}
                                            // 빠짐 검사에서 남은 줄. 판정에서 항상 확인 필요
    // 글자를 읽지 못한 쪽이 있으면: {"field": "other", "text": "읽지 못한 쪽이 있어 …", "reason": "unread_pages", "pages": [3], "evidence": [], "status": "needs_review"}
  ],
  "exclusive_evidence": ["lh-2026-11-mapo:p9-l2"],   // LLM이 exclusive로 답한 줄. 카드에 "중복 불가 조건이 있어요"로 표시만
  "coverage": {"marked": 21, "used": 15, "labeled": {"definition": 2, "procedure": 1, "exclusive": 1, "out_of_scope": 1, "not_condition": 0}, "unaccounted": 1},
  "compiled": {"model": "claude-opus-4-8", "prompt": "v1", "doc_sha256": "…", "raw": "rules/compiled/_raw/lh-2026-11-mapo.json", "at": "2026-10-31T21:10"}
}
```

조건 한 줄의 키

| 키 | 뜻 |
|---|---|
| `field` | 아래 통제 어휘. `other`는 어휘 밖 조건이다. `text`에 원문 요지를 쓰고, 판정에서 항상 확인 필요다 |
| `op` | `==` `!=` `<=` `>=` `<` `>` `in` `not_in` |
| `value` | 금액은 만원, 기간은 필드의 단위(개월, 년), 날짜는 `YYYY-MM-DD`, 소득 %는 숫자 |
| `income_basis` | 소득 조건에 필수(시트의 `standard`). `median_pct`(시트 "기준중위소득"), `urban_worker_pct`(시트 "도시근로자"), `absolute_annual`, `absolute_monthly`, `recognized`(소득인정액). 뒤의 셋은 시트 "없음"에 해당한다. 기준표가 없는 종류나 연도는 확인 필요 |
| `any_of` | OR. 가지 하나는 AND 묶음이고 한 단계만 둔다. `evidence`, `status`, `quote`는 묶음에 단다 |
| `as_of` | 기준일. `notice_date`(공고일 현재), `application_date`(신청일·접수일 현재 또는 기준). 원문에 없으면 뺀다. 판정은 오늘(`?today=`)로 하고, 기준일은 카드와 해둘 일 문구에 쓴다 |
| `evidence` | 근거 줄 ID 목록. `{doc_id}:{줄 ID}`(§8). 모든 조건에 필수. 읽지 못한 쪽을 알리는 조건(`reason: "unread_pages"`)만 비고 `pages`에 쪽 번호가 있다 |
| `quote` | 손 조건표만. 사람이 쓴 원문 문장이다. `python -m backend.compiler.resolve_manual`이 `evidence`로 바꾸고, 못 찾으면 실패한다 |
| `status` | `reviewed`(사람이 쓰거나 확인), `auto_verified`(AI, 검사 전부 통과), `needs_review`(AI, 검사 하나라도 실패). 확정 판정에는 앞의 둘만 쓴다 |
| `checks` | AI 조건만. 검사(`schema`, `evidence`, `value`, `comparator`, `unit`, `keyword`, `pair`, `layer`)별 `ok`, `na`(해당 없음), `fail:사유`(SPEC §9.3) |
| `note` | 사람용 메모. 엔진은 읽지 않는다. 판정을 바꿔야 하는 말은 `other` 조건으로 쓴다 |

`confidence`, `votes`, `chunk_id`, `page`, `bbox`, `source_doc`은 조건에 쓰지 않는다. 쪽과 좌표는 근거 줄에 있다(§8).

`field` 통제 어휘. 값은 팀 시트 `DB필드_` 탭의 필드명이다(`policy_requirements.field`가 "위 필드명 중 하나"). 어휘 밖 필드는 pydantic이 거부한다. 거부된 조건은 조용히 빠지므로, 시트에 칸이 없는 조건은 처음부터 `other`로 쓴다. 어휘를 늘리려면 시트와 이 문서를 같이 고친다. (계산)은 직접 받지 않고 계산하는 값이다.

| 대상 | 필드 |
|---|---|
| 나 ① | `age`(계산, `birth_year`에서. 출생연도만 있어 만 나이는 두 값 중 하나다. 경계에 걸리면 확인 필요), `gender`, `sido`, `sigungu`, `marital_status`(미혼\|예비부부\|신혼\|기혼\|이혼·사별), `marriage_years`(계산, `marriage_date`에서. 혼인신고 전이면 혼인 기간 조건은 탈락), `pregnant`, `due_month`, `children_count`, `youngest_child_age`, `household_size`, `employment_status`(재학\|구직\|재직\|자영업\|육아휴직\|기타) |
| 나 ② | `tenure_type`(자가\|전세\|월세\|보증부월세\|무상거주), `is_householder`(세대주\|세대원), `is_homeless`, `deposit`, `monthly_rent`, `residence_months`(계산, `move_in_date`에서), `house_price`, `employment_type`(맞벌이\|외벌이\|해당없음), `income_self`, `income_spouse`, `income_household`, `income_couple`(계산. 미혼·이혼·사별이면 `income_self`, 예비부부·신혼·기혼이면 `income_self + income_spouse`이고 하나라도 모르면 비어 있다. 부부합산 조건에 쓰고 `income_household`로 대신하지 않는다), `income_band_median`(계산), `income_band_urban`(계산), `dependents_count`, `supports_parent_65`, `support_years`(계산, `support_start_date`에서), `has_account`, `subscription_months`(계산, `joined_date`에서), `payment_count`, `deposit_amount` |
| 나 ③ | `qual_code`(`in`/`not_in`, 시트 `DB코드표_자격코드`), `history`(이력 종류와 날짜, 시트 `DB코드표_이력종류`. 예: `homeless_years`(계산, `주택_처분` 날짜에서)), `income_recognized`(소득인정액, 상수 없음, 항상 확인 필요). 자산·자동차가액은 시트에 칸이 없어 `other`로 쓰고 항상 확인 필요 |
| 부모님 | `relation`(부\|모), `age`(계산), `sido`, `sigungu`, `lives_alone`, `lives_with_child`, `ltc_grade`(없음\|1~5등급\|인지지원등급), `disability_registered`, `basic_pension`, `livelihood_status`(생계\|의료\|주거\|교육\|차상위\|해당없음), `care_wanted` |
| 공통 | `apply_date`(계산, 오늘. `?today=`로 바꾼다. 접수 기간은 `apply_date >=` 시작일과 `apply_date <=` 마감일 두 조건으로 쓴다), `other`(어휘 밖 조건) |

금액은 전부 만원이다(시트 기준). 조건 JSON의 키는 DB의 `policy_requirements` 열과 이렇게 대응한다: `field` = `field`, `op` = `operator`, `value` = `value`, `income_basis` = `standard`. 나머지 키(`any_of`의 묶음·가지 번호, `as_of`, `evidence`, `status`, `checks`, `text`)는 시트 예시보다 우리가 더 붙이는 열이다.

소득 %는 저장값이 아니라 판정할 때 `income_standards`(연도별)로 계산한다. 공고 원문의 세부 기준값(소득 %, 가격 상한, 부양 기간)은 조건의 `value`로 들어가고 DB에서는 `policy_requirements` 한 줄이 된다.

### 조건표에 쓰지 않고 계산하는 것

해둘 일, 열리고 닫히는 날짜, 단계 태그는 조건에서 계산한다. 따로 쓰면 검증 밖에 놓이고 조건과 어긋난다. 계산한 값은 조건의 `evidence`와 `as_of`를 물려받는다. `clock`, `prerequisites`, `stage_tags`, `events`, `deadline`은 조건표 키가 아니고, 판정 결과(§3)와 검색 결과(§7)에만 계산해서 싣는다.

- 시간에 따라 커지는 칸: `age`, `marriage_years`, `residence_months`, `subscription_months`, `support_years`, `homeless_years`, `youngest_child_age`, `apply_date`. 이 칸의 `>=`·`>` 조건에서 탈락이면 시간이 지나면 열린다(`opens_later`, 재료 날짜가 있으면 그 날짜). `<=`·`<` 조건에서 통과면 언젠가 닫힌다(`closes_at`).
- 해둘 일(카드 `prerequisites`, 타임라인 `todo`): 아래 칸에 걸린 조건에서 나온다.

| 조건의 칸 | `action` | 해둘 일 |
|---|---|---|
| `has_account`, `subscription_months`, `payment_count`, `deposit_amount` | `subscription_account` | 청약통장 가입·납입 |
| `sido`, `sigungu`, `residence_months` | `move_in` | 전입신고 |
| `marital_status`, `marriage_years` | `marriage_registration` | 혼인신고(단계 넘기기로 보여준다) |
| 부모 `ltc_grade` | `ltc_grade_apply` | 장기요양등급 신청 |

- 단계 태그(`stage_tags`): `age` 상한이 39 이하면 `youth`, `marital_status`에 예비부부가 있으면 `marriage_planned`, `marriage_years` 조건이 있거나 `marital_status`에 신혼이 있으면 `newlywed`, `children_count` 조건의 값이 1이거나 `youngest_child_age`·`pregnant`·`due_month` 조건이 있으면 `child`, `children_count` 조건의 값이 2 이상이면 `multi_child`, `subject`가 `parent`면 `parent`. `any_of` 가지 안의 조건도 본다.

## 2. 프로필 (폼 3단계)

정본은 팀 시트 `복지추천_필드스키마_3단계.xlsx`(볼트 프로젝트 폴더)다. `DB필드_①가입`, `DB필드_②알림설정`, `DB필드_③공고별확인` 탭이 칸, 타입, 필수, 민감정보, KNN 사용 여부를 정한다. 이 절은 API 모양과 시트에 없는 칸만 적는다. 시트와 다르면 시트를 따른다.

| 단계 | 언제 받나 | 테이블 (시트) | 비슷한 사용자 피처 |
|---|---|---|---|
| ① 가입 | 처음 가입할 때. 추천에 꼭 필요한 최소 정보 | `users`: 닉네임(실명 아님), 성별, 출생연도, 시도·시군구, 혼인 상태, 혼인신고일, 임신·출산 예정월(민감), 자녀 수, 막내 나이, 가구원 수, 취업 상태 | `KNN 사용` = Y인 칸(시군구는 빼고 시도만) |
| ② 알림 설정 | "맞춤 공고 받아보기"를 켤 때 | `user_housing`(점유 형태, 세대주, 무주택, 보증금·월세, 전입일, 주택 가격), `user_income`(맞벌이, 본인·배우자·가구 월소득(민감), 부양가족, 노부모 부양), `user_subscription`(통장, 가입일, 납입 횟수, 예치금), `user_alert`(관심 분야, 알림 방법) | `KNN 사용` = Y인 칸 |
| ③ 공고별 확인 | 특정 공고를 볼 때. 그 공고에 필요한데 비어 있는 칸만 | `user_qualifications`(자격 코드, 대상, 확인 방법, 한 자격 한 줄), `user_history`(이력 종류, 날짜, 한 이력 한 줄), `parents`(부·모 각각 한 줄) | 아니오 |

원칙 (시트 `00_안내`)

- 소득은 원래 숫자(월, 만원)를 저장한다. `income_band_median`, `income_band_urban`은 저장하지 않고 판정할 때 연도별 기준표(`income_standards`)와 가구원 수로 계산한다.
- 우선자격과 이력은 칸을 늘리지 않고 한 줄씩 저장한다. 코드 목록은 `DB코드표_자격코드`, `DB코드표_이력종류`.
- 민감정보(소득, 임신·출산, 장애, 수급, 장기요양등급, 일부 자격 코드)는 별도 동의 + 최소 수집이다. 동의가 없으면 그 칸은 비고, 그 칸에 걸린 조건은 "확인 필요"가 된다.
- 비슷한 사용자 피처는 ①② 칸 중 `KNN 사용` = Y인 것만, 원핫 + 0~1 정규화(`KNN용_2단계`, 열 대응은 `KNN용_피처사전`). ③ 칸은 대부분 비어 있어 거리 계산을 망치므로 뺀다. 소득 구간(%)은 규칙 판정에만 쓴다.
- 공고 원문의 세부 기준값(소득 %, 가격 상한, 부양 기간)은 `policy_requirements`에 들어간다.
- 더미데이터는 시연 공고 20개(손 15 + AI 추출 5)가 실제로 쓰는 칸부터 채운다.
- 시트의 상황 문장 칸은 MVP에서 받지 않는다. 입력은 폼이고, 사용자 입력은 LLM에 보내지 않는다(SPEC §1.3).

```jsonc
{
  "user_id": "U7f3a…",                      // 무작위. 실명·연락처 없음 
  "stages_done": ["signup", "alerts"],
  "consents": {"sensitive": true, "parent": true},
  "self": {
    // ① users
    "nickname": "지원", "gender": "여", "birth_year": 1999, "sido": "서울", "sigungu": "마포구",
    "marital_status": "예비부부", "marriage_date": null, "pregnant": "N", "due_month": null,
    "children_count": 0, "youngest_child_age": null, "household_size": 1, "employment_status": "재직",
    // ② user_housing, user_income, user_subscription, user_alert
    "tenure_type": "월세", "is_householder": "세대주", "is_homeless": "Y", "deposit": 1000, "monthly_rent": 55, "move_in_date": "2024-03-01",
    "employment_type": "해당없음", "income_self": 270, "income_spouse": null, "income_household": 270,   // 만원. null = 모름
    "dependents_count": 0, "supports_parent_65": "N",
    "has_account": "Y", "joined_date": "2021-03-01", "payment_count": null, "deposit_amount": null,
    "alert_categories": ["주거", "임신출산"], "alert_channel": "이메일", "email": "…",   // 알림 수신 주소. 계정용 이메일은 별도 인증 테이블에 저장하며 알림 수신은 별도 선택
    // ③ 물어본 것만
    "qualifications": [{"qual_code": "청년", "target": "본인", "verified": "자기신고"}],
    "history": []
  },
  "parents": [                              // 탭을 안 열면 []. 부·모 각각 한 줄
    {"relation": "모", "birth_year": 1966, "sido": "경기", "sigungu": "고양시", "lives_alone": "Y", "lives_with_child": "N",
     "ltc_grade": "없음", "disability_registered": "N", "basic_pension": "N", "livelihood_status": "해당없음", "care_wanted": "Y"}
  ],
  "derived": {"age": [26, 27], "income_couple": null, "tags": ["youth", "marriage_planned", "homeless"], "income_band_median": null, "income_band_urban": null}   // 서버 계산, 저장 안 함. 만 나이는 출생연도만 있어 두 값. income_couple은 예비부부라 배우자 소득을 알아야 나온다. 태그는 여러 개
}
```

시트에 칸이 없어서 생기는 한계 (시트를 늘리지 않고 이렇게 처리한다)

| 없는 것 | 처리 |
|---|---|
| 예정 사건의 날짜(혼인신고 예정일, 둘째 시점 등) | 타임라인은 날짜 대신 단계로 넘긴다. "다음 단계로 가면 프로필이 이렇게 바뀐다"고 가정하고 다시 판정한다. 날짜는 시트의 날짜 칸(`marriage_date`, `due_month`, `birth_year`, `joined_date`, `move_in_date`)에서 계산되는 것만 쓴다 |
| 부모 출생월 | 기초연금은 만 65세가 되는 해까지만 알려주고, 시작 달은 "생일이 속한 달 1개월 전부터"라는 원문 문장으로 안내한다 |
| 부모 퇴직, 수술 예정, 소득, 주택 | 부모 사건은 65세 도달과 장기요양등급 신청(돌봄 희망 + 등급 없음)만 쓴다. 소득·주택 조건은 확인 필요 |
| 자산, 자동차가액 | 그런 조건은 항상 확인 필요 |
| 이메일 주소 | 계정용 이메일은 가입 필수이며 인증 테이블에 둔다. 알림 주소·수신 동의는 별도로 관리한다 |

DB 테이블은 시트 그대로다: `users`, `user_housing`, `user_income`, `user_subscription`, `user_alert`, `user_qualifications`, `user_history`, `parents`, `policy_requirements`, 여기에 `income_standards`(연도 × 기준 × 가구원 수 → 금액)를 더한다. API 응답은 `user_id`로 합친 모양이다.

엔드포인트: `POST /profiles`(① 저장, `user_id` 반환), `PATCH /profiles/{id}`(② 또는 ③에서 받은 칸 추가), `GET /profiles/{id}`, `DELETE /profiles/{id}`(프로필, 알림, 업로드 규칙 전부 삭제). 시연 프리셋: `GET /profiles/presets`(`[{"id": "jiwon", "label", "virtual": true}]`), `POST /profiles/presets/{id}`(SPEC §2의 가상 페르소나로 새 프로필을 만들고 `user_id` 반환. 기존 프로필은 덮어쓰지 않는다).

## 3. 판정 결과 (`POST /judge` 응답)

```jsonc
{
  "user_id": "U7f3a…",
  "ask": {"subject": "self", "field": "marriage_date", "question": "혼인신고를 하셨나요? 했다면 언제인가요?",
          "options": [{"label": "안 함", "value": null, "set": {"marital_status": "예비부부"}}, {"label": "날짜 입력", "value": "date"}],
          "why": "후보 6개 중 4개가 이 칸으로 갈린다"},   // null = 질문 없음
  "cards": [
    {
      "rule_id": "manual:hug-newlywed-jeonse", "subject": "self", "name": "신혼부부전용 전세자금", "domain": "fund_loan",   // 예시 프로필: 신혼인데 혼인신고일과 소득을 아직 안 적었다. review는 카드에 status 문자열만
      "verdict": "needs_check",             // eligible | needs_check | ineligible | opens_later(확정 탈락이 전부 시간이 지나거나 해둘 일을 하면 풀린다. 예: 64세의 age >= 65, 부모 장기요양등급 "없음"의 ltc_grade in [등급], 청약통장 없음)
      "verdict_why": null,                  // "ai_unreviewed" = 검수 전 AI 조건표가 모두 통과했다 → "AI가 읽은 조건은 모두 맞아요. 원문을 확인하고 신청하세요". "next_step" = 지금은 아니고 다음 단계(혼인신고·출산)로 가면 열린다(verdict opens_later). "rule_error" = 조건표가 깨져 판정하지 못했다(needs_check)
      "ai_extracted": false,                // review.status != reviewed → true → 배지
      "conditions": [                       // read_as = 조건을 템플릿으로 쓴 문장(우리가 읽은 조건), evidence = 근거 줄(쪽, 좌표, 텍스트)
        {"read_as": "혼인 7년 이내(신청일 기준)", "grade": "질문", "ok": null, "ask": "marriage_date", "status": "reviewed",
         "evidence": [{"id": "nhuf-newlywed-jeonse:l14", "page": null, "bbox": null, "text": "…"}]},
        {"read_as": "부부합산 연소득 7,500만 원 이하, 또는 (신혼·기혼) 본인이나 배우자 연소득 5,000만 원 이하", "grade": "질문", "ok": null, "ask": "income_self", "status": "reviewed",
         "evidence": [{"id": "nhuf-newlywed-jeonse:l18", "page": null, "bbox": null, "text": "…"}]},
        {"read_as": "순자산 기준 이하", "grade": "확인 필요", "ok": null, "why": "시트에 칸이 없는 조건", "status": "reviewed",
         "evidence": [{"id": "nhuf-newlywed-jeonse:l21", "page": null, "bbox": null, "text": "…"}]}
        // AI 조건은 "checks"가 같이 온다. 빠짐 검사에서 남은 줄은 {"read_as": "원문 조건 미반영", "grade": "확인 필요", "why": "AI가 조건으로 읽지 못한 원문 줄", …}
      ],
      "exclusive_with": [{"rule_id": "manual:hug-buttimok-youth", "name": "청년전용 버팀목", "both_eligible": false}],   // AI 조건표는 "exclusive_evidence"(원문 줄)만 표시
      "opens_at":  {"step": "newlywed"},                                       // 다음 단계로 가면 열린다 (날짜 없음). 그 밖에 {"field", "when"|"year"}(시간이 지나면), {"action": "ltc_grade_apply"}(해둘 일을 하면)
      "closes_at": {"field": "marriage_years", "from": "marriage_date", "plus_years": 7, "when": null},   // 통과 중인 <= 조건에서 계산. 혼인신고일이 생기면 날짜가 나온다
      "apply_from": null,                   // 손 조건표의 apply_window에서
      "prerequisites": [{"action": "subscription_account", "min_months": 6, "have_months": 67, "status": "met", "evidence": ["nhuf-newlywed-jeonse:l16"]}],   // subscription_months >= 6 조건에서 계산(joined_date 기준). 원문 확인 전 예시
      "documents": [                        // 서류 사전 매핑 결과 
        {"name": "혼인관계증명서", "doc_id": "family_marriage_cert", "issuer": "대법원 전자가족관계등록시스템 / 주민센터", "online": "https://efamily.scourt.go.kr", "fee": "온라인 무료", "who_provides": "applicant", "status": "found"},
        {"name": "임대차계약서", "doc_id": null, "who_provides": "applicant", "status": "self_held"},
        {"name": "주민등록등본", "doc_id": "resident_register", "who_provides": "official", "status": "found"},
        {"name": "○○확인서", "doc_id": null, "status": "unknown"}     // → "발급처 확인 필요"
      ],
      "explain": "…",                       // 템플릿 문장 + 근거 줄
      "detail_url": "…", "updated": "2026-10-31", "review": "reviewed"
    }
  ],
  "timeline": {                             // 단계 넘기기. 예정 날짜는 받지 않는다(시트에 없음). 다음 단계로 가면 프로필이 이렇게 바뀐다고 가정하고 다시 판정한다. opens·closes·todo는 조건에서 계산한다(§1)
    "self": [
      {"step": "newlywed",    "assume": {"marital_status": "신혼", "marriage_date": "today"}, "opens": ["manual:hug-newlywed-jeonse"], "closes": ["manual:hug-buttimok-youth"],
       "todo": [{"action": "subscription_account", "min_months": 6, "have_months": 67, "status": "met", "evidence": ["nhuf-newlywed-jeonse:l16"]}]},
      {"step": "child",       "assume": {"children_count": 1, "youngest_child_age": 0}, "opens": ["manual:hug-newborn-buttimok"], "closes": [], "todo": []},
      {"step": "multi_child", "assume": {"children_count": 2}, "opens": ["…"], "closes": [], "todo": []}
    ],
    "parent": [
      {"step": "ltc_apply", "now": true, "why": "돌봄 희망 + 장기요양등급 없음", "opens": ["manual:ltc-insurance"], "todo": [{"action": "ltc_grade_apply", "evidence": ["…"]}]},
      {"step": "age65", "relation": "모", "age": 65, "year": 2031, "opens": ["manual:basic-pension"], "apply_from": "2031년 생일이 속한 달의 1개월 전부터(생일 달은 출생연도만 있어 확인 필요)"}   // 부모 한 명씩, 조건의 나이별로(age70이면 70세 되는 해). apply_from은 65세 apply_window만
    ],
    "dated": [                              // 날짜가 계산되는 것만. 시트의 날짜 칸에서
      {"what": "청년 나이 상한(만 34세) 지남", "year": 2034, "from": "birth_year", "note": "만 35세 생일부터 해당 안 됨"},   // 카드 closes_at의 year와 같은 해
      {"what": "어머니 만 65세", "year": 2031, "from": "parents.birth_year"}
    ]
  },
  "similar": {                            // 비슷한 가구 알림 . 맞춤 추천과 섞지 않는다
    "method": "knn", "features": "sheet_minmax", "k": 50, "neighbors": 50,   // 시트 KNN용_2단계 그대로. 비교판은 "rule_bins"(비슷한 가구 정확도에서 비교). k번째와 거리가 같은 이웃까지 넣으면 50보다 클 수 있다
    "basis": "가상 인구 9,000명(가정 분포)",
    "label": "주로 청년·예비부부·무주택·서울 가구", "label_share": 0.62,   // 이웃의 태그 조합 중 가장 많은 것과 그 비율
    "known_fields": 9,
    "assignment": "full",                 // full | reference(아는 칸 3개 미만 또는 label_share < 0.5 → "참고")
    "items": [{"rule_id": "manual:seoul-youth-deposit", "name": "서울 청년 임차보증금 이자지원", "subject": "self", "benefit_type": "loan",
               "prevalence": 0.72,           // 이웃 가구 중 해당되는 비율
               "my_verdict": "needs_check",  // needs_check만 올린다. 낡기 쉬운 칸 때문에 ineligible이면 items가 아니라 "정보가 바뀌었나요?"로
               "blocking_fields": ["income_household"]}]   // 이 칸을 알려주면 판정된다. 적을수록 앞
  },
  "disclaimer": "참고용 모의 판정, 실제 자격은 접수 기관의 심사로 결정됩니다"
}
```

조건표 수와 평가는 응답에 싣지 않고 `GET /stats/coverage`로 낸다. 평가는 `eval/results.json`을 읽는다(SPEC §17). 비율보다 개수와 n을 싣는다.

```jsonc
{
  "manual": 15,
  "compiled": {"rules": …, "conditions": …, "auto_verified": …, "needs_review": …, "unaccounted_lines": …},
  "eval": {
    "split": {"dev": 5, "test": 10},
    "precision_auto_verified": {"test": {"correct": …, "n": …}, "sample": {"correct": …, "n": 50}},   // 시험용 10개, 대량 추출 무작위 표본
    "missed": …,                                              // 정답 조건 중 AI 조건표에 없고 미반영 줄로도 안 뜬 수. 목표 0
    "agreement": {"households": 9000, "rules": 10, "same": …, "danger": …, "missed_benefit": …},   // danger = AI eligible·정답 ineligible, missed_benefit = AI ineligible·정답은 그 밖
    "verifier": {"llm_wrong": …, "caught": …, "llm_right": …, "flagged_right": …}             // LLM 원출력 기준. 검사별 내역은 results.json에
  }
}
```

## 4. 서류 사전 (`docs/documents.json`)

```jsonc
[
  {"doc_id": "resident_register", "name": "주민등록등본", "aliases": ["주민등록표 등본", "등본"],
   "issuer": "정부24 / 주민센터", "online": "https://www.gov.kr", "offline": "주민센터·무인발급기", "fee": "온라인 무료, 창구 400원", "validity": "통상 3개월",
   "who_provides_default": "official", "verified_from": "정부24 발급 서비스 목록", "updated": "2026-10-31"},
  {"doc_id": "financial_consent", "name": "금융정보등제공동의서", "aliases": ["금융정보제공동의서"], "issuer": "주민센터·국민연금공단 창구 양식", "online": null, "offline": "창구 작성", "fee": "무료", "validity": null, "who_provides_default": "applicant", "verified_from": "복지로 기초연금 안내", "updated": "2026-10-31"}
]
```

매핑 규칙(오프라인, 손 조건표 15 + AI 추출 5를 미리 매핑해 캐시): 조건 JSON `documents[]` 문자열 → `aliases` 정확/부분 일치 → 없으면 `status: "unknown"`("발급처 확인 필요"). LLM 제안은 쓰지 않는다. gov24 `documents_official`에 있으면 `who_provides: official`. 런타임 `/judge`는 캐시만 읽는다. AI 조건표의 서류명은 원문 줄에 그대로 있는 것만 남는다(SPEC §9.3).

## 5. 알림 (`GET /notifications`, 사용자 선택은 로그인 세션)

```jsonc
[
  {"id": "n_01", "kind": "new_rule",   "subject": "self",   "rule_id": "upload:seoul-2026-11-youth", "title": "새 공고: 서울 청년 … AI가 읽은 조건을 확인해 보세요", "created": "2026-10-31T15:02", "read": false},
  {"id": "n_02", "kind": "d_day",      "subject": "self",   "rule_id": "manual:hug-newborn-buttimok", "title": "출산 예정월(2027-03) 전에 신생아 특례 대출 서류를 준비하세요", "due": "2027-02-01", "from": "due_month", "read": false},
  {"id": "n_03", "kind": "closing",    "subject": "self",   "rule_id": "…", "title": "청년전용 버팀목 나이 상한 도달 D-90", "due": "…", "read": true},
  {"id": "n_04", "kind": "apply_open", "subject": "parent", "rule_id": "manual:basic-pension", "title": "어머니가 2031년에 만 65세가 됩니다. 기초연금은 생일이 속한 달 1개월 전부터 신청할 수 있어요", "due": "2031", "read": false},
  {"id": "n_05", "kind": "explore",    "subject": "self",   "rule_id": "manual:seoul-youth-deposit", "title": "비슷한 나이대·상황에서 72%가 해당돼요(가상 인구 기준). 소득을 알려주시면 확인해 드릴게요", "prevalence": 0.72, "neighbors": 50, "blocking_fields": ["income_household"], "basis": "가상 인구(가정 분포)", "read": false}
]
```

알림은 두 단계다. `new_rule`·`d_day`·`closing`·`apply_open`은 확정 알림이다. 확정 알림은 상태가 `reviewed`나 `auto_verified`인 조건으로 계산한 알림이다(새 조건표 재판정 결과, 조건에서 계산한 날짜, 손 조건표의 `apply_window`). `needs_review` 조건으로는 날짜 알림을 만들지 않는다. 검수 전 AI 조건표의 `new_rule`은 "조건을 확인해 보세요"로 쓴다. `ineligible` 제도에는 보내지 않는다. "신청할 수 있어요"는 verdict가 `eligible`인 제도에만 쓴다. `explore`는 비슷한 가구 알림이다. 알림은 앱 알림함에 항상 쌓이고, `alert_channel`이 이메일이면 같은 내용을 이메일로도 보낸다(`backend/notify/`, `emailed_at` 기록). `alert_categories`에 없는 분야는 이메일로 보내지 않는다. 신청 기한이 지난 제도는 올리지 않는다. 내 정보로 `ineligible`인 제도는 "정보가 바뀌었나요?"로만 묻는다.

시연: `POST /trigger/rebuild` (새 규칙 재판정), `?today=2031-01-15` (날짜가 계산되는 알림 재현), `POST /notify/test-email` (시연용 메일 한 통), `PATCH /notifications/{id}/read`.

비슷한 가구: `data/population/users.parquet`(사람 × 칸, 시트 DB샘플 칸 전부 + `split`·`from_text`), `meta.json`(출처, 가정값, 정규화 최소·최대 `scale`, 열 이름), `eligibility.npz`(사람 × 제도 해당 여부), `X.npy`(시트 `KNN용_2단계` 그대로의 입력 행렬, 32열. 신규 가입자도 `scale`로 편다. 빈 칸은 NaN)를 저장한다. 팀이 열어 볼 `더미데이터.xlsx`도 같이 쓴다. 비교판으로 `bins.json`(칸별 기준선, `policy_requirements`에서 생성)을 만든다. 사용자마다 이웃 목록을 `user_neighbors`에 저장하고 프로필이 바뀌면 다시 찾는다. 학습 단계가 없어 신규 가입자도 가입 즉시 계산된다. 생성 `uv run --project backend python -m backend.population.build --n 10000 --holdout 1000 --seed 42`(이웃 후보 9,000, 평가 1,000). 평가 `GET /stats/explore` → `{"k": 50, "precision_at_5": …, "recall_at_5": …, "baseline_popular": …, "baseline_random": …, "baseline_question_only": …, "variant_rule_bins": …}` .

고르는 순서: 이웃에서 제도별 해당 비율 → 빼기(이미 `eligible`, 기한 지남, 다른 시도 지자체 제도, 아는 칸으로 확정 탈락) → 순위(비율, `blocking_fields` 적은 순, 마감 가까운 순) → 문턱(30% 이상, 최대 5, 같은 `benefit_type` 2개까지). 새 공고는 거꾸로: 가상 인구에 한 번 판정 → 사용자별 저장된 이웃으로 비율 → 문턱을 넘고 맞춤 추천에 없는 사용자에게만 `explore`.

## 6. 공고 투입 (`POST /ingest`)

입력: PDF·HWP·HWPX·텍스트 파일 또는 URL (안내문: "개인 서류를 올리지 마세요", 주민번호 패턴 거부. 이미지 스캔 PDF는 서버 안의 tesseract로만 읽고(없으면 거부. 업로드는 네이토로 보내지 않는다), 암호·배포용 HWP와 HWP 3.x는 거부). 출력: §1 조건 JSON(`source: "upload"`, `review.status: "unreviewed"`) + 로그.

```jsonc
{"doc_id": "upload-20261031-01", "lines": 412, "section": {"from": "p6-l1", "to": "p9-l40", "found_by": "heading"}, "marked": 21,
 "llm_calls": 1, "schema_retries": 0, "rules": 2, "conditions": 12, "auto_verified": 9, "needs_review": 3,
 "fails": [{"rule_id": "upload:upload-20261031-01:newlywed", "field": "income_couple", "check": "comparator", "reason": "no_comparator", "evidence": ["upload-20261031-01:p8-l4"]}],
 "unaccounted": ["upload-20261031-01:p8-l9"], "unread_pages": [], "model": "…", "prompt": "v1"}
```

화면은 진행 표시(줄 만들기 → 자격 구간 → 읽기 → 검증 → 합류) 뒤 조건 표를 보여준다: 우리가 읽은 조건(템플릿 문장), 근거 줄, 검사별 ✓/✗, 미반영 줄. 그다음 카드에 합류시키고 `new_rule` 알림을 만든다. 검수 전이라 카드는 `eligible`이 되지 않는다(SPEC §5.2). 시연 PDF 2건은 결과 캐시 + "캐시 재생" 토글.

## 7. 검색 (`GET /search?q=…&tag=…&subject=self|parent`, 개인화 사용자는 로그인 세션)

```jsonc
{
  "q": "신혼 특공",
  "results": [
    {"service_id": "gov24:WII…", "rule_id": "manual:subscription-newlywed", "name": "신혼부부 특별공급", "org": "국토교통부",
     "region": null, "snippet": "…혼인기간 7년 이내…", "stage_tags": ["marriage_planned", "newlywed"],
     "badge": "needs_check",            // eligible(추천) | similar(비슷한 가구) | needs_check | ineligible | no_rule(조건표 없음, 원문 보기만)
     "detail_url": "https://…", "updated": "2026-10-31"},
    {"service_id": "local:…", "rule_id": null, "name": "○○구 신혼부부 주거비 지원", "badge": "no_rule", "stage_tags": ["newlywed"], "detail_url": "…", "updated": "…"}
  ],
  "nudge": {                              // 2단계 . 없으면 null. 자동으로 바꾸지 않는다
    "missing_tag": "marriage_planned",      // 검색 결과에 많고 내 프로필에 없는 생애 단계 태그
    "question": "혹시 결혼 준비 중이거나 신혼이세요? 정보를 바꾸면 맞는 제도를 다시 찾아드릴게요",
    "options": [{"label": "결혼 준비 중", "set": {"marital_status": "예비부부"}}, {"label": "신혼(혼인신고 함)", "set": {"marital_status": "신혼"}}, {"label": "아니요", "set": null}],
    "why": "상위 5개 중 3개가 결혼 준비·신혼 단계 제도"
  }
}
```

태그는 프로필에서 계산하고 여러 개가 동시에 붙는다. `youth`는 나이 묶음(만 19~39세. 실제 나이 조건은 제도마다 규칙이 판정), `marriage_planned`(예비부부), `newlywed`(신혼·기혼, 자녀 없음), `child`(자녀 1), `multi_child`(자녀 2 이상)는 생애 단계, `homeless`는 주거 태그다. 30세 신혼은 `youth`와 `newlywed`를 둘 다 갖는다. 다섯 단계 타임라인은 이야기 순서이고 태그를 하나로 묶지 않는다. 검색어는 서버 로그에 남기지 않는다. 단계 키워드 사전은 `docs/stage_keywords.json`(C). 제도 쪽 `stage_tags`는 조건에서 계산한다(§1).

## 8. 원문과 줄 (`GET /notices/{doc_id}`, `GET /notices/{doc_id}/file`, `data/notices/{doc_id}.lines.json`)

```jsonc
{
  "doc_id": "2026-11-mapo-apt",           // `:`를 쓰지 않는다. API 산문은 gov24-WII…, local-…
  "title": "○○ 아파트 입주자모집공고",
  "source": "applyhome",                  // applyhome(청약홈) | lh(LH 공고) | local(지자체) | upload(사용자 투입) | web(손 조건표의 출처 페이지) | api(공공데이터 산문)
  "kind": "pdf",                          // pdf | hwp | hwpx | text
  "source_url": "https://…",              // 받은 곳
  "fetched_at": "2026-10-31",
  "sha256": "…",                          // 원문이 바뀌면 줄 ID도 바뀔 수 있다. 다르면 조건표를 다시 만든다
  "pages": 48,                            // pdf만
  "text_layer": true,                     // false = 이미지 스캔 쪽이 있다. 그 쪽은 글자 인식으로 줄을 만들었다
  "ocr": null,                            // null | "tesseract" | "llm"(네이토 API)
  "pblanc_no": "2026000123",              // 청약홈 공고번호(있으면). 15098547 응답과 연결
  "section": {"from": "p6-l1", "to": "p9-l40", "found_by": "heading"},   // 자격 구간. 제목을 못 찾으면 {"found_by": "none"}(전체를 썼다)
  "rules": ["applyhome:2026000123:newlywed", "applyhome:2026000123:first_home"],
  "lines": null                           // text·hwp·hwpx면 줄 목록을 싣는다(좌표 없음). pdf는 /file을 그리고 근거 줄 좌표로 칠한다
}
```

줄 목록(`data/notices/{doc_id}.lines.json`, 커밋한다)

```jsonc
[
  {"id": "p7-l23", "page": 7, "bbox": [72.0, 418.5, 310.2, 431.0], "text": "…청약통장 가입 후 6개월이 지난…", "mark": true},   // pdf: pdfplumber 단어를 같은 줄끼리 묶고 상자를 합친다
  {"id": "p8-l6", "page": 8, "bbox": [72.0, 520.1, 520.4, 534.0], "text": "3인 | 7,004,509원 | 120%", "mark": true, "table": "p8-t1"},   // 표 한 행. 칸 사이 " | "
  {"id": "p2-l5", "page": 2, "bbox": null, "text": "…", "mark": true, "src": "ocr"},   // 스캔 쪽의 글자 인식 줄. tesseract면 bbox가 있고 네이토(llm)면 없다. 이 줄을 근거로 한 조건은 needs_review
  {"id": "l14", "page": null, "bbox": null, "text": "…혼인기간 7년 이내…", "mark": true}   // text·hwp·hwpx: 줄바꿈과 항목 기호(○, -, ※) 단위, 문단 단위
]
```

- 근거 ID는 `{doc_id}:{줄 ID}`다.
- `mark`는 조건 신호어가 있는 줄이다(SPEC §9.2). LLM은 표시된 줄마다 근거로 쓰거나 라벨을 단다.
- PDF 보기는 `file`을 pdf.js(react-pdf)로 그리고, 카드 조건의 `evidence[].page`·`bbox`로 해당 줄을 칠한다. 텍스트 원문은 줄 목록을 그리고 근거 줄을 칠한다. 런타임에 텍스트 검색으로 위치를 찾지 않는다.

## 인증·소유권 계약 (구현 전환 요구사항)

기존 예시의 `user_id`는 응답 식별자이며 다른 계정에 접근할 권한을 뜻하지 않는다. 아래 내용은 인증·PostgreSQL 전환 설계이며 기존 서버에 구현되었다는 뜻이 아니다.

| 메서드 | 경로 | 계약 |
|---|---|---|
| POST | `/auth/signup` | 이메일·비밀번호·닉네임·필수 동의로 계정 생성. 비밀번호 확인은 클라이언트 입력 보조이며 저장하지 않는다 |
| POST | `/auth/login` | 이메일·비밀번호 인증 후 HttpOnly·Secure 세션 쿠키 발급 |
| POST | `/auth/logout` | 현재 서버 세션 폐기 및 쿠키 삭제 |
| GET | `/auth/me` | 현재 계정의 비밀정보 없는 식별 정보와 연결된 프로필 ID 반환 |
| DELETE | `/auth/me` | 계정·모든 세션·프로필·알림·사용자 업로드 데이터 삭제 |

- DB는 PostgreSQL이며 기존 추천 테이블에 `auth_accounts`, `auth_sessions`를 추가한다. 계정과 프로필은 외래 키로 연결한다. 비밀번호와 세션 토큰은 해시만 저장한다.
- `POST /profiles`는 세션 계정에 프로필을 연결한다. `GET/PATCH/DELETE /profiles/{id}` 경로는 유지하되 서버에서 세션 계정의 소유 프로필과 ID를 비교한다. 미인증은 401, 타인 또는 존재하지 않는 프로필 요청은 동일한 404 응답을 사용한다.
- `POST /judge`는 세션에서 본인 프로필을 결정한다. 기존 요청의 `user_id`는 생략 가능하며, 전환 중 전달되면 본인 프로필과 일치하는지 검사하고 다르면 403으로 거부한다.
- `GET /search`는 로그인 없이 공고를 검색할 수 있지만 개인화 배지는 반환하지 않는다. 로그인 상태에서는 세션의 프로필만 사용한다. 기존 `user_id` 쿼리가 전달되면 로그인·본인 일치를 확인하며 미인증은 401, 불일치는 403으로 거부한다.
- `GET /notifications`도 세션 소유자의 목록만 반환한다. 기존 `user_id`가 전달되면 본인 일치를 검사하며 다른 계정 선택에 쓰지 않는다. 알림 읽음 API도 해당 알림의 소유권을 확인한다.
- 상태 변경 요청에는 CSRF 방어를 적용하며, 인증 실패 메시지는 계정 존재를 드러내지 않는다. 로그인 반복 요청은 제한한다.
- 계정 이메일 수집은 이메일 알림 수신 동의가 아니다. 소득·건강 등 민감정보 동의도 분리한다. 실제 연결 값과 인증 비밀정보는 문서·로그에 남기지 않는다.
