"""스텁 응답. docs/api.md §2(프로필), §3(판정 결과)의 예시를 그대로 옮겼다.

진짜 엔진·DB가 붙으면 지운다. 모양을 바꾸려면 api.md를 먼저 고친다.
"""

EXAMPLE_PROFILE = {
    "user_id": "U7f3a",
    "stages_done": ["signup", "alerts"],
    "consents": {"sensitive": True, "parent": True},
    "self": {
        # ① users
        "nickname": "지원", "gender": "여", "birth_date": "1999-04-15", "sido": "서울", "sigungu": "마포구",
        "marital_status": "예비부부", "marriage_date": None, "pregnant": "N", "due_month": None,
        "children_count": 0, "youngest_child_age": None, "household_size": 1, "employment_status": "재직",
        # ② user_housing, user_income, user_subscription, user_alert
        "tenure_type": "월세", "is_householder": "세대주", "is_homeless": "Y", "deposit": 1000, "monthly_rent": 55,
        "move_in_date": "2024-03-01",
        "employment_type": "해당없음", "income_self": 270, "income_spouse": None, "income_household": 270,
        "dependents_count": 0, "supports_parent_65": "N",
        "has_account": "Y", "joined_date": "2021-03-01", "payment_count": None, "deposit_amount": None,
        "alert_categories": ["주거", "임신출산"], "alert_channel": "이메일", "email": None,
        # ③ 물어본 것만
        "qualifications": [{"qual_code": "청년", "target": "본인", "verified": "자기신고"}],
        "history": [],
    },
    "parents": [
        {"relation": "모", "birth_date": "1966-07-03", "sido": "경기", "sigungu": "고양시", "lives_alone": "Y",
         "lives_with_child": "N", "ltc_grade": "없음", "disability_registered": "N", "basic_pension": "N",
         "livelihood_status": "해당없음", "care_wanted": "Y"},
    ],
    "derived": {"age": [27], "income_couple": None, "tags": ["youth", "marriage_planned", "homeless"],
                "income_band_median": None, "income_band_urban": None},
}

EXAMPLE_CARD = {
    "rule_id": "manual:hug-newlywed-jeonse", "subject": "self", "name": "신혼부부전용 전세자금", "domain": "fund_loan",
    "verdict": "needs_check",
    "verdict_why": None,
    "ai_extracted": False,
    "conditions": [
        {"read_as": "혼인 7년 이내(신청일 기준)", "grade": "질문", "ok": None, "ask": "marriage_date", "status": "reviewed",
         "evidence": [{"id": "nhuf-newlywed-jeonse:l14", "page": None, "bbox": None, "text": "…"}]},
        {"read_as": "부부합산 연소득 7,500만 원 이하, 또는 (신혼·기혼) 본인이나 배우자 연소득 5,000만 원 이하",
         "grade": "질문", "ok": None, "ask": "income_self", "status": "reviewed",
         "evidence": [{"id": "nhuf-newlywed-jeonse:l18", "page": None, "bbox": None, "text": "…"}]},
        {"read_as": "순자산 기준 이하", "grade": "확인 필요", "ok": None, "why": "시트에 칸이 없는 조건", "status": "reviewed",
         "evidence": [{"id": "nhuf-newlywed-jeonse:l21", "page": None, "bbox": None, "text": "…"}]},
    ],
    "exclusive_with": [{"rule_id": "manual:hug-buttimok-youth", "name": "청년전용 버팀목", "both_eligible": False}],
    "opens_at": {"step": "newlywed"},
    "closes_at": {"field": "marriage_years", "from": "marriage_date", "plus_years": 7, "when": None},
    "apply_from": None,
    "prerequisites": [{"action": "subscription_account", "min_months": 6, "have_months": 67, "status": "met",
                       "evidence": ["nhuf-newlywed-jeonse:l16"]}],
    "documents": [
        {"name": "혼인관계증명서", "doc_id": "family_marriage_cert", "issuer": "대법원 전자가족관계등록시스템 / 주민센터",
         "online": "https://efamily.scourt.go.kr", "fee": "온라인 무료", "who_provides": "applicant", "status": "found"},
        {"name": "임대차계약서", "doc_id": None, "who_provides": "applicant", "status": "self_held"},
        {"name": "주민등록등본", "doc_id": "resident_register", "who_provides": "official", "status": "found"},
        {"name": "○○확인서", "doc_id": None, "status": "unknown"},
    ],
    "explain": "…",
    "detail_url": "…", "updated": "2026-10-31", "review": "reviewed",
}

EXAMPLE_JUDGE = {
    "user_id": "U7f3a",
    "ask": {"subject": "self", "field": "marriage_date", "question": "혼인신고를 하셨나요? 했다면 언제인가요?",
            "options": [{"label": "안 함", "value": None, "set": {"marital_status": "예비부부"}},
                        {"label": "날짜 입력", "value": "date"}],
            "why": "후보 6개 중 4개가 이 칸으로 갈린다"},
    "cards": [EXAMPLE_CARD],
    "timeline": {
        "self": [
            {"step": "newlywed", "assume": {"marital_status": "신혼", "marriage_date": "today"},
             "opens": ["manual:hug-newlywed-jeonse"], "closes": ["manual:hug-buttimok-youth"],
             "todo": [{"action": "subscription_account", "min_months": 6, "have_months": 67, "status": "met",
                       "evidence": ["nhuf-newlywed-jeonse:l16"]}]},
            {"step": "child", "assume": {"children_count": 1, "youngest_child_age": 0},
             "opens": ["manual:hug-newborn-buttimok"], "closes": [], "todo": []},
            {"step": "multi_child", "assume": {"children_count": 2}, "opens": ["…"], "closes": [], "todo": []},
        ],
        "parent": [
            {"step": "ltc_apply", "now": True, "why": "돌봄 희망 + 장기요양등급 없음", "opens": ["manual:ltc-insurance"],
             "todo": [{"action": "ltc_grade_apply", "evidence": ["…"]}]},
            {"step": "age65", "year": 2031, "opens": ["manual:basic-pension"],
             "apply_from": "2031년 6월부터"},
        ],
        "dated": [
            {"what": "청년 나이 상한(만 34세) 지남", "year": 2034, "from": "birth_date", "note": "만 35세 생일부터 해당 안 됨"},
            {"what": "어머니 만 65세", "year": 2031, "from": "parents.birth_date"},
        ],
    },
    "similar": {
        "method": "knn", "features": "sheet_minmax", "k": 50, "neighbors": 50,
        "basis": "가상 인구 9,000명(가정 분포)",
        "label": "주로 청년·예비부부·무주택·서울 가구", "label_share": 0.62,
        "known_fields": 9,
        "assignment": "full",
        "items": [{"rule_id": "manual:seoul-youth-deposit", "name": "서울 청년 임차보증금 이자지원", "subject": "self",
                   "benefit_type": "loan", "prevalence": 0.72, "my_verdict": "needs_check",
                   "blocking_fields": ["income_household"]}],
    },
    "disclaimer": "참고용 모의 판정, 실제 자격은 접수 기관의 심사로 결정됩니다",
}
