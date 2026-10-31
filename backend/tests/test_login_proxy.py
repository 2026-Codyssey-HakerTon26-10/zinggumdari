"""화면이 같은 출처 프록시(/api/backend → API)로 부를 때 로그인 제한이 사용자 IP별로 세는지(#66).

uvicorn은 바로 앞 주소가 FORWARDED_ALLOW_IPS(기본 127.0.0.1,::1)에 있을 때만 X-Forwarded-For로
request.client를 바꾼다. 여기서는 그 미들웨어를 그대로 씌워 확인한다. DB는 쓰지 않는다.
"""

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from backend.app.main import app
from backend.app.routers import auth as auth_router


class Recorder:
    """retry_after에 넘어온 IP를 적고 바로 429를 내서 DB까지 가지 않는다."""

    def __init__(self):
        self.ips = []

    def retry_after(self, email, ip):
        self.ips.append(ip)
        return 60


@pytest.fixture
def seen(monkeypatch):
    rec = Recorder()
    monkeypatch.setattr(auth_router, "limiter", rec)
    return rec.ips


def _login(peer, trusted="127.0.0.1,::1", forwarded=None):
    client = TestClient(ProxyHeadersMiddleware(app, trusted_hosts=trusted), client=(peer, 50000))
    headers = {"X-Forwarded-For": forwarded} if forwarded else {}
    return client.post("/auth/login", json={"email": "a@test.com", "password": "pass1234"}, headers=headers)


def test_local_proxy_passes_user_ip(seen):
    # Next 개발 서버(127.0.0.1)가 넘긴 사용자 주소로 센다
    assert _login("127.0.0.1", forwarded="203.0.113.7").status_code == 429
    assert _login("127.0.0.1", forwarded="198.51.100.9").status_code == 429
    assert seen == ["203.0.113.7", "198.51.100.9"]


def test_untrusted_peer_cannot_fake_ip(seen):
    # 믿지 않는 주소가 보낸 X-Forwarded-For는 무시한다 → 제한을 피해 가지 못한다
    _login("192.0.2.50", forwarded="203.0.113.7")
    assert seen == ["192.0.2.50"]


def test_deploy_proxy_needs_forwarded_allow_ips(seen):
    # 배포 프록시 주소를 FORWARDED_ALLOW_IPS에 넣지 않으면 모든 사용자가 프록시 주소 하나로 세진다
    _login("10.0.0.5", forwarded="203.0.113.7")
    _login("10.0.0.5", trusted="10.0.0.5", forwarded="203.0.113.7")
    assert seen == ["10.0.0.5", "203.0.113.7"]
