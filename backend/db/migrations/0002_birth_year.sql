-- 출생연도(birth_year). api.md §2 프로필과 엔진(만 나이 두 값, 단계 날짜)이 이 칸을 쓴다.
-- 0001은 생년월일(birth_date)만 두어 프리셋·화면이 보내는 birth_year를 저장하지 못했다. birth_date는 그대로 둔다.
ALTER TABLE users   ADD COLUMN birth_year integer;
ALTER TABLE parents ADD COLUMN birth_year integer;
