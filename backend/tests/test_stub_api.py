"""/profiles, /judge 스텁이 docs/api.md 모양으로 답하는지."""

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_profile_crud():
    user_id = client.post("/profiles", json={"self": {"nickname": "지원", "birth_year": 1999}}).json()["user_id"]
    assert client.get(f"/profiles/{user_id}").json()["self"]["birth_year"] == 1999

    patched = client.patch(f"/profiles/{user_id}", json={"self": {"income_self": 270}}).json()
    assert patched["self"]["income_self"] == 270 and patched["self"]["nickname"] == "지원"

    assert client.delete(f"/profiles/{user_id}").status_code == 204
    assert client.get(f"/profiles/{user_id}").status_code == 404


def test_judge_shape():
    body = client.post("/judge", json={"user_id": "U7f3a"}).json()
    assert set(body) >= {"user_id", "ask", "cards", "timeline", "similar", "disclaimer"}
    card = body["cards"][0]
    assert card["verdict"] in {"eligible", "needs_check", "ineligible", "opens_later"}
    assert card["detail_url"] and card["updated"]
    assert all(c["evidence"] for c in card["conditions"])
