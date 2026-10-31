평가 연결
=========

`uv run --project backend python -m eval.score --input 채점기록.json --output eval/results.json`

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
