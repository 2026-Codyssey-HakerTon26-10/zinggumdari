"""/profiles, /judge 스텁이 docs/api.md 모양으로 답하는지, 개발 모드가 아니면 닫혀 있는지, 동의를 지키는지."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


@pytest.fixture
def dev(monkeypatch):
    monkeypatch.setenv("DEV_STUB_API", "1")


def test_closed_by_default(monkeypatch):
    monkeypatch.delenv("DEV_STUB_API", raising=False)
    assert client.get("/profiles/U7f3a").status_code == 404
    assert client.post("/profiles", json={"self": {}}).status_code == 404
    assert client.post("/judge", json={}).status_code == 404


def test_profile_crud(dev):
    user_id = client.post("/profiles", json={"self": {"nickname": "지원", "birth_year": 1999}}).json()["user_id"]
    assert client.get(f"/profiles/{user_id}").json()["self"]["birth_year"] == 1999

    patched = client.patch(f"/profiles/{user_id}", json={"self": {"employment_status": "재직"}}).json()
    assert patched["self"]["employment_status"] == "재직" and patched["self"]["nickname"] == "지원"

    assert client.delete(f"/profiles/{user_id}").status_code == 204
    assert client.get(f"/profiles/{user_id}").status_code == 404


def test_new_profile_has_no_consent(dev):
    user_id = client.post("/profiles", json={"self": {"nickname": "지원"}}).json()["user_id"]
    assert client.get(f"/profiles/{user_id}").json()["consents"] == {"sensitive": False, "parent": False}


def test_sensitive_dropped_without_consent(dev):
    body = {"self": {"birth_year": 1999, "income_self": 270, "pregnant": "N"},
            "parents": [{"relation": "모", "birth_year": 1966}]}
    user_id = client.post("/profiles", json=body).json()["user_id"]
    p = client.get(f"/profiles/{user_id}").json()
    assert "income_self" not in p["self"] and "pregnant" not in p["self"]
    assert p["self"]["birth_year"] == 1999
    assert p["parents"] == []

    p = client.patch(f"/profiles/{user_id}", json={"self": {"income_self": 270}}).json()
    assert "income_self" not in p["self"]


def test_sensitive_kept_with_consent(dev):
    body = {"consents": {"sensitive": True, "parent": True}, "self": {"income_self": 270},
            "parents": [{"relation": "모", "birth_year": 1966, "ltc_grade": "없음"}]}
    user_id = client.post("/profiles", json=body).json()["user_id"]
    p = client.get(f"/profiles/{user_id}").json()
    assert p["self"]["income_self"] == 270 and p["parents"][0]["ltc_grade"] == "없음"

    p = client.patch(f"/profiles/{user_id}", json={"consents": {"sensitive": False, "parent": True}}).json()
    assert "income_self" not in p["self"] and "ltc_grade" not in p["parents"][0]   # 동의를 거두면 지운다


def test_judge_shape(dev):
    body = client.post("/judge", json={"user_id": "U7f3a"}).json()
    assert set(body) >= {"user_id", "ask", "cards", "timeline", "similar", "disclaimer"}
    card = body["cards"][0]
    assert card["verdict"] in {"eligible", "needs_check", "ineligible", "opens_later"}
    assert card["detail_url"] and card["updated"]
    assert all(c["evidence"] for c in card["conditions"])
