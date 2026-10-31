-- 팀 결정: 출생 정보는 생년월일(birth_date)이 기준이다. 만 나이는 판정 기준일과 생년월일로 한 값을 계산한다.
-- 0002가 더한 출생연도(birth_year) 칸을 뺀다. 0002는 이미 적용한 DB가 있어 고치지 않고 여기서 뺀다.
ALTER TABLE users   DROP COLUMN IF EXISTS birth_year;
ALTER TABLE parents DROP COLUMN IF EXISTS birth_year;
