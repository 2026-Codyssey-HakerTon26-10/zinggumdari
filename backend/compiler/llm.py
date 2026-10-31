"""네이토 API(대회 지급, Anthropic 방식) 호출. 공고 원문만 보낸다. 사용자 입력은 보내지 않는다.

- 키와 모델은 레포 루트 `.env`에서 읽는다(`CODYSSEY_API_KEY`, `CODYSSEY_BASE_URL`, `LLM_MODEL`, `LLM_MODEL_BULK`, `LLM_MODEL_OCR`).
  다른 곳의 .env를 쓰려면 `ZINGGUM_ENV_FILE`에 경로를 준다.
- 출력은 JSON 스키마 강제 출력(structured outputs)으로 받고 temperature는 0이다.
- 응답이 잘리거나(최대 토큰) 오류가 나면 한 번만 다시 부른다(SPEC §9.2).
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_URL = "https://copa.codyssey.kr"
DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MODEL_BULK = "claude-haiku-4"
STRUCTURED_BETA = "structured-outputs-2025-11-13"


class LLMError(RuntimeError):
    pass


def _load_env() -> dict[str, str]:
    path = Path(os.environ.get("ZINGGUM_ENV_FILE") or REPO_ROOT / ".env")
    out: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    # 환경 변수가 .env보다 우선
    for k in ("CODYSSEY_API_KEY", "CODYSSEY_BASE_URL", "LLM_MODEL", "LLM_MODEL_BULK", "LLM_MODEL_OCR"):
        if os.environ.get(k):
            out[k] = os.environ[k]
    return out


def model_name(kind: str = "main") -> str:
    """kind: main(시연·평가) | bulk(대량 추출) | ocr(스캔 글자 인식)."""
    env = _load_env()
    main = env.get("LLM_MODEL") or DEFAULT_MODEL
    if kind == "bulk":
        return env.get("LLM_MODEL_BULK") or DEFAULT_MODEL_BULK
    if kind == "ocr":
        return env.get("LLM_MODEL_OCR") or main
    return main


def available() -> bool:
    return bool(_load_env().get("CODYSSEY_API_KEY"))


@dataclass
class LLMResult:
    data: dict                      # 스키마대로 파싱한 출력
    raw_text: str                   # 모델이 낸 문자열 그대로
    model: str                      # 응답의 실제 모델명
    usage: dict = field(default_factory=dict)
    retries: int = 0
    seconds: float = 0.0


def _post(body: dict, *, timeout: float) -> dict:
    env = _load_env()
    key = env.get("CODYSSEY_API_KEY")
    if not key:
        raise LLMError("CODYSSEY_API_KEY가 없습니다. 레포 루트 .env에 넣으세요")
    base = (env.get("CODYSSEY_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": STRUCTURED_BETA,
        "content-type": "application/json",
    }
    r = httpx.post(f"{base}/v1/messages", headers=headers, json=body, timeout=timeout)
    if r.status_code != 200:
        raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def call_json(system: str, content: str | list, schema: dict, *, model: str | None = None,
              max_tokens: int = 16000, timeout: float = 600.0) -> LLMResult:
    """스키마를 강제한 JSON 한 번. content는 문자열 또는 Anthropic content 블록 목록."""
    model = model or model_name("main")
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0,
        "system": system,
        "messages": [{"role": "user", "content": content}],
        "output_format": {"type": "json_schema", "schema": schema},
    }
    last: Exception | None = None
    t0 = time.time()
    for attempt in range(2):
        try:
            resp = _post(body, timeout=timeout)
            if resp.get("stop_reason") == "max_tokens":
                raise LLMError("응답이 최대 토큰에서 잘렸습니다")
            text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
            data = json.loads(text)
            return LLMResult(data=data, raw_text=text, model=resp.get("model", model), usage=resp.get("usage", {}),
                             retries=attempt, seconds=round(time.time() - t0, 1))
        except (LLMError, httpx.HTTPError, json.JSONDecodeError) as e:
            last = e
    raise LLMError(f"두 번 모두 실패: {last}")


OCR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"lines": {"type": "array", "items": {"type": "string"}}},
    "required": ["lines"],
}
OCR_SYSTEM = (
    "너는 스캔된 한국어 공고문 한 쪽을 글자 그대로 옮기는 전사기다. 보이는 순서(위→아래, 왼→오른)대로 한 줄씩 적는다. "
    "고치거나 요약하거나 빠진 글자를 짐작해 채우지 않는다. 숫자, 단위, 기호(○, -, ※, %, ~)는 보이는 그대로 쓴다. "
    "표는 한 행을 한 줄로 쓰고 칸 사이에 ' | '를 넣는다. 읽을 수 없는 글자는 □로 쓴다."
)


def ocr_page(png: bytes, *, model: str | None = None) -> LLMResult:
    """스캔 PDF 한 쪽 이미지를 줄 목록으로 옮긴다. 좌표는 없다."""
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png).decode()}},
        {"type": "text", "text": "이 쪽의 글자를 줄 단위로 옮겨라."},
    ]
    return call_json(OCR_SYSTEM, content, OCR_SCHEMA, model=model or model_name("ocr"), max_tokens=8000)
