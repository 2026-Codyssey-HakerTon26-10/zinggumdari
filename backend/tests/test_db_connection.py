import backend.db as db


def test_connect_uses_database_url(monkeypatch):
    calls = {}

    def fake_connect(url, **kwargs):
        calls["url"] = url
        calls["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(db.psycopg, "connect", fake_connect)

    connection = db.connect("postgresql://example/db")

    assert connection is not None
    assert calls == {
        "url": "postgresql://example/db",
        "kwargs": {"autocommit": True},
    }