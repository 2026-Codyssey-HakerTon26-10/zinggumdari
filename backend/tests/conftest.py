import os

import pytest


@pytest.fixture(autouse=True)
def _no_repo_env(monkeypatch, tmp_path):
    """테스트가 레포 루트 .env(키, ZINGGUM_OCR)를 읽지 않게 한다. 실제 호출 테스트(ZINGGUM_LIVE=1)는 그대로 둔다."""
    if os.environ.get("ZINGGUM_LIVE") != "1":
        monkeypatch.setenv("ZINGGUM_ENV_FILE", str(tmp_path / "none.env"))
