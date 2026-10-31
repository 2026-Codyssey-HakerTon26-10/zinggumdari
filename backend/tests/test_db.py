"""PostgreSQL 테이블과 프로필 저장(SPEC §14.1, api.md §2).

진짜 PostgreSQL에 붙는다. TEST_DATABASE_URL(환경변수나 .env)이 없으면 건너뛴다. 매 테스트마다 스키마를 지우고 다시 만든다.
예: TEST_DATABASE_URL=postgresql://localhost/zinggumdari_test
"""

import copy
from datetime import date

import pytest

from backend.data.config import env

URL = env("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="TEST_DATABASE_URL 없음")

if URL:
    import psycopg

    from backend.db import connect, migrate, profiles

PROFILE = {
    "stages_done": ["signup", "alerts"],
    "consents": {"sensitive": True, "parent": True},
    "self": {
        "nickname": "지원", "gender": "여", "birth_year": 1999, "sido": "서울", "sigungu": "마포구",
        "marital_status": "예비부부", "marriage_date": None, "pregnant": "N", "due_month": None,
        "children_count": 0, "youngest_child_age": None, "household_size": 1, "employment_status": "재직",
        "tenure_type": "월세", "is_householder": "세대주", "is_homeless": "Y", "deposit": 1000, "monthly_rent": 55,
        "move_in_date": "2024-03-01", "house_price": None,
        "employment_type": "해당없음", "income_self": 270, "income_spouse": None, "income_household": 270,
        "dependents_count": 0, "supports_parent_65": "N", "support_start_date": None,
        "has_account": "Y", "joined_date": "2021-03-01", "payment_count": None, "deposit_amount": None,
        "alert_categories": ["주거", "임신출산"], "alert_channel": "이메일", "email": "jiwon@example.com",
        "qualifications": [{"qual_code": "청년", "target": "본인", "verified": "자기신고"}],
        "history": [{"event_type": "청약_당첨", "event_date": "2023-05-10"}],
    },
    "parents": [
        {"relation": "모", "birth_year": 1966, "sido": "경기", "sigungu": "고양시", "lives_alone": "Y",
         "lives_with_child": "N", "ltc_grade": "없음", "disability_registered": "N", "basic_pension": "N",
         "livelihood_status": "해당없음", "care_wanted": "Y"},
    ],
}


@pytest.fixture
def conn():
    with psycopg.connect(URL, autocommit=True) as c:
        c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
    c = connect(URL)
    migrate.run(c)
    yield c
    c.close()


def _account(conn, email="a@example.com"):
    return profiles.create_account(conn, email, "hash$x")


def _count(conn, table):
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_migrate_twice_is_noop(conn):
    assert migrate.run(conn) == []
    tables = {r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")}
    assert {"auth_accounts", "auth_sessions", "users", "user_housing", "user_income", "user_subscription",
            "user_alert", "user_qualifications", "user_history", "parents", "policy_requirements",
            "income_standards", "notifications", "schema_migrations"} <= tables


def test_save_and_load_roundtrip(conn):
    user_id = profiles.create(conn, _account(conn), PROFILE)
    got = profiles.load(conn, user_id)
    assert got["user_id"] == user_id
    assert user_id.startswith("U")
    assert got["stages_done"] == PROFILE["stages_done"]
    assert got["consents"] == PROFILE["consents"]
    assert got["self"] == PROFILE["self"]
    assert got["parents"] == PROFILE["parents"]


def test_dates_come_back_as_iso_strings(conn):
    p = copy.deepcopy(PROFILE)
    p["self"]["marriage_date"] = "2025-05-10"
    user_id = profiles.create(conn, _account(conn), p)
    got = profiles.load(conn, user_id)["self"]
    assert got["marriage_date"] == "2025-05-10"
    assert got["move_in_date"] == "2024-03-01"
    assert got["history"] == [{"event_type": "청약_당첨", "event_date": "2023-05-10"}]


def test_save_replaces_rows(conn):
    user_id = profiles.create(conn, _account(conn), PROFILE)
    p = profiles.load(conn, user_id)
    p["self"]["income_self"] = 300
    p["self"]["qualifications"] = []
    p["self"]["history"] = []
    p["parents"] = []
    profiles.save(conn, p)
    got = profiles.load(conn, user_id)
    assert got["self"]["income_self"] == 300
    assert got["self"]["qualifications"] == []
    assert got["self"]["history"] == []
    assert got["parents"] == []


def test_signup_only_profile_has_empty_later_stages(conn):
    p = {"stages_done": ["signup"], "consents": {"sensitive": False, "parent": False},
         "self": {"nickname": "민", "birth_year": 1995}, "parents": []}
    got = profiles.load(conn, profiles.create(conn, _account(conn), p))
    assert got["self"]["nickname"] == "민"
    assert got["self"]["income_self"] is None
    assert got["self"]["alert_categories"] is None
    assert got["self"]["qualifications"] == []


def test_sheet_columns_exist(conn):
    """팀 시트 DB필드_ 탭의 칸 이름 그대로(계산값 income_band_*, MVP에서 안 받는 situation_text는 뺌)."""
    cols = {(t, c) for t, c in conn.execute(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'")}
    for want in [("user_housing", "house_price"), ("user_income", "support_start_date"),
                 ("user_history", "event_type"), ("user_history", "event_date"),
                 ("policy_requirements", "policy_id"), ("policy_requirements", "field"),
                 ("policy_requirements", "operator"), ("policy_requirements", "value"),
                 ("policy_requirements", "standard")]:
        assert want in cols, want


def test_unknown_field_is_rejected(conn):
    p = copy.deepcopy(PROFILE)
    p["self"]["real_name"] = "홍길동"
    with pytest.raises(ValueError):
        profiles.create(conn, _account(conn), p)
    assert _count(conn, "users") == 0


def test_load_missing_returns_none(conn):
    assert profiles.load(conn, "Unope") is None


def test_one_profile_per_account(conn):
    account = _account(conn)
    profiles.create(conn, account, PROFILE)
    with pytest.raises(psycopg.errors.UniqueViolation):
        profiles.create(conn, account, PROFILE)
    assert profiles.user_id_for(conn, account) is not None


def test_email_unique_ignoring_case(conn):
    _account(conn, "Jiwon@Example.com")
    with pytest.raises(psycopg.errors.UniqueViolation):
        _account(conn, "jiwon@example.com")


def test_profile_needs_existing_account(conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        profiles.create(conn, "00000000-0000-0000-0000-000000000000", PROFILE)


def test_delete_account_removes_everything(conn):
    account = _account(conn)
    user_id = profiles.create(conn, account, PROFILE)
    conn.execute("INSERT INTO auth_sessions (account_id, token_hash, expires_at) VALUES (%s, 'h', now())",
                 (account,))
    conn.execute("INSERT INTO notifications (id, user_id, kind, subject, rule_id, title, created) "
                 "VALUES ('n_1', %s, 'new_rule', 'self', 'manual:x', 't', %s)", (user_id, date(2026, 11, 1)))
    other = profiles.create(conn, _account(conn, "b@example.com"), PROFILE)

    profiles.delete_account(conn, account)

    assert profiles.load(conn, user_id) is None
    for table in ("auth_sessions", "notifications"):
        assert _count(conn, table) == 0
    assert _count(conn, "parents") == 1  # 다른 계정 것은 남는다
    assert profiles.load(conn, other) is not None


def test_delete_profile_keeps_account(conn):
    account = _account(conn)
    user_id = profiles.create(conn, account, PROFILE)
    profiles.delete(conn, user_id)
    assert profiles.load(conn, user_id) is None
    assert _count(conn, "auth_accounts") == 1
    assert _count(conn, "user_qualifications") == 0
