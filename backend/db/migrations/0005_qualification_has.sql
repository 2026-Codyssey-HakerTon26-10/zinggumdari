-- 공고별 자격 질문의 해당·미해당 답변을 저장한다.
ALTER TABLE user_qualifications ADD COLUMN has text NOT NULL DEFAULT 'Y';
-- 기존 행과 has를 생략한 기존 입력은 종전과 같이 해당함(Y)으로 유지한다.
ALTER TABLE user_qualifications ADD CONSTRAINT user_qualifications_has_valid CHECK (has IN ('Y', 'N'));
