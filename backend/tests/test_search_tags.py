"""검색의 단계 태그와 색인 미리 만들기."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import search as search_router
from backend.planner import stage_tags
from backend.search import service
from backend.search.corpus import rule_stage_tags


def _rule(*conditions, subject="self"):
    return {"subject": subject, "conditions": list(conditions)}


def test_stage_tags_are_the_planners():
    """검색이 따로 세던 때 AI 조건표에서 갈리던 꼴들. 지금은 플래너 계산을 그대로 쓴다."""
    cases = [
        _rule({"field": "children_count", "op": ">=", "value": 1}),                      # 예전 검색: 태그 없음
        _rule({"field": "age", "op": "<", "value": 40}),                                  # 만 39세 이하
        _rule({"field": "marital_status", "op": "not_in", "value": ["신혼", "예비부부"]}),   # 제외 조건은 태그가 아니다
        _rule({"field": "age", "op": "<=", "value": 34}, subject="parent"),                # 부모님 제도는 youth가 아니다
        _rule({"any_of": [[{"field": "children_count", "op": ">=", "value": 2}],
                          [{"field": "marital_status", "op": "in", "value": ["예비부부"]}]]}),
    ]
    for rule in cases:
        assert rule_stage_tags(rule) == stage_tags(rule)
    assert rule_stage_tags(cases[0]) == ["child"]
    assert rule_stage_tags(cases[1]) == ["youth"]
    assert rule_stage_tags(cases[2]) == []
    assert rule_stage_tags(cases[3]) == ["parent"]


def _app():
    app = FastAPI()
    app.include_router(search_router.router)
    return app


def test_index_is_built_when_app_starts(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "get_index", lambda: calls.append(1))
    TestClient(_app())          # 앱이 뜨기 전(요청 없이 만들기만)에는 부르지 않는다
    assert calls == []
    with TestClient(_app()):
        assert calls == [1]


def test_app_starts_even_if_index_fails(monkeypatch):
    def broken():
        raise OSError("덤프 없음")

    monkeypatch.setattr(service, "get_index", broken)
    with TestClient(_app()) as client:
        assert client.get("/docs").status_code == 200
