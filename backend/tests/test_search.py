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
from backend.search.index import BM25, SearchIndex, _in_region, bigrams, expand_query
from backend.search.ports import Ports, fake_judge, ports, profile_tags
from backend.search.rank import closed

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
    {"id": "upload:upload-20261031-ab12cd34:x", "source": "upload", "name": "남이 올린 청년 공고", "subject": "self",
     "review": {"status": "unreviewed"}, "conditions": []},
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
    # 엔진(#12)이 머지돼도 이 파일은 가짜 판정 기준으로 본다. 엔진 연결은 test_engine_port_*가 본다
    monkeypatch.setattr("backend.search.ports._engine_judge", lambda: None)
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
    assert not any(r.startswith("upload:") for r in rules)                  # 남의 업로드는 공용 색인에 없다
    assert by["gov24:135200000001"]["region"] == {"sido": "경기", "sigungu": "고양시"}
    assert by["gov24:135200000002"]["region"] is None and by["gov24:135200000002"]["subject"] == "parent"
    assert by["local:WLF001"]["region"] == {"sido": "부산", "sigungu": "해운대구"}
    assert "multi_child" in by["local:WLF001"]["stage_tags"]
    assert short_sido("충청북도 청주시") == "충북"


def test_region_filter_matches_full_and_short_sido():
    """덤프는 짧은 이름, 손 조건표는 "경상남도"처럼 긴 이름이라 지역 필터는 둘을 맞춰 비교한다."""
    assert _in_region({"region": {"sido": "경상남도", "sigungu": "의령군"}}, "경남")
    assert _in_region({"region": {"sido": "경남", "sigungu": "거창군"}}, "경상남도")
    assert _in_region({"region": None}, "경남")   # 전국
    assert not _in_region({"region": {"sido": "경상북도"}}, "경남")
    assert not _in_region({"region": {"sido": "서울특별시"}}, "경남")


def test_applyhome_and_lh_deadline_and_special_supply(tmp_path):
    """청약홈은 주택형 행의 특공 세대수를 공고마다 더해 요약과 단계 태그로, 청약홈과 LH는 접수 마감을 deadline으로."""
    def page(folder, data):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "page-0001.json").write_text(json.dumps({"data": data, "totalCount": len(data)}, ensure_ascii=False))
    page("applyhome_detail", [
        {"PBLANC_NO": "2026000001", "HOUSE_NM": "가나 센트럴", "HOUSE_SECD_NM": "APT", "SUBSCRPT_AREA_CODE_NM": "경기",
         "RCRIT_PBLANC_DE": "2026-10-20", "RCEPT_BGNDE": "2026-11-03", "RCEPT_ENDDE": "2026-11-05"},
        {"PBLANC_NO": "2026000002", "HOUSE_NM": "다라 신혼희망타운", "HOUSE_SECD_NM": "신혼희망타운",
         "SUBSCRPT_AREA_CODE_NM": "서울", "RCRIT_PBLANC_DE": "2026-03-02", "RCEPT_BGNDE": "2026-03-16", "RCEPT_ENDDE": "2026-03-18"},
    ])
    page("applyhome_mdl", [
        {"PBLANC_NO": "2026000001", "NWWDS_HSHLDCO": 10, "LFE_FRST_HSHLDCO": 5, "MNYCH_HSHLDCO": 0, "NWBB_HSHLDCO": 2},
        {"PBLANC_NO": "2026000001", "NWWDS_HSHLDCO": 3, "LFE_FRST_HSHLDCO": "1", "MNYCH_HSHLDCO": 4, "NWBB_HSHLDCO": 0},
        {"PBLANC_NO": "2026000002", "SPSPLY_HSHLDCO": 200},
    ])
    (tmp_path / "lh_list").mkdir()   # LH 응답은 [{"dsSch": …}, {"dsList": […]}] 모양이다
    (tmp_path / "lh_list" / "page-0001.json").write_text(json.dumps([{"dsSch": []}, {"dsList": [
        {"PAN_ID": "0001", "PAN_NM": "행복주택", "CNP_CD_NM": "서울특별시", "PAN_SS": "접수마감", "CLSG_DT": "2026.10.10"}]}],
        ensure_ascii=False))
    docs, _ = build_corpus(raw_dir=tmp_path, rules=[])
    by = {d["service_id"]: d for d in docs}
    apt, town, lh = by["applyhome:2026000001"], by["applyhome:2026000002"], by["lh:0001"]
    assert apt["fields"]["target"] == "특별공급 신혼부부 13세대, 생애최초 6세대, 다자녀 4세대, 신생아 2세대"
    assert apt["stage_tags"] == ["newlywed", "multi_child", "child"]
    assert town["stage_tags"] == ["newlywed"] and town["fields"]["target"] is None   # 신혼희망타운은 주택형 칸이 비어도 신혼
    today = date(2026, 11, 1)
    assert not closed(apt, None, today) and closed(town, None, today) and closed(lh, None, today)


def test_manual_rule_benefit_is_indexed(client):
    docs, _ = build_corpus(rules=[{**RULES[0], "benefit_text": "건설량의 15% 범위에서 특별공급"}])
    assert next(d for d in docs if d["service_id"] == "manual:subscription-newlywed")["fields"]["benefit"].startswith("건설량")


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



def _doc(name, aliases=()):
    return {"name": name, "fields": {"aliases": "\n".join(aliases)}}


def test_abbreviation_counts_for_relevance():
    """줄임말 검색도 별칭에 걸리면 관련도 첫 구간이다(로그인해 배지가 붙어도 1위가 밀리지 않게).
    실제 조건표 별칭이 "신혼 특별공급"이라 "신혼 특공"이 통째 일치하지 않던 경우."""
    from backend.search.rank import STRONG, relevance_band
    newlywed = _doc("청약 신혼부부 특별공급", ["신혼부부 특공", "신혼 특별공급"])
    multi = _doc("청약 다자녀가구 특별공급", ["다자녀 특별공급", "다자녀 특공"])
    assert relevance_band(newlywed, "신혼 특공") == STRONG
    assert relevance_band(multi, "신혼 특공") != STRONG
    assert relevance_band(multi, "다자녀 특공") == STRONG
    assert relevance_band(newlywed, "다자녀 특공") != STRONG


def _cards_judge(profile, rules, today=None):
    return {r["id"]: {"rule_id": r["id"], "verdict": "needs_check", "blocking_fields": []} for r in rules}


def test_similar_badge_from_engine(client, monkeypatch):
    seen = {}

    def similar_for(profile, cards, rules, today=None):
        seen.update(cards=cards, rules={r["id"] for r in rules})
        return {"items": [{"rule_id": "manual:seoul-newlywed-interest"}]}

    ports._judge = _cards_judge
    monkeypatch.setattr("backend.search.ports._engine_similar", lambda: similar_for)
    body = client.get("/search", params={"q": "서울 신혼부부 이자"}, headers=AS_U1).json()
    assert {r["name"]: r["badge"] for r in body["results"]}["서울 신혼부부 임차보증금 이자지원"] == "similar"
    # 검색 후보가 아니라 색인의 조건표 전부로 고른다(/judge의 비슷한 가구 묶음과 같은 제도)
    assert "manual:basic-pension" in seen["rules"] and seen["cards"]["manual:basic-pension"]["verdict"] == "needs_check"


def test_similar_badge_needs_login_and_survives_failure(client, monkeypatch):
    calls = []
    ports._judge = _cards_judge
    monkeypatch.setattr("backend.search.ports._engine_similar", lambda: lambda *a, **k: calls.append(1) or 1 / 0)
    assert client.get("/search", params={"q": "서울 신혼부부 이자"}).status_code == 200
    assert calls == []   # 로그인하지 않으면 부르지 않는다
    body = client.get("/search", params={"q": "서울 신혼부부 이자"}, headers=AS_U1).json()
    assert calls == [1] and "similar" not in {r["badge"] for r in body["results"]}


def test_similar_badge_without_population_cache(client, monkeypatch, tmp_path):
    from backend.engine import similar
    monkeypatch.setattr(similar, "POP_DIR", tmp_path / "no-population")
    similar.clear_cache()
    ports._judge = _cards_judge
    body = client.get("/search", params={"q": "서울 신혼부부 이자"}, headers=AS_U1).json()
    assert "similar" not in {r["badge"] for r in body["results"]}
    similar.clear_cache()


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
    seen = {}

    def engine(profile, rules, today=None):
        seen["today"] = today
        return {"cards": [{"rule_id": "a", "verdict": "opens_later"}]}

    p._judge = engine
    out = p.verdicts({}, [{"id": "a"}, {"id": "b"}, {"id": "c", "subject": "parent"}], date(2031, 1, 15))
    assert out == {"a": "opens_later", "b": "ineligible", "c": "needs_check"}
    assert seen["today"] == date(2031, 1, 15)                       # ?today=가 엔진까지 간다


def test_engine_port_reads_rule_id_dict():
    """#12의 judge()는 {rule_id: 카드}를 돌려준다. 부모님 탭을 안 연 카드(no_subject)는 탈락이 아니다."""
    p = Ports()
    p._judge = lambda profile, rules, today=None: {
        "a": {"verdict": "eligible"}, "b": {"rule_id": "b", "verdict": "ineligible"},
        "c": {"verdict": "ineligible", "no_subject": True}}
    out = p.verdicts({}, [{"id": "a"}, {"id": "b"}, {"id": "c", "subject": "parent"}, {"id": "d"}])
    assert out == {"a": "eligible", "b": "ineligible", "c": "needs_check", "d": "ineligible"}


def test_criteria_text_keeps_evidence_when_other_text_present(tmp_path, monkeypatch):
    from backend.notices import store
    from backend.search.corpus import from_rule
    monkeypatch.setattr(config, "NOTICES_DIR", tmp_path)
    store.register_text("청약통장 가입기간 6개월 이상\n순자산 기준 이하", "ai-doc", "api", None, "t", notices_dir=tmp_path)
    rule = {"id": "gov24:X", "name": "주거 지원", "conditions": [
        {"field": "subscription_months", "op": ">=", "value": 6, "evidence": ["ai-doc:l1"], "status": "auto_verified"},
        {"field": "other", "text": "원문 조건 미반영", "reason": "unaccounted", "evidence": ["ai-doc:l2"], "status": "needs_review"}]}
    text = from_rule(rule)["fields"]["criteria"]
    assert "청약통장 가입기간 6개월 이상" in text and "순자산 기준 이하" in text and "원문 조건 미반영" in text


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


@pytest.mark.parametrize("path", ["/search?q=%EC%8B%A0", "/search/?q=%EC%8B%A0", "/Search?q=%EC%8B%A0"])
def test_search_query_not_in_access_log(path):
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("127.0.0.1:1", "GET", path, "1.1", 200), None)
    for f in logging.getLogger("uvicorn.access").filters:
        f.filter(rec)
    assert "%EC" not in rec.getMessage()


def test_access_log_keeps_other_paths():
    rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                            ("127.0.0.1:1", "GET", "/notices/x?page=2", "1.1", 200), None)
    for f in logging.getLogger("uvicorn.access").filters:
        f.filter(rec)
    assert "/notices/x?page=2" in rec.getMessage()


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
