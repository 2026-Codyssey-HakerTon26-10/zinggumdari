"""프로필 칸 분류. 프로필 저장(동의 확인)과 엔진이 같이 쓴다."""

# 민감정보(SPEC §4.4). 별도 동의가 있을 때만 저장한다.
SENSITIVE = {"income_self", "income_spouse", "income_household", "income_couple", "income_band_median",
             "income_band_urban", "income_recognized", "pregnant", "due_month", "disability_registered",
             "livelihood_status", "ltc_grade", "basic_pension"}
