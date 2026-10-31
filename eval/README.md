평가 연결
=========

`uv run --project backend python -m eval.score --input 채점기록.json --split eval/split.json --output eval/results.json`

채점기록의 verdicts는 expected/actual 판정 쌍, extraction은 gold/extracted 조건 배열 쌍이다.
정답 데이터는 평가 담당자가 원문과 동결한 조건표에서 만든다. 예시 숫자로 실제 정답을 만들지 않는다.
score 도구는 지정한 입력 외에는 페르소나 정답이나 시험용 조건표를 읽지 않는다.
판정 일치 평가에서 AI_ELIGIBLE을 허용하는 설정은 규칙 엔진 어댑터에서 명시한다.

`explore.compare`는 pool/holdout이 겹치면 거부하고 원래 필드 단위로 1개·3개·절반을 남긴다.
KNN 20/50/100, 동일 필터를 거친 전체 해당 비율 순위와 무작위를 비교한다.
인기순 기준보다 낮은 시나리오가 있으면 demo_enabled=False다. 이 기준선 이름은 평가에서만 쓰고
추천 카드에서는 선호·인기라는 표현을 쓰지 않는다.

`coverage.create_router(load_rules)`는 main 담당자가 등록한다. 평가 전에는 null을 반환한다.
공개 results.json에 개인별 프로필·정답을 넣지 않는다. silent_omissions는 공고 조건과 근거 줄만 포함한다.
실제 손 조건표·엔진·페르소나가 아직 없어 결과 파일과 정답·표본50 채점은 생성하지 않았다.

수정한 평가 계약
----------------

compare의 기본 결과는 purpose=validation이며 k 선택에만 쓴다. demo_enabled는 None이다.
최종 시험은 분리한 test 행으로 compare(..., fixed_k=선택결과["k"],
validation_ids=선택결과["validation_ids"])를 한 번 호출한다. pool·검증·시험의 ID 중복은 거부한다.
시험 결과에서 k를 다시 선택하지 않는다. 검증 결과를 최종 성능으로 내보내면 실패한다.
추천 콜백은 masked_row 키워드로 가려진 원래 행도 받는다. 시도·개인 판정 필터는 이 행만 보고
계산하며 원래 holdout 프로필을 캡처하면 안 된다. 실제 엔진으로 만든 가상 인구를 별도 분할한다.

독립 시험 결과 dict를 JSON으로 보관한 뒤 공개 결과로 내보내는 명령:
`uv run --project backend python -m eval.explore --input 독립시험결과.json --output eval/explore-results.json`
공개 precision/recall은 동일 크기의 세 가림 시나리오 평균이며 scenarios에 원 지표와 분모를 남긴다.
baseline_question_only와 variant_rule_bins는 아직 미측정이므로 None이다.

채점기록 extraction·verdicts에는 rule_id가 필수이고 verdicts는 user_id도 필요하다.
split의 dev/test는 제도 ID 목록이다. dev·미지정 제도는 시험 채점에서 거부한다.
sample50은 correct 불리언을 가진 정확히 50개 채점 기록, verifier는 correct·flagged 불리언을 가진
원출력 조건별 채점 기록이다. 값이 없으면 결과도 None이다. 실제 정답 파일은 변경하지 않는다.
