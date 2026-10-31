"""배포 주소에서 쿠키를 실어 부를 수 있게 CORS 허용 주소를 환경변수로 받는다."""

from backend.app.main import cors_origins


def test_default_is_local_frontend(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert cors_origins() == ["http://localhost:3000"]


def test_env_list_trims_and_drops_trailing_slash(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://zinggum.example.com/ , http://localhost:3000,, ")
    assert cors_origins() == ["https://zinggum.example.com", "http://localhost:3000"]


def test_wildcard_is_refused(monkeypatch):
    # 쿠키를 싣는 요청(allow_credentials)에 *를 쓰면 아무 사이트나 세션으로 API를 부른다
    monkeypatch.setenv("CORS_ORIGINS", "*")
    assert cors_origins() == ["http://localhost:3000"]
