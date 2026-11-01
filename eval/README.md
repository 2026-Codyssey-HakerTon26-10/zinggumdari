평가 연결
=========

현재 상태 (2026-11-01)
---------------------

#60은 main에 병합됐다. 페르소나 정답 5건, 표본 50개·개발용 원출력 45개 채점 기록,
results.json이 이미 존재한다. 과거의 "아직 없음" 요청은 현재 상태와 다르다.
이번 결과는 생년월일 전환 이후 엔진으로 다시 실행했다. 개발용 엄격 키 일치 3/11,
표본 근거 대조 31/50, 원출력 오답 포착 9/12다. 수치를 독립 시험 정확도로 말하지 않는다.
KNN 독립 시험은 eval/knn_test.py로 측정했다(아래 「KNN 독립 시험」). 부모 판정 일치(가상 인구에 부모 정보 없음)는 범위 밖으로 두고, 외부 서비스 확인은 남아 있다.


`uv run --project backend python -m eval.score --input 채점기록.json --split eval/split.json --output eval/results.json`

채점기록의 verdicts는 expected/actual 판정 쌍, extraction은 gold/extracted 조건 배열 쌍이다.
정답 데이터는 평가 담당자가 원문과 동결한 조건표에서 만든다. 예시 숫자로 실제 정답을 만들지 않는다.
score 도구는 지정한 입력 외에는 페르소나 정답이나 시험용 조건표를 읽지 않는다.
판정 일치 평가에서 AI_ELIGIBLE을 허용하는 설정은 규칙 엔진 어댑터에서 명시한다.

`explore.compare`는 pool/holdout이 겹치면 거부하고 원래 필드 단위로 1개·3개·절반을 남긴다.
KNN 20/50/100, 동일 필터를 거친 전체 해당 비율 순위와 무작위를 비교한다.
인기순 기준보다 낮은 시나리오가 있으면 demo_enabled=False다. 이 기준선 이름은 평가에서만 쓰고
추천 카드에서는 선호·인기라는 표현을 쓰지 않는다.

`coverage.create_router(load_rules)`는 main에 등록돼 있다. 평가 전에는 null을 반환한다.
공개 results.json에 개인별 프로필·정답을 넣지 않는다. silent_omissions는 공고 조건과 근거 줄만 포함한다.
손 조건표·엔진은 연결됐지만 AI 조건표·실제 채점 기록이 없으면 결과 파일과 표본 채점 숫자를 생성하지 않는다.

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
split의 dev/test는 제도 ID 목록이다. 개발용만 채점하며 test·outside·미지정 제도는 거부한다. 시험용은 개수만 기록하고 정밀도는 항상 null이다.
sample50은 rule_id·condition_index·correct 불리언을 가진 중복 없는 정확히 50개 채점 기록, verifier는 correct·flagged 불리언을 가진
원출력 조건별 채점 기록이다. 값이 없으면 결과도 None이다. 실제 정답 파일은 변경하지 않는다.


개발용 평가와 제출 준비 (#43)
----------------------------

추출 정밀도와 판정 일치는 개발용 5개만 입력한다. 출력은 evaluation_scope=dev_only,
precision_auto_verified.dev와 test=null이다. limitation 문구를 /stats/coverage에도 전달한다.
개발용은 프롬프트를 맞춘 집합이므로 독립 시험 성능으로 발표하면 안 된다.
채점 기록이 없으면 status=not_evaluated이고 수치는 null이다. 빈 결과 파일로 완료를 대신하지 않는다.
판정 기록의 (user_id, rule_id) 및 추출 기록의 rule_id 중복은 거부한다.

AI 결과가 준비되면 원문을 다시 호출하지 않고 캐시에서 표본을 만든다:

`uv run --project backend python -m eval.sample --rules-dir rules/compiled --output eval/sample50.json`

표본은 고정 seed, 모집단 해시, 중복 없는 50개 조건을 기록한다. 50개 미만이면 실패하고
correct는 모두 null이다. 프롬프트를 작성하지 않는 평가 담당자가 evidence의 원문과 대조하여
각 correct를 true/false로 작성한다. 실패한 조건을 더 좋은 조건으로 바꾸거나 재추출하지 않는다.
완료된 표본 객체를 채점기록의 sample50에 넣어 eval.score를 실행한다. 표본은 덮어쓰지 않는다.
페르소나 정답도 원문을 보고 별도로 확정하며 엔진의 출력값을 정답으로 복사하지 않는다.

`uv run --project backend python -m eval.submission`

점검기는 외부 자원 표의 미확정 행, AI 조건표·페르소나·실제 평가 결과 존재와 평가 범위,
현재 commit과 git 저자 이름을 보여준다. 개인정보 정답 본문은 열지 않는다. 실제 팀원 5명의
실명 대응 확인·팀명 확정·외부 자원 이용 조건 확인은 사람이 마친 뒤에만 다음을 실행한다:

`uv run --project backend python -m eval.submission --team-name 팀명 --authors-confirmed --commit HEAD --write /tmp/submission`

미완료 항목, 더러운 작업 트리, HEAD와 다른 커밋이면 제출 안내를 만들지 않는다. 생성 파일은
저장소 공개 주소와 정확한 커밋 해시만 담고 기존 제출 파일은 덮어쓰지 않는다. 이 명령은 main을
수정하거나 커밋을 고정하지 않으며 마감 뒤 main 변경에는 팀장 승인이 필요하다.

이메일 대상 연결
----------------

현재 main의 알림 라우터와 send_email은 이메일 채널 선택·관심 분야·수신 주소·기발송 여부를
확인한다. 프로필 저장 담당자가 동의한 alert_channel/alert_categories/email을 DB에 저장해야 한다.
실제 SMTP 설정과 수신 계정 확인 없이는 실메일 테스트를 하지 않는다. 앱 재판정은 인앱 알림 저장이며
자동 이메일 발송 작업자·delivery_unknown 복구까지 완료된 것은 아니다(backend/notify/README.md).


가상 함정 페르소나
-----------------

혼인 8년·소득 초과, 소득 초과 단독 사례, 64세 부모님, 접수 마감 청년월세, 만 나이 경계
5건을 eval/personas/에 작성했다. 모두 가상이며 독립적인 손 조건표 근거를 expected에 기록했다.
64세는 미래 개방/확인 필요를 허용하고 eligible을 금지한다. 생년만 아는 만 나이 경계는
확인 필요만 허용한다. 엔진 결과로 정답을 생성하거나 실패 후 정답을 맞추지 않는다.
평가 담당자가 명시적으로 실행한다(일반 테스트는 이 정답 파일을 열지 않는다):

`uv run --project backend python -m eval.personas --personas-dir eval/personas --output eval/persona-results.json`

persona-results.json은 이 5건의 안전성 점검 결과이며, 개발용 추출 정밀도나 9000가구 판정 일치,
표본50 채점을 대체하지 않는다. eval/results.json의 실제 AI 평가와 이 5건의 함정 안전성 결과를 혼동하지 않는다.


현재 채점 스냅샷
----------------

현재 results.json과 reviews/는 #54의 커밋 2d6b5adba5ee1b930530ed0ab9dd9df6ee1d86c7을
대상으로 Codex 보조 채점한 기록이다. 원래 표본 50개(seed=42, 모집단 961개)를 바꾸지 않았고,
개발용 원출력 45개도 근거와 대조했다. 첨부 근거 135개를 같은 커밋의 lines.json과 대조했다.
리뷰 파일에 각 행의 원본 해시와 판정 이유를 남겼다. 원문에 없는 기준일, 주체/대안 상실,
지역 분기 누락은 오답으로 보수적으로 처리한다. 발표 전 이 채점 기준과 개별 판단을 검토할 수 있다.
other의 문구 차이로 인한 엄격 키 일치의 한계도 그대로 남겼으며 근거 겹침만으로 정답을 늘리지 않는다.

#54 입력 세 파일은 main의 eval/에 병합돼 있다:

`uv run --project backend python -m eval.assemble --inputs-dir eval`

원본 입력의 출처 커밋은 source_snapshot에 보존한다. 현재 main 입력 파일/조건의 해시가 달라지면 기존 리뷰를 재사용하지 않는다.
개발용 5개 추출 점수와 표본 점수는 별도 분모로 보고, test는 항상 null이다. 고정 원본 스냅샷과
현재 조건표 개수를 혼동하지 않도록 source_snapshot을 공개 통계에도 전달한다.

원래 생성된 가상 인구 users.parquet 캐시가 있으면 네트워크 없이 판정 일치를 계산한다:

`uv run --project backend python -m eval.agreement --input eval/score_input.json --population data/population/users.parquet --today 2026-11-01 --output /tmp/agreement.json`

`uv run --project backend python -m eval.assemble --inputs-dir eval --agreement /tmp/agreement.json`

캐시의 pool 9000가구 × 개발용 본인 제도 3개 = 27000쌍을 비교했다. 부모 정보가 없는 캐시라
부모 제도 2개는 지어내지 않고 제외했으며 agreement_source에 기록했다. 같은 엔진의 손/AI 조건
비교이므로 독립적인 법률 정확도나 KNN 최종 성능이 아니다. KNN 독립 시험은 아래 절에 있다.
로컬 시연 기준으로 진행하며 Vercel CORS/쿠키 배포 변경은 이번 작업에 포함하지 않는다.


제출 팀 정보
------------

사용자 확인 팀명은 **초보임**이며 계정·실명 대응은 team.json에 기록했다.
submission 명령은 이 파일에서 팀명과 확인된 5명 대응을 읽는다. 명시적인 --team-name은
파일 값을 덮어쓴다. GitHub 계정은 대소문자 구분 없이 중복 검사한다. 과거 git author 별칭을
실명으로 바꾸거나 커밋 이력을 재작성한 것은 아니며, 점검 출력에서 원래 저자 이름도 확인한다.
팀명·실명이 확인돼도 나머지 평가/외부 자원 점검이 통과하기 전에는 제출 파일을 생성하지 않는다.


제출 점검의 재생성 조건
----------------------

submission은 파일 존재만으로 평가 완료를 판단하지 않는다. 원본 입력 세 파일과 채점 기록 해시,
채점기 코드 해시, 판정 일치 평가의 엔진 코드 해시를 현재 코드와 대조한다. 페르소나 안전성은
모든 사례 통과·위험 eligible 0건과 현재 페르소나/엔진 해시를 확인한다. KNN은 독립 시험 결과가
없으면 미완료로 남긴다. 해시 계산은 정답 본문을 출력하지 않는다. 코드나 입력이 바뀌면
agreement/personas/assemble 명령을 다시 실행해야 한다. 현재 결과를 통과시키기 위해 누락된
부모 정보나 미측정 KNN 수치를 지어내지 않는다. 이 점검은 영상·발표자료 및 대회 규정의
전체 준수 여부를 자동 보증하지 않는다.


KNN 독립 시험
-------------

`uv run --project backend python -m eval.knn_test --today 2026-11-01`

가상 인구의 holdout 1000명을 seed 42로 검증 500명·시험 500명으로 나눈다. pool 9000명이 이웃 후보다.
k(20/50/100)는 검증으로만 고르고 시험은 고른 k로 한 번만 돌린다. 추천 쪽 판정은 compare()가 가린 행만
엔진에 넣어 계산하고, 정답은 원래 행 전체의 확정 판정이다. 기준선(인기순·무작위)은 KNN과 같은 정책 필터
(`knn.open_to`)와 종류별 개수 제한(`knn.top_by_type`)을 쓴다. 결과는 eval/explore-results.json이며
이미 있으면 덮어쓰지 않는다(코드·인구가 바뀌어 다시 잴 때만 `--overwrite`).

현재 결과: 시험 precision@5 0.0084, recall@5 0.20(k=20). 무작위 0.0048/0.11보다 높고 인기순과 같다.
가상 인구에 자산 등 칸이 없어 검수된 나 대상 제도 17개 중 확정 판정이 나오는 제도는 1개(rules_with_positive)이므로,
이 수치는 그 범위의 값이다. demo_enabled는 인기순과 동률이라 true이며 KNN 우위의 근거로 쓰지 않는다.
