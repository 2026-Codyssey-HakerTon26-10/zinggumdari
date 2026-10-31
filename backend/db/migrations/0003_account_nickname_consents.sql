-- 가입 때 받는 닉네임과 필수 동의(SPEC §4.1). 계정에 둔다(추천 입력 칸인 users와 분리).
-- 동의는 동의한 시각만 남긴다. 선택 동의(이메일 알림, 민감정보)는 여기가 아니라 프로필 consents에 있다.
-- 이 파일 전에 가입한 계정은 null이다(화면이 칸을 보내기 전 가입).
ALTER TABLE auth_accounts ADD COLUMN nickname          text;
ALTER TABLE auth_accounts ADD COLUMN terms_agreed_at   timestamptz;
ALTER TABLE auth_accounts ADD COLUMN privacy_agreed_at timestamptz;
