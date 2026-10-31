-- 처음 스키마 (SPEC §14.1, api.md §2·§5·인증 절). 칸 이름은 팀 시트 `복지추천_필드스키마_3단계.xlsx`의 DB필드_ 탭 그대로.
-- 시트에서 뺀 것: 계산값 income_band_median·income_band_urban(판정 때 계산), situation_text(MVP에서 안 받음).
-- 시트에 없는데 더한 것: 동의·stages_done(api.md §2), user_alert.email(알림 주소, api.md §2), 계정·세션·알림 테이블.
-- 금액은 전부 만원. 계정을 지우면 세션·프로필·알림이 같이 지워진다(ON DELETE CASCADE).

-- 계정·세션 (비밀번호와 세션 토큰은 해시만)
CREATE TABLE auth_accounts (
    account_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email          text NOT NULL,
    password_hash  text NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX auth_accounts_email_key ON auth_accounts (lower(email));

CREATE TABLE auth_sessions (
    session_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id   uuid NOT NULL REFERENCES auth_accounts ON DELETE CASCADE,
    token_hash   text NOT NULL UNIQUE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    revoked_at   timestamptz
);
CREATE INDEX auth_sessions_account_idx ON auth_sessions (account_id);

-- ① 가입 (계정당 프로필 하나)
CREATE TABLE users (
    user_id             text PRIMARY KEY,
    account_id          uuid NOT NULL UNIQUE REFERENCES auth_accounts ON DELETE CASCADE,
    stages_done         text[] NOT NULL DEFAULT '{}',
    consent_sensitive   boolean NOT NULL DEFAULT false,
    consent_parent      boolean NOT NULL DEFAULT false,
    nickname            text,
    gender              text,
    birth_year          integer,
    sido                text,
    sigungu             text,
    marital_status      text,
    marriage_date       date,
    pregnant            text,
    due_month           text,          -- 'YYYY-MM'
    children_count      integer,
    youngest_child_age  integer,
    household_size      integer,
    employment_status   text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- ② 알림 설정 (프로필당 한 줄)
CREATE TABLE user_housing (
    user_id         text PRIMARY KEY REFERENCES users ON DELETE CASCADE,
    tenure_type     text,
    is_householder  text,
    is_homeless     text,
    deposit         numeric,
    monthly_rent    numeric,
    move_in_date    date,
    house_price     numeric          -- 공시가격, 자가일 때만
);

CREATE TABLE user_income (
    user_id             text PRIMARY KEY REFERENCES users ON DELETE CASCADE,
    employment_type     text,
    income_self         numeric,
    income_spouse       numeric,
    income_household    numeric,
    dependents_count    integer,
    supports_parent_65  text,
    support_start_date  date
);

CREATE TABLE user_subscription (
    user_id         text PRIMARY KEY REFERENCES users ON DELETE CASCADE,
    has_account     text,
    joined_date     date,
    payment_count   integer,
    deposit_amount  numeric
);

CREATE TABLE user_alert (
    user_id           text PRIMARY KEY REFERENCES users ON DELETE CASCADE,
    alert_categories  text[],
    alert_channel     text,
    email             text            -- 알림 받을 주소. 계정 이메일과 따로
);

-- ③ 공고별 확인 (한 줄에 하나)
CREATE TABLE user_qualifications (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    text NOT NULL REFERENCES users ON DELETE CASCADE,
    qual_code  text NOT NULL,
    target     text,
    verified   text
);
CREATE INDEX user_qualifications_user_idx ON user_qualifications (user_id);

CREATE TABLE user_history (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       text NOT NULL REFERENCES users ON DELETE CASCADE,
    event_type  text NOT NULL,     -- 코드는 시트 DB코드표_이력종류
    event_date  date
);
CREATE INDEX user_history_user_idx ON user_history (user_id);

CREATE TABLE parents (
    user_id                text NOT NULL REFERENCES users ON DELETE CASCADE,
    relation               text NOT NULL CHECK (relation IN ('부', '모')),
    birth_year             integer,
    sido                   text,
    sigungu                text,
    lives_alone            text,
    lives_with_child       text,
    ltc_grade              text,
    disability_registered  text,
    basic_pension          text,
    livelihood_status      text,
    care_wanted            text,
    PRIMARY KEY (user_id, relation)
);

-- 알림 (backend/notify/ 레코드 모양)
CREATE TABLE notifications (
    id          text PRIMARY KEY,
    user_id     text NOT NULL REFERENCES users ON DELETE CASCADE,
    kind        text NOT NULL,
    subject     text NOT NULL,
    rule_id     text NOT NULL,
    title       text NOT NULL,
    created     date NOT NULL,
    due         text,              -- 'YYYY-MM-DD' 또는 'YYYY'
    extra       jsonb NOT NULL DEFAULT '{}',   -- from, evidence, prevalence 같은 나머지 칸
    read        boolean NOT NULL DEFAULT false,
    emailed_at  timestamptz
);
CREATE INDEX notifications_user_idx ON notifications (user_id);

-- 제도의 조건 한 줄 (시트 칸 policy_id·field·operator·value·standard + 조건 JSON에서 온 칸)
-- policy_id는 조건 JSON의 id(manual:…). any_of는 묶음·가지 번호
CREATE TABLE policy_requirements (
    policy_id   text NOT NULL,
    seq         integer NOT NULL,
    field       text NOT NULL,
    operator    text NOT NULL,
    value       jsonb,
    standard    text,              -- 소득 조건의 기준표(income_basis). 아니면 NULL
    any_of      integer,
    branch      integer,
    subject     text NOT NULL,
    status      text,
    evidence    text[] NOT NULL DEFAULT '{}',
    condition   jsonb NOT NULL,    -- 원래 조건 그대로
    PRIMARY KEY (policy_id, seq)
);

-- 연도별 소득 기준표 (월, 만원)
CREATE TABLE income_standards (
    year            integer NOT NULL,
    basis           text NOT NULL,     -- median_pct, urban_worker_pct …
    household_size  integer NOT NULL,
    amount          numeric NOT NULL,
    PRIMARY KEY (year, basis, household_size)
);
