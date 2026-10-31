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
