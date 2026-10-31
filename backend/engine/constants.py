"""소득 기준표 시드(`income_standards`). 금액은 월, 만원. 키는 연도 → 가구원 수(1~6).

표에 없는 연도·종류, 7인 이상은 판정에서 "확인 필요"다(SPEC §5.3). 값을 추정해 채우지 않는다.
"""

# 보건복지부 「2026년 기준 중위소득」 보도자료(2025-07-31). 원 단위 → 만원.
MEDIAN_INCOME = {
    2026: {1: 256.4238, 2: 419.9292, 3: 535.9036, 4: 649.4738, 5: 755.6719, 6: 855.5952},
}

# 도시근로자 가구원수별 가구당 월평균소득. 출처 확인 전이라 비워 둔다 → 해당 조건은 확인 필요.
URBAN_WORKER_INCOME: dict[int, dict[int, float]] = {}

STANDARDS = {"median_pct": MEDIAN_INCOME, "urban_worker_pct": URBAN_WORKER_INCOME}
