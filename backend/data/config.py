"""레포 경로와 .env 읽기. 백엔드 2 모듈이 같이 쓴다."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
NOTICES_DIR = DATA_DIR / "notices"
RULES_DIRS = (ROOT / "rules" / "manual", ROOT / "rules" / "compiled", ROOT / "rules" / "uploads")   # uploads는 사용자 업로드, 커밋 안 함
DOCS_DIR = ROOT / "docs"

load_dotenv(ROOT / ".env")


def env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def data_go_kr_key() -> str | None:
    """data.go.kr 키는 인코딩 키와 디코딩 키 두 벌이다.

    httpx가 쿼리를 다시 인코딩하므로 인코딩 키(%2B 등)를 넣으면 두 번 인코딩된다.
    어느 쪽을 넣어도 되게 풀어서 돌려준다.
    """
    key = env("DATA_GO_KR_KEY")
    return unquote(key) if key and "%" in key else key
