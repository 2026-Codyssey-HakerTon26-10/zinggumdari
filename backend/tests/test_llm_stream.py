"""llm._post: 스트림이 정상 종료됐을 때만 응답으로 돌려준다."""

import json
from contextlib import contextmanager

import pytest

from backend.compiler import llm

DATA = '{"ok": true}'


def sse(*events):
    return [f"data: {json.dumps(e)}" for e in events]


START = {"type": "message_start", "message": {"model": "m", "usage": {"input_tokens": 3}}}
DELTA = {"type": "content_block_delta", "delta": {"type": "text_delta", "text": DATA}}
END = {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 2}}
STOP = {"type": "message_stop"}


@pytest.fixture
def stream(monkeypatch):
    monkeypatch.setattr(llm, "_load_env", lambda: {"CODYSSEY_API_KEY": "k"})
    calls = {"n": 0}

    def use(lines):
        class Resp:
            status_code = 200

            def iter_lines(self):
                yield from lines

        @contextmanager
        def fake(*a, **k):
            calls["n"] += 1
            yield Resp()
        monkeypatch.setattr(llm.httpx, "stream", fake)
        return calls
    return use


def test_normal_stream_returns_text(stream):
    stream(sse(START, DELTA, END, STOP))
    out = llm._post({"model": "m"}, timeout=5)
    assert out["content"][0]["text"] == DATA and out["stop_reason"] == "end_turn" and out["usage"]["output_tokens"] == 2


@pytest.mark.parametrize("events", [
    (START, DELTA),                          # 연결이 끊겨 종료 이벤트가 없다
    (START, DELTA, END),                     # stop_reason은 왔는데 message_stop이 없다
    (START, DELTA, STOP),                    # message_stop은 왔는데 stop_reason이 없다
    (START, DELTA, {"type": "message_delta", "delta": {"stop_reason": "refusal"}}, STOP),   # 허용하지 않는 종료 사유
])
def test_unfinished_stream_is_an_error(stream, events):
    calls = stream(sse(*events))
    with pytest.raises(llm.LLMError, match="정상 종료"):
        llm._post({"model": "m"}, timeout=5)
    # call_json은 한 번 더 부르고, 그래도 안 되면 실패로 보낸다(파이프라인의 실패·캐시 재생 경로)
    with pytest.raises(llm.LLMError, match="두 번 모두 실패"):
        llm.call_json("s", "c", {"type": "object"}, model="m", timeout=5)
    assert calls["n"] == 3


def test_broken_event_json_is_an_error(stream):
    stream(["data: {잘린", *sse(STOP)])
    with pytest.raises(llm.LLMError, match="스트림 이벤트"):
        llm._post({"model": "m"}, timeout=5)
