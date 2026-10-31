알림 연결
=========

`router.create_router(store, require_user, require_admin)`를 앱 담당자가 등록한다.
인증을 기본 허용하는 경로는 없다. require_user는 세션 소유 프로필 ID를 반환하고,
require_admin은 전 사용자 재판정 권한을 확인해야 한다.

PostgreSQL 저장소 어댑터는 다음 메서드를 제공한다.

- list(user_id): 소유자의 알림 목록만 반환
- mark_read(user_id, notification_id): 두 ID를 함께 조건으로 갱신하고 미소유/없음은 None
- rebuild(today): service.rebuild에 저장된 프로필과 규칙 엔진, save 콜백 연결
- test_email(user_id): 소유자 알림 설정의 수신 동의·관심 분야 확인 후 자기 주소로만 발송

save(user_id, item)은 알림 ID를 고유 키로 upsert하고 계정 삭제 시 함께 삭제한다.
앱 알림을 먼저 저장한 다음 email.send_email을 호출한다. 메일 실패 시 앱 알림은 보존한다.
record_sent(user_id, notification_id, emailed_at)은 성공 시각을 저장한다.
동시 발송 작업은 DB에서 같은 알림을 한 작업자만 잡도록 구현해야 한다.
SMTP는 STARTTLS를 사용하고 비밀번호를 로그에 남기지 않는다. 환경변수는 기존 .env.example을 쓴다.

날짜는 새로 계산하지 않는다. 플래너가 계산한 kind/due/title/evidence/from 이벤트를 받아
검증된 조건의 evidence와 대조하고 해당 날짜에만 만든다. 부모 연도 알림은 연도 단위로 처리한다.
인구 기반 알림은 population.recommend의 필터를 통과한 item만 explore_notification에 전달한다.

현재 인증·DB·플래너가 없어 실제 main 등록과 실메일 발송은 연결 후 검증해야 한다.

judge(profile, rules, today=today)는 알림과 동일한 기준일을 받아야 한다.
superseded_by와 no_subject 카드는 알림에서 제외한다. opens_later는 검증된 날짜 이벤트만 허용한다.
due는 발송일이다. D-90 등의 발송일은 플래너가 계산한다. 여러 날 표시할 경우 플래너가
notify_from(ISO 날짜)을 제공하면 그 날부터 due까지 생성한다. 숫자 90을 알림 코드에 넣지 않는다.

공고 투입 연결점은 backend.notify.api.connect(handler)다. handler는 rule_ids·today·account_id를 받아
service.rebuild의 동일 인자에 전달한다. 계정이 있는 요청에서 해당 인자를 받지 못하는 handler는
호출하지 않는다. upload: 제도는 account_id 없이 호출할 수 없으며 전체 사용자로 폴백하지 않는다.
DB 어댑터는 세션의 계정 소유 관계를 확인하고 내부 profile.account_id를 붙여 전달한다.
service.rebuild도 해당 account_id의 프로필만 판정한다. 내부 계정 메타데이터가 없으면 제외한다.
공용 규칙은 모두 판정에 주되 업로드는 범위가 있는 선택된 제도만 포함한다.
전 사용자 공개 공고 재판정은 account_id=None이며 사용자 업로드 규칙을 판정·알림에서 제외한다.

ID 중복 upsert는 기존 read, created, emailed_at을 유지해야 한다. 메일 발송은 upsert 후
DB에서 다시 읽은 레코드로 판단해야 한다. 생성 직후의 read=False 레코드를 바로 발송하지 않는다.
SMTP는 정확히 한 번 발송을 보장하지 않는다. 최소 한 번 정책에서는 중복 가능성이 있다.
SMTP 수락 후 record_sent가 실패하면 DeliveryRecordError가 발생하며, 어댑터는 해당 작업을
delivery_unknown으로 분리하고 자동 재발송을 멈춘다. 수락 결과를 확인해 기록만 복구하거나,
중복 가능성을 인지한 명시적 재시도를 선택해야 한다. SMTP 수락 전 실패만 retryable로 처리한다.

업로드 판정에는 account_id와 명시적 rule_ids가 둘 다 필요하다. rule_ids=None 또는 []이면
업로드를 엔진에 전달하지 않는다. 공용 규칙만 판정한다. rule_ids는 신뢰할 수 있는 서버
어댑터가 해당 계정의 소유 관계를 확인한 ID만 전달해야 하며, 클라이언트의 ID 목록을
그대로 전달하면 안 된다. 계정 지정만으로 모든 업로드를 볼 수 있는 권한이 생기지 않는다.
