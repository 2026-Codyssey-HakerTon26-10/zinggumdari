"""PostgreSQL 테이블과 프로필 저장(SPEC §14.1, api.md §2).

진짜 PostgreSQL에 붙는다. TEST_DATABASE_URL(환경변수나 .env)이 없으면 건너뛴다.
테스트마다 무작위 이름의 스키마(test_…)를 만들어 그 안에만 테이블을 만들고, 끝나면 그 스키마만 지운다.
public이나 다른 스키마는 건드리지 않는다. 예: TEST_DATABASE_URL=postgresql://localhost/zinggumdari_test
"""

import copy
import secrets
import threading
from contextlib import contextmanager
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
        "nickname": "지원", "gender": "여", "birth_date": "1999-04-15", "sido": "서울", "sigungu": "마포구",
        "marital_status": "예비부부", "marriage_date": None, "pregnant": "N", "due_month": None,
        "children_count": 0, "youngest_child_age": None, "household_size": 1, "employment_status": "재직",
        "tenure_type": "월세", "is_householder": "세대주", "is_homeless": "Y", "deposit": 1000, "monthly_rent": 55,
        "move_in_date": "2024-03-01", "house_price": None,
        "employment_type": "해당없음", "income_self": 270, "income_spouse": None, "income_household": 270,
        "dependents_count": 0, "supports_parent_65": "N", "support_start_date": None,
        "has_account": "Y", "joined_date": "2021-03-01", "payment_count": None, "deposit_amount": None,
        "alert_categories": ["주거", "임신출산"], "alert_channel": "이메일", "email": "jiwon@example.com",
        "qualifications": [{"qual_code": "청년", "target": "본인", "verified": "자기신고", "has": "Y"}],
        "history": [{"event_type": "청약_당첨", "event_date": "2023-05-10"}],
    },
    "parents": [
        {"relation": "모", "birth_date": "1966-07-03", "sido": "경기", "sigungu": "고양시", "lives_alone": "Y",
         "lives_with_child": "N", "ltc_grade": "없음", "disability_registered": "N", "basic_pension": "N",
         "livelihood_status": "해당없음", "care_wanted": "Y"},
    ],
}


@contextmanager
def isolated_schema():
    """무작위 스키마 하나를 만들고 search_path를 거기로. 나갈 때 그 스키마만 지운다."""
    name = "test_" + secrets.token_hex(6)
    c = connect(URL)
    try:
        c.execute(f"CREATE SCHEMA {name}")
        c.execute(f"SET search_path TO {name}")
        migrate.run(c)
        yield c, name
    finally:
        c.execute(f"DROP SCHEMA IF EXISTS {name} CASCADE")
        c.close()


@pytest.fixture
def conn():
    with isolated_schema() as (c, _):
        yield c


@pytest.fixture
def schema():
    with isolated_schema() as (c, name):
        yield c, name


def _connect_to(name):
    c = connect(URL)
    c.execute(f"SET search_path TO {name}")
    return c


def _account(conn, email="a@example.com"):
    return profiles.create_account(conn, email, "hash$x")


def _count(conn, table):
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_migrate_twice_is_noop(conn):
    assert migrate.run(conn) == []
    tables = {r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()")}
    assert {"auth_accounts", "auth_sessions", "users", "user_housing", "user_income", "user_subscription",
            "user_alert", "user_qualifications", "user_history", "parents", "policy_requirements",
            "income_standards", "notifications", "schema_migrations"} <= tables


def test_public_schema_is_untouched():
    marker = "zz_test_marker_" + secrets.token_hex(4)
    with psycopg.connect(URL, autocommit=True) as c:
        c.execute(f"CREATE TABLE public.{marker} (x int)")
        c.execute(f"INSERT INTO public.{marker} VALUES (1)")
        try:
            with isolated_schema() as (inner, name):
                profiles.create(inner, _account(inner), PROFILE)
            assert c.execute(f"SELECT x FROM public.{marker}").fetchone() == (1,)
            assert c.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
                             (name,)).fetchone() is None
        finally:
            c.execute(f"DROP TABLE public.{marker}")


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


def test_update_replaces_rows(conn):
    user_id = profiles.create(conn, _account(conn), PROFILE)

    def change(p):
        p["self"]["income_self"] = 300
        p["self"]["qualifications"] = []
        p["self"]["history"] = []
        p["parents"] = []

    returned = profiles.update(conn, user_id, change)
    got = profiles.load(conn, user_id)
    assert returned == got
    assert got["self"]["income_self"] == 300
    assert got["self"]["qualifications"] == []
    assert got["self"]["history"] == []
    assert got["parents"] == []


def test_signup_only_profile_has_empty_later_stages(conn):
    p = {"stages_done": ["signup"], "consents": {"sensitive": False, "parent": False},
         "self": {"nickname": "민", "birth_date": "1995-01-01"}, "parents": []}
    got = profiles.load(conn, profiles.create(conn, _account(conn), p))
    assert got["self"]["nickname"] == "민"
    assert got["self"]["income_self"] is None
    assert got["self"]["alert_categories"] is None
    assert got["self"]["qualifications"] == []


def test_sheet_columns_exist(conn):
    """팀 시트 DB필드_ 탭의 칸 이름 그대로(계산값 income_band_*, MVP에서 안 받는 situation_text는 뺌)."""
    cols = {(t, c) for t, c in conn.execute(
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = current_schema()")}
    for want in [("users", "birth_date"), ("parents", "birth_date"), ("user_housing", "house_price"), ("user_income", "support_start_date"),
                 ("user_history", "event_type"), ("user_history", "event_date"),
                 ("policy_requirements", "policy_id"), ("policy_requirements", "field"),
                 ("policy_requirements", "operator"), ("policy_requirements", "value"),
                 ("policy_requirements", "standard")]:
        assert want in cols, want
    # 출생은 생년월일이 기준이다(팀 결정). 0002가 더한 출생연도 칸은 0004가 뺐다
    assert ("users", "birth_year") not in cols and ("parents", "birth_year") not in cols


def test_update_missing_returns_none(conn):
    assert profiles.update(conn, "Unope", lambda p: None) is None


def test_update_unknown_field_keeps_old_values(conn):
    user_id = profiles.create(conn, _account(conn), PROFILE)

    def change(p):
        p["self"]["income_self"] = 1
        p["self"]["real_name"] = "홍길동"

    with pytest.raises(ValueError):
        profiles.update(conn, user_id, change)
    assert profiles.load(conn, user_id)["self"]["income_self"] == 270


def test_concurrent_updates_do_not_lose_changes(schema):
    """A가 동의를 거두고 소득을 지우는 동안 B가 닉네임을 바꾼다. B는 A가 끝난 최신 값 위에 고쳐야 한다."""
    conn, name = schema
    user_id = profiles.create(conn, _account(conn), PROFILE)
    other = _connect_to(name)
    b_done = threading.Event()

    def b_change(p):
        p["self"]["nickname"] = "민"

    def run_b():
        profiles.update(other, user_id, b_change)
        b_done.set()

    def a_change(p):
        threading.Thread(target=run_b).start()
        assert not b_done.wait(0.5)  # A가 잠금을 쥐고 있는 동안 B는 기다린다
        p["consents"]["sensitive"] = False
        p["self"]["income_self"] = None
        p["self"]["income_household"] = None

    try:
        profiles.update(conn, user_id, a_change)
        assert b_done.wait(5)
    finally:
        other.close()
    got = profiles.load(conn, user_id)
    assert got["self"]["nickname"] == "민"
    assert got["consents"]["sensitive"] is False
    assert got["self"]["income_self"] is None
    assert got["self"]["income_household"] is None


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


@pytest.mark.parametrize("answer", ["Y", "N"])  # 해당·미해당 두 답변의 DB 왕복을 확인한다.
def test_qualification_answer_survives_storage(conn, answer):  # 실제 저장·조회에서 답이 바뀌지 않아야 한다.
    profile = copy.deepcopy(PROFILE)  # 다른 사례의 입력을 바꾸지 않는다.
    profile["self"]["qualifications"][0]["has"] = answer  # 사용자가 선택한 답변을 넣는다.
    user_id = profiles.create(conn, _account(conn), profile)  # 해당 계정 프로필로 저장한다.
    assert profiles.load(conn, user_id)["self"]["qualifications"][0]["has"] == answer  # 미해당이 해당함으로 복원되지 않아야 한다.
    profiles.update(conn, user_id, lambda current: current["self"]["qualifications"][0].update(has="N"))  # 이미 있던 자격도 미해당으로 고친다.
    assert profiles.load(conn, user_id)["self"]["qualifications"][0]["has"] == "N"  # 재조회 후에도 미해당을 유지한다.


def test_legacy_qualification_defaults_to_yes(conn):  # 기존 has 생략 계약을 보존한다.
    profile = copy.deepcopy(PROFILE)  # 기존 입력 모양을 따로 만든다.
    profile["self"]["qualifications"][0].pop("has")  # 과거 클라이언트처럼 해당 여부를 생략한다.
    user_id = profiles.create(conn, _account(conn), profile)  # 생략 입력도 저장할 수 있어야 한다.
    assert profiles.load(conn, user_id)["self"]["qualifications"][0]["has"] == "Y"  # 기존 자격은 해당함이라는 의미를 유지한다.
