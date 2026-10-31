"""프로필 계산 칸 derived(api.md §2): 만 나이 두 값, 부부합산 소득, 태그, 소득 구간. 저장하지 않고 응답 때 계산한다."""

from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import profiles
from backend.engine.derive import derive
from backend.engine.stub_data import EXAMPLE_PROFILE

TODAY = date(2026, 11, 1)


def test_example_profile_matches_api_example():
    d = derive(EXAMPLE_PROFILE, TODAY)
    want = EXAMPLE_PROFILE["derived"]
    assert (d["age"], d["income_couple"], d["tags"]) == (want["age"], want["income_couple"], want["tags"])
    assert d["income_band_median"] == pytest.approx(270 / 256.4238 * 100, abs=0.1)   # 1인 가구 270만 원 → 약 105%


def test_tags():
    def tags(**me):
        return derive({"self": me}, TODAY)["tags"]
    assert tags(birth_year=1999, marital_status="미혼") == ["youth"]
    assert tags(birth_year=1996, marital_status="신혼") == ["youth", "newlywed"]          # 30세 신혼은 청년·신혼 둘 다
    assert tags(birth_year=1980, marital_status="기혼", children_count=1) == ["child"]
    assert tags(birth_year=1990, marital_status="기혼", children_count=3, is_homeless="Y") == ["youth", "multi_child", "homeless"]
    assert tags(birth_year=2010) == []                                                   # 만 15·16세는 청년 아님
    assert tags() == []


def test_income_couple_and_band():
    d = derive({"self": {"marital_status": "신혼", "income_self": 300, "income_spouse": 200,
                         "income_household": 500, "household_size": 2},
                "consents": {"sensitive": True}}, TODAY)
    assert d["income_couple"] == 500
    assert d["income_band_median"] == pytest.approx(500 / 419.9292 * 100, abs=0.1)
    assert d["income_band_urban"] is None   # 도시근로자 기준표가 없다


def test_unknown_values_stay_none():
    d = derive({"self": {"marital_status": "예비부부", "income_self": 270}}, TODAY)
    assert d["income_couple"] is None and d["income_band_median"] is None and d["age"] is None


def test_get_profile_has_derived(monkeypatch):
    monkeypatch.setenv("DEV_STUB_API", "1")
    app = FastAPI()
    app.include_router(profiles.router)   # 메모리 스텁. DB 경로는 test_profiles_judge_db
    client = TestClient(app)
    user_id = client.post("/profiles", json={"self": {"birth_year": 1996, "marital_status": "신혼"}}).json()["user_id"]
    body = client.get(f"/profiles/{user_id}?today=2026-11-01").json()
    assert body["derived"]["tags"] == ["youth", "newlywed"] and body["derived"]["age"] == [29, 30]
    # 저장하지 않고 응답 때 계산한다: 칸을 바꾸면 derived도 바뀐다
    body = client.patch(f"/profiles/{user_id}", json={"self": {"children_count": 2}}).json()
    assert "multi_child" in body["derived"]["tags"]
    preset = client.post("/profiles/presets/jiwon").json()["user_id"]
    assert client.get(f"/profiles/{preset}").json()["derived"]["tags"] == ["youth", "marriage_planned", "homeless"]
