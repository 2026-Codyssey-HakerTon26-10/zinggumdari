"""메모리 스텁 /profiles(backend/app/routers/profiles.py)가 docs/api.md 모양으로 답하는지, 개발 모드가 아니면 닫혀 있는지,
동의를 지키는지. 서버(main.py)에는 DB 라우터(profiles_db)가 올라가므로 스텁 라우터만 올린 작은 앱으로 본다.
/judge 응답 모양은 서버 앱에서 본다(세션 의존성을 예시 프로필로 바꿔 끼움)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers import judge, profiles
from backend.engine.stub_data import EXAMPLE_PROFILE

_stub = FastAPI()
_stub.include_router(profiles.router)
client = TestClient(_stub)


@pytest.fixture
def dev(monkeypatch):
    monkeypatch.setenv("DEV_STUB_API", "1")


def test_closed_by_default(monkeypatch):
    monkeypatch.delenv("DEV_STUB_API", raising=False)
    assert client.get("/profiles/U7f3a").status_code == 404
    assert client.post("/profiles", json={"self": {}}).status_code == 404


def test_profile_crud(dev):
    user_id = client.post("/profiles", json={"self": {"nickname": "지원", "birth_date": "1999-04-15"}}).json()["user_id"]
    assert client.get(f"/profiles/{user_id}").json()["self"]["birth_date"] == "1999-04-15"

    patched = client.patch(f"/profiles/{user_id}", json={"self": {"employment_status": "재직"}}).json()
    assert patched["self"]["employment_status"] == "재직" and patched["self"]["nickname"] == "지원"

    assert client.delete(f"/profiles/{user_id}").status_code == 204
    assert client.get(f"/profiles/{user_id}").status_code == 404


def test_new_profile_has_no_consent(dev):
    user_id = client.post("/profiles", json={"self": {"nickname": "지원"}}).json()["user_id"]
    assert client.get(f"/profiles/{user_id}").json()["consents"] == {"sensitive": False, "parent": False}


def test_sensitive_dropped_without_consent(dev):
    body = {"self": {"birth_date": "1999-04-15", "income_self": 270, "pregnant": "N"},
            "parents": [{"relation": "모", "birth_date": "1966-07-03"}]}
    user_id = client.post("/profiles", json=body).json()["user_id"]
    p = client.get(f"/profiles/{user_id}").json()
    assert "income_self" not in p["self"] and "pregnant" not in p["self"]
    assert p["self"]["birth_date"] == "1999-04-15"
    assert p["parents"] == []

    p = client.patch(f"/profiles/{user_id}", json={"self": {"income_self": 270}}).json()
    assert "income_self" not in p["self"]


def test_sensitive_kept_with_consent(dev):
    body = {"consents": {"sensitive": True, "parent": True}, "self": {"income_self": 270},
            "parents": [{"relation": "모", "birth_date": "1966-07-03", "ltc_grade": "없음"}]}
    user_id = client.post("/profiles", json=body).json()["user_id"]
    p = client.get(f"/profiles/{user_id}").json()
    assert p["self"]["income_self"] == 270 and p["parents"][0]["ltc_grade"] == "없음"

    p = client.patch(f"/profiles/{user_id}", json={"consents": {"sensitive": False, "parent": True}}).json()
    assert "income_self" not in p["self"] and "ltc_grade" not in p["parents"][0]   # 동의를 거두면 지운다


def test_judge_shape():
    app.dependency_overrides[judge.own_profile] = lambda: {"account_id": "acct", "profile": EXAMPLE_PROFILE}
    try:
        body = TestClient(app).post("/judge", json={"user_id": "U7f3a"}).json()
    finally:
        app.dependency_overrides.pop(judge.own_profile, None)
    assert set(body) >= {"user_id", "ask", "cards", "timeline", "similar", "disclaimer"}
    card = body["cards"][0]
    assert card["verdict"] in {"eligible", "needs_check", "ineligible", "opens_later"}
    assert card["detail_url"] and card["updated"]
    # 엔진이 조건표의 region(API 메타데이터)으로 붙이는 「거주지 …」 줄은 원문 줄이 없다(api.md §1 region)
    assert all(c["evidence"] for c in card["conditions"] if not c["read_as"].startswith("거주지 "))


@pytest.mark.parametrize("bad", ["false", "true", 1, 0, None, [], {}])
def test_consent_must_be_bool(dev, bad):
    body = {"consents": {"sensitive": bad}, "self": {"income_self": 270}}
    assert client.post("/profiles", json=body).status_code == 422
    user_id = client.post("/profiles", json={"self": {}}).json()["user_id"]
    assert client.patch(f"/profiles/{user_id}", json={"consents": {"sensitive": bad}}).status_code == 422
    assert client.get(f"/profiles/{user_id}").json()["consents"]["sensitive"] is False


def test_sensitive_qualifications_need_consent(dev):
    quals = [{"qual_code": "청년", "target": "본인", "verified": "자기신고"},
             {"qual_code": "기초생활수급자", "target": "본인", "verified": "자기신고"}]
    user_id = client.post("/profiles", json={"self": {"qualifications": quals}}).json()["user_id"]
    assert [q["qual_code"] for q in client.get(f"/profiles/{user_id}").json()["self"]["qualifications"]] == ["청년"]

    p = client.patch(f"/profiles/{user_id}", json={"consents": {"sensitive": True}, "self": {"qualifications": quals}}).json()
    assert len(p["self"]["qualifications"]) == 2
    p = client.patch(f"/profiles/{user_id}", json={"consents": {"sensitive": False}}).json()   # 동의 철회
    assert [q["qual_code"] for q in p["self"]["qualifications"]] == ["청년"]


# 시연 프리셋(SPEC §2, §16) ---------------------------------------------------------------------

def test_presets_list(dev):
    assert client.get("/profiles/presets").json() == [
        {"id": "jiwon", "label": "지원(1999, 예비부부) + 어머니(1966)", "virtual": True}]


def test_preset_creates_new_profile_each_time(dev):
    a = client.post("/profiles/presets/jiwon").json()["user_id"]
    b = client.post("/profiles/presets/jiwon").json()["user_id"]
    assert a != b   # 매번 새 프로필. 다른 사람 프로필을 덮어쓰지 않는다
    p = client.get(f"/profiles/{a}").json()
    me, mom = p["self"], p["parents"][0]
    assert (me["nickname"], me["birth_date"], me["marital_status"], me["sigungu"]) == ("지원", "1999-04-15", "예비부부", "마포구")
    assert (me["deposit"], me["monthly_rent"], me["income_self"], me["joined_date"]) == (1000, 55, 270, "2021-03-01")
    assert (mom["relation"], mom["birth_date"], mom["sigungu"], mom["care_wanted"]) == ("모", "1966-07-03", "고양시", "Y")
    assert p["consents"] == {"sensitive": True, "parent": True}   # 가상 페르소나라 동의한 것으로 둔다
    client.patch(f"/profiles/{a}", json={"self": {"marital_status": "신혼"}})
    assert client.get(f"/profiles/{b}").json()["self"]["marital_status"] == "예비부부"


def test_unknown_preset_404(dev):
    assert client.post("/profiles/presets/nobody").status_code == 404


def test_presets_closed_by_default(monkeypatch):
    monkeypatch.delenv("DEV_STUB_API", raising=False)
    assert client.post("/profiles/presets/jiwon").status_code == 404


# 실패한 PATCH는 아무것도 바꾸지 않는다(#11 리뷰) --------------------------------------------------

@pytest.mark.parametrize("bad", [
    {"consents": {"sensitive": False}, "self": {"qualifications": [1]}},
    {"consents": {"sensitive": False}, "self": {"qualifications": "청년"}},
    {"consents": {"sensitive": False}, "self": "x"},
    {"consents": {"sensitive": False}, "parents": [1]},
    {"consents": {"sensitive": False}, "parents": {"relation": "모"}},
])
def test_rejected_patch_changes_nothing(dev, bad):
    body = {"consents": {"sensitive": True, "parent": True}, "self": {"income_self": 270},
            "parents": [{"relation": "모", "ltc_grade": "3등급"}]}
    user_id = client.post("/profiles", json=body).json()["user_id"]
    before = client.get(f"/profiles/{user_id}").json()
    assert client.patch(f"/profiles/{user_id}", json=bad).status_code == 422
    assert client.get(f"/profiles/{user_id}").json() == before


def test_withdraw_consent_clears_self_and_parents(dev):
    body = {"consents": {"sensitive": True, "parent": True}, "self": {"income_self": 270, "pregnant": "N"},
            "parents": [{"relation": "모", "ltc_grade": "3등급", "basic_pension": "Y", "birth_date": "1950-05-05"}]}
    user_id = client.post("/profiles", json=body).json()["user_id"]
    p = client.patch(f"/profiles/{user_id}", json={"consents": {"sensitive": False}}).json()
    assert "income_self" not in p["self"] and "pregnant" not in p["self"]
    assert p["parents"] == [{"relation": "모", "birth_date": "1950-05-05"}]


@pytest.mark.parametrize("bad", [{"self": "x"}, {"self": {"qualifications": [1]}}, {"parents": [1]}])
def test_rejected_post(dev, bad):
    assert client.post("/profiles", json=bad).status_code == 422
