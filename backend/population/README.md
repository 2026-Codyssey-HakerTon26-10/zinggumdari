비슷한 가구 연결
================

기존 README의 build 명령은 원본 캐시로 인구와 X.npy를 만든다.
`features.query_vector(profile, scale, year=오늘연도)`로 신규 가입자의 빈 칸을 유지해 변환한다.
`knn.neighbors()`는 k번째 동률까지 반환하고 공통으로 아는 칸이 없으면 빈 목록을 반환한다.

`eligibility.build_table(profiles, rules, judge, path)`의 judge 어댑터는
`{rule_id: {verdict: ...}}`를 반환해야 한다. profile 목록은 pool만 넘긴다.
캐시에는 행 user_ids와 열 rule_ids를 함께 저장한다. 로드할 때 순서를 맞춘다.
`knn.recommend()`의 행렬·판정표·태그도 반드시 같은 pool 순서여야 한다.

규칙 엔진 담당자가 실제 judge 반환값을 이 어댑터로 연결해야 한다.
부모 인구가 없는 현 캐시로 부모 제도를 추천하지 않는다.
시도 표기는 프로필과 규칙을 같은 표기로 정규화해서 넘긴다.
`deadline`은 엔진이 원문 조건에서 계산한 ISO 날짜 또는 None이다.
holdout은 평가에만 쓰고 이웃 후보로 넣지 않는다.

부류 이름은 derived.tags 코드에 TAG_LABELS를 적용한다. 인구별 태그는 엔진에서 계산한
derived.tags에 시도 이름을 더해 전달한다. unknown 영문 코드는 화면에 노출하지 않는다.
확인 필요를 이웃의 확정 해당으로 집계하지 않는다. 이 때문에 자산 등 other 조건이 있는
제도는 비율이 낮거나 0일 수 있으며, 해당 의미 변경은 팀 계약 합의 전까지 하지 않는다.
