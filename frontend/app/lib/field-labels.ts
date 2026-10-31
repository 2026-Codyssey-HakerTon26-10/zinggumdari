const labels: Record<string, string> = { // API의 필드 이름을 입력 화면과 같은 쉬운 이름으로 표시해요.
    age: "만 나이", birth_date: "생년월일", gender: "성별", nickname: "닉네임", // 기본 정보의 이름이에요.
    sido: "시도", sigungu: "시군구", marital_status: "혼인 상태", marriage_date: "혼인신고일", marriage_years: "혼인 기간", // 거주 지역과 혼인 정보를 구분해요.
    children_count: "자녀 수", youngest_child_age: "막내 자녀 나이", household_size: "가구원 수", pregnant: "임신 여부", due_month: "출산 예정월", // 가족 상황을 안내해요.
    employment_status: "취업 상태", employment_type: "맞벌이 여부", // 취업과 가구 소득 구성을 구분해요.
    tenure_type: "주거 형태", is_householder: "세대주 여부", is_homeless: "무주택 여부", deposit: "보증금", monthly_rent: "월세", // 주거 관련 확인 항목이에요.
    move_in_date: "전입일", residence_months: "거주 기간", house_price: "주택 가격", homeless_years: "무주택 기간", // 날짜에서 계산하는 기간도 쉬운 이름으로 보여줘요.
    income_self: "본인 월평균소득", income_spouse: "배우자 월평균소득", income_household: "가구 월평균소득", income_couple: "부부 합산소득", // 소득 값을 서로 바꾸어 표현하지 않아요.
    income_recognized: "소득인정액", income_band_median: "기준 중위소득 대비 소득", income_band_urban: "도시근로자 기준 대비 소득", // 소득 기준 종류를 구분하고 확인이 필요함을 유지해요.
    dependents_count: "부양가족 수", supports_parent_65: "만 65세 이상 부모님 부양 여부", support_start_date: "부양 시작일", support_years: "부양 기간", // 부양 정보를 구체적으로 안내해요.
    has_account: "청약통장 가입 여부", joined_date: "청약통장 가입일", subscription_months: "청약통장 가입 기간", payment_count: "납입 횟수", deposit_amount: "청약 예치금", // 청약통장 확인 항목이에요.
    relation: "부모님 구분", lives_alone: "혼자 거주 여부", lives_with_child: "자녀와 동거 여부", // 부모님의 생활 정보를 구분해요.
    ltc_grade: "공식 장기요양등급", disability_registered: "장애 등록 여부", basic_pension: "기초연금 수급 여부", livelihood_status: "수급·차상위 여부", care_wanted: "돌봄 희망 여부", // 공식 확인 결과의 이름만 표시해요.
    qual_code: "우선 자격", qualifications: "우선 자격", history: "관련 이력", apply_date: "신청일", other: "추가 조건", // 직접 확인해야 할 다른 조건도 숨기지 않아요.
}; // 화면 표시만 바꾸고 API 필드와 저장 값은 바꾸지 않아요.
export function fieldLabel(field: string): string { // 서버가 알려준 확인할 항목의 사용자용 이름을 반환해요.
    return Object.prototype.hasOwnProperty.call(labels, field) ? labels[field] : "추가 정보"; // 모르는 내부 키를 그대로 노출하지 않고 확인 필요 항목으로 남겨요.
} // 필드 이름 표시를 마쳐요.
