"""프로필 칸 분류. 프로필 저장(동의 확인)과 엔진이 같이 쓴다."""

# 민감정보(SPEC §4.4). 별도 동의가 있을 때만 저장한다.
SENSITIVE = {"income_self", "income_spouse", "income_household", "income_couple", "income_band_median",
             "income_band_urban", "income_recognized", "pregnant", "due_month", "disability_registered",
             "livelihood_status", "ltc_grade", "basic_pension"}

# 민감 자격 코드(SPEC §4.4 "일부 자격 코드"). 팀 시트 DB코드표_자격코드의 민감 표시가 들어오기 전까지
# 이 말이 들어간 코드를 민감으로 본다(보수적).
SENSITIVE_QUAL_WORDS = ("수급", "차상위", "의료급여", "장애", "한부모", "임신", "임산", "출산", "난임",
                        "질환", "질병", "치매", "장기요양", "유공", "보훈", "북한이탈", "다문화")


def is_sensitive_qual(code) -> bool:
    return any(w in str(code or "") for w in SENSITIVE_QUAL_WORDS)
