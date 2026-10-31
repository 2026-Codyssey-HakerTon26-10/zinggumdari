"""검색(backend/search)과 배지."""

import json
import logging
import time
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import search as search_router
from backend.data import config
from backend.search import service
from backend.search.corpus import build_corpus, rule_stage_tags, short_sido
from backend.search.index import BM25, SearchIndex, bigrams, expand_query
from backend.search.ports import Ports, fake_judge, ports, profile_tags

R = {"status": "reviewed"}
REVIEWED = {"review": {"status": "reviewed"}}
RULES = [
    {"id": "manual:subscription-newlywed", "source": "manual", "name": "신혼부부 특별공급", "org": "국토교통부", "region": None,
     "subject": "self", "aliases": ["신혼 특공"], **REVIEWED,
     "conditions": [{"field": "is_homeless", "op": "==", "value": "Y", "quote": "무주택세대구성원", **R},
                    {"field": "marriage_years", "op": "<=", "value": 7, "quote": "혼인기간 7년 이내", **R}]},
    {"id": "manual:hug-buttimok-youth", "source": "manual", "name": "청년전용 버팀목전세자금", "org": "주택도시기금",
     "region": None, "subject": "self", "aliases": ["청년 버팀목"], **REVIEWED,
     "conditions": [{"field": "age", "op": "<=", "value": 34, "quote": "만 19세 이상 만 34세 이하", **R},
                    {"field": "is_homeless", "op": "==", "value": "Y", "quote": "무주택 세대주", **R}]},
    {"id": "manual:basic-pension", "source": "manual", "name": "기초연금", "org": "보건복지부", "region": None,
     "subject": "parent", "aliases": [], **REVIEWED,
     "conditions": [{"field": "age", "op": ">=", "value": 65, "quote": "만 65세 이상", **R},
                    {"field": "income_recognized", "op": "<=", "value": 247, "income_basis": "recognized", "quote": "소득인정액", **R}]},
    {"id": "manual:youth-rent", "source": "manual", "name": "청년월세 한시 특별지원", "subject": "self", **REVIEWED,
     "conditions": [{"field": "apply_date", "op": "<=", "value": "2026-05-29", "quote": "2026. 5. 29.까지", **R}]},
    {"id": "manual:seoul-newlywed-interest", "source": "manual", "name": "서울 신혼부부 임차보증금 이자지원",
     "subject": "self", "region": {"sido": "서울", "sigungu": None}, "same_as": ["gov24:WII000001"], **REVIEWED,
     "conditions": [{"field": "marital_status", "op": "in", "value": ["신혼", "기혼"], "quote": "신혼부부", **R}]},
    {"id": "gov24:WII000001", "source": "gov24", "name": "AI가 읽은 서울 신혼", "subject": "self", "review": {"status": "unreviewed"},
     "conditions": [{"field": "age", "op": "<=", "value": 39, "evidence": ["x:l1"], "status": "auto_verified"}]},
    {"id": "gov24:WII000009", "source": "gov24", "name": "AI가 읽은 청년 주거", "subject": "self", "review": {"status": "unreviewed"},
     "conditions": [{"field": "age", "op": "<=", "value": 39, "evidence": ["x:l1"], "status": "auto_verified"}]},
]

GOV24_PAGE = {"page": 1, "perPage": 500, "totalCount": 3, "currentCount": 3, "data": [
    {"서비스ID": "WII000001", "서비스명": "서울 신혼부부 임차보증금 이자 지원", "소관기관명": "서울특별시", "소관기관유형": "지방자치단체",
     "지원대상": "혼인 7년 이내 신혼부부", "상세조회URL": "https://www.gov.kr/portal/rcvfvrSvc/dtlEx/WII000001", "수정일시": "20261020"},
    {"서비스ID": "135200000001", "서비스명": "출산 축하금", "소관기관명": "경기도 고양시", "지원대상": "출산 가정", "선정기준": "고양시 거주"},
    {"서비스ID": "135200000002", "서비스명": "노인 일자리", "소관기관명": "보건복지부", "소관기관유형": "중앙행정기관", "지원대상": "만 65세 이상 어르신"},
]}
SSIS_XML = """<wantedList><totalCount>1</totalCount><resultCode>0</resultCode>
<servList><servId>WLF001</servId><servNm>다자녀 가정 양육비</servNm><ctpvNm>부산광역시</ctpvNm><sggNm>해운대구</sggNm>
<servDgst>셋째 이상 다자녀 가정 양육비 지원</servDgst><lastModYmd>20261001</lastModYmd></servList></wantedList>"""

PERSONA = {"user_id": "U1", "self": {"birth_year": 1999, "sido": "서울", "marital_status": "예비부부", "is_homeless": "Y",
                                     "children_count": 0}, "parents": [{"relation": "모", "birth_year": 1966}]}
TODAY = date(2026, 10, 31)
AS_U1 = {"x-test-profile": "U1"}   # 테스트용 가짜 세션(로그인한 U1)


@pytest.fixture
def client(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    (raw / "gov24_serviceList").mkdir(parents=True)
    (raw / "gov24_serviceList" / "page-0001.json").write_text(json.dumps(GOV24_PAGE, ensure_ascii=False))
    (raw / "ssis_local").mkdir()
    (raw / "ssis_local" / "page-0001.xml").write_text(SSIS_XML)
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    for r in RULES:
        (rules_dir / f"{r['id'].replace(':', '_')}.json").write_text(json.dumps(r, ensure_ascii=False))
    monkeypatch.setattr(config, "RAW_DIR", raw)
    monkeypatch.setattr(config, "RULES_DIRS", (rules_dir,))
    monkeypatch.setattr(config, "DOCS_DIR", tmp_path)            # stage_keywords.json 없음 → 기본값
    monkeypatch.setattr(config, "NOTICES_DIR", tmp_path / "notices")
    service.reset_index()
    saved = dict(ports.__dict__)
    ports.session_user = lambda req: {"account_id": f"A-{pid}", "profile_id": pid} if (pid := req.headers.get("x-test-profile")) else None
    ports.load_profile = lambda pid: PERSONA if pid == "U1" else None
    app = FastAPI()
    app.include_router(search_router.router)
    yield TestClient(app)
    ports.__dict__.update(saved)
    service.reset_index()


def names(body):
    return [r["name"] for r in body["results"]]


def test_bigrams_and_expand():
    assert bigrams("신혼부부 특공") == ["신혼", "혼부", "부부", "특공"]
    rules = {r["id"]: r for r in RULES}
    assert "특별공급" in expand_query("신혼 특공", rules)
    assert "청년전용 버팀목전세자금" in expand_query("청년버팀목", rules)


def test_bm25_ranks_rare_term_higher():
    bm = BM25([["신혼", "부부"], ["청년", "부부"], ["청년", "청년", "주거"]])
    s = bm.get_scores(["신혼"])
    assert s[0] > 0 and s[1] == 0 and s[2] == 0
    assert bm.get_scores(["청년"])[2] > bm.get_scores(["청년"])[1]


def test_rule_stage_tags_from_conditions():
    tags = {r["id"]: rule_stage_tags(r) for r in RULES}
    assert tags["manual:hug-buttimok-youth"] == ["youth"]
    assert tags["manual:subscription-newlywed"] == ["newlywed"]
    assert tags["manual:basic-pension"] == ["parent"]
    branchy = {"conditions": [{"any_of": [[{"field": "children_count", "op": ">=", "value": 2}],
                                          [{"field": "marital_status", "op": "in", "value": ["예비부부"]}]]}]}
    assert set(rule_stage_tags(branchy)) == {"marriage_planned", "multi_child"}


def test_corpus_same_as_and_regions(client):
    docs, rules = build_corpus()
    by = {d["service_id"]: d for d in docs}
    joined = by["gov24:WII000001"]
    assert joined["rule_id"] == "manual:seoul-newlywed-interest"            # 손 조건표가 이긴다
    assert joined["name"] == "서울 신혼부부 임차보증금 이자지원" and joined["detail_url"].endswith("WII000001")
    assert "gov24:WII000001" not in rules and "gov24:WII000009" in rules     # same_as에 걸린 AI 조건표는 뺀다
    assert by["gov24:135200000001"]["region"] == {"sido": "경기", "sigungu": "고양시"}
    assert by["gov24:135200000002"]["region"] is None and by["gov24:135200000002"]["subject"] == "parent"
    assert by["local:WLF001"]["region"] == {"sido": "부산", "sigungu": "해운대구"}
    assert "multi_child" in by["local:WLF001"]["stage_tags"]
    assert short_sido("충청북도 청주시") == "충북"


@pytest.mark.parametrize("q, want", [("신혼 특공", "신혼부부 특별공급"), ("버팀목", "청년전용 버팀목전세자금"), ("기초연금", "기초연금")])
def test_spec_queries_in_top5(client, q, want):
    assert want in names(client.get("/search", params={"q": q}).json())[:5]


def test_badges_with_profile(client):
    body = client.get("/search", params={"q": "신혼 특공 버팀목 기초연금 청년월세 청년 주거", "today": "2026-10-31"},
                      headers=AS_U1).json()
    badge = {r["name"]: r["badge"] for r in body["results"]}
    assert badge["청년전용 버팀목전세자금"] == "eligible"           # 26~27세, 무주택
    assert badge["신혼부부 특별공급"] == "ineligible"              # 혼인신고 전이면 혼인 기간 조건 탈락
    assert badge["기초연금"] == "ineligible"                       # 어머니 59~60세. 진짜 엔진은 opens_later 자리
    assert badge["청년월세 한시 특별지원"] == "ineligible"          # 접수 끝난 함정
    assert badge["AI가 읽은 청년 주거"] == "needs_check"            # 검수 전 AI 조건표는 eligible이 안 된다
    assert body["judge"] == "fake"


def test_anonymous_gets_no_personal_badge(client):
    body = client.get("/search", params={"q": "출산 축하금"}).json()
    assert body["results"][0]["name"] == "출산 축하금" and body["results"][0]["badge"] == "no_rule"
    assert body["nudge"] is None
    body = client.get("/search", params={"q": "버팀목"}).json()
    assert {r["name"]: r["badge"] for r in body["results"]}["청년전용 버팀목전세자금"] is None


def test_user_id_query_needs_matching_login(client):
    assert client.get("/search", params={"q": "버팀목", "user_id": "U1"}).status_code == 401
    assert client.get("/search", params={"q": "버팀목", "user_id": "U2"}, headers=AS_U1).status_code == 403
    assert client.get("/search", params={"q": "버팀목", "user_id": "U1"}, headers=AS_U1).status_code == 200


def test_similar_badge(client):
    ports.similar_rule_ids = lambda uid: {"manual:seoul-newlywed-interest"}
    ports.load_profile = lambda pid: {"self": {"birth_year": 1999}}
    body = client.get("/search", params={"q": "서울 신혼부부 이자"}, headers={"x-test-profile": "x"}).json()
    assert {r["name"]: r["badge"] for r in body["results"]}["서울 신혼부부 임차보증금 이자지원"] == "similar"


def test_filters(client):
    assert all("parent" in r["stage_tags"] for r in client.get("/search", params={"q": "연금 노인", "tag": "parent"}).json()["results"])
    assert "기초연금" not in names(client.get("/search", params={"q": "기초연금", "subject": "self"}).json())
    assert "다자녀 가정 양육비" not in names(client.get("/search", params={"q": "다자녀 양육비", "region": "서울"}).json())
    assert "다자녀 가정 양육비" in names(client.get("/search", params={"q": "다자녀 양육비", "region": "부산광역시"}).json())


def test_nudge(client):
    ports.load_profile = lambda pid: {"self": {"birth_year": 1999, "marital_status": "미혼", "children_count": 0}}
    body = client.get("/search", params={"q": "신혼부부"}, headers={"x-test-profile": "x"}).json()
    assert body["nudge"]["missing_tag"] == "newlywed" and body["nudge"]["options"][-1]["set"] is None


def test_engine_port_reads_cards():
    p = Ports()
    p._judge = lambda profile, rules: {"cards": [{"rule_id": "a", "verdict": "opens_later"}]}
    out = p.verdicts({}, [{"id": "a"}, {"id": "b"}, {"id": "c", "subject": "parent"}])
    assert out == {"a": "opens_later", "b": "ineligible", "c": "needs_check"}


def test_fake_judge_age_boundary_and_any_of():
    rule = {**REVIEWED, "conditions": [{"field": "age", "op": "<=", "value": 26, **R}]}
    assert fake_judge(PERSONA, rule, TODAY) == "needs_check"      # 1999년생은 26 또는 27, 경계는 확인 필요
    rule = {**REVIEWED, "conditions": [{"field": "age", "op": "<=", "value": 27, **R}]}
    assert fake_judge(PERSONA, rule, TODAY) == "eligible"
    rule = {**REVIEWED, "conditions": [{"any_of": [[{"field": "is_homeless", "op": "==", "value": "N"}],
                                                   [{"field": "sido", "op": "==", "value": "서울"}]], **R}]}
    assert fake_judge(PERSONA, rule, TODAY) == "eligible"
    rule = {**REVIEWED, "conditions": [{"field": "age", "op": "<=", "value": 20, "status": "needs_review"}]}
    assert fake_judge(PERSONA, rule, TODAY) == "needs_check"
    assert profile_tags(PERSONA, TODAY) == {"youth", "marriage_planned", "homeless", "parent"}


def test_search_query_not_in_access_log():
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("127.0.0.1:1", "GET", "/search?q=%EC%8B%A0", "1.1", 200), None)
    for f in logging.getLogger("uvicorn.access").filters:
        f.filter(rec)
    assert "%EC" not in rec.getMessage()


def test_search_speed_10k_docs():
    docs = [{"service_id": f"s{i}", "rule_id": None, "name": f"제도 {i} 청년 주거 지원 사업", "org": "기관", "region": None,
             "subject": "self", "stage_tags": [], "detail_url": None, "updated": None, "source": "x",
             "fields": {"target": "만 19세 이상 39세 이하 무주택 세대주 신혼부부 출산 가정 " * 3}} for i in range(10000)]
    idx = SearchIndex(docs, {})
    start = time.perf_counter()
    assert idx.search("신혼 특공")
    assert time.perf_counter() - start < 1.0


def test_exact_name_beats_long_mentions():
    long = {"service_id": "a", "rule_id": None, "name": "기초연금", "org": None, "region": None, "subject": "parent",
            "stage_tags": [], "detail_url": None, "updated": None, "source": "x",
            "fields": {"target": "만 65세 이상 어르신 " * 40 + "기초연금"}}
    others = [{**long, "service_id": f"o{i}", "name": f"노인 목욕비 {i}", "fields": {"target": "기초연금 수급자 기초연금"}}
              for i in range(5)]
    idx = SearchIndex([*others, long], {})
    assert idx.search("기초연금")[0][0]["service_id"] == "a"
