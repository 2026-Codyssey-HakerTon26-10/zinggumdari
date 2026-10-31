import json
from datetime import date

import httpx
import pytest

from backend.data import config, dump, load
from backend.data.deadline import is_closed, parse_deadline
from backend.data.sources import api_error, parse_xml, ssis_items, ssis_total

SSIS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<wantedList><totalCount>3</totalCount><pageNo>1</pageNo><numOfRows>2</numOfRows>
<resultCode>0</resultCode><resultMessage>SUCCESS</resultMessage>
<servList><servId>A1</servId><servNm>청년 월세</servNm><ctpvNm>서울특별시</ctpvNm></servList>
<servList><servId>A2</servId><servNm>신혼 이자</servNm><ctpvNm>서울특별시</ctpvNm></servList>
</wantedList>"""


def test_parse_xml_repeated_tags_become_list():
    p = parse_xml(SSIS_XML)
    assert ssis_total(p) == 3
    assert [x["servId"] for x in ssis_items(p)] == ["A1", "A2"]
    assert api_error(p) is None


def test_api_error_shapes():
    assert "SERVICE_KEY_IS_NOT_REGISTERED" in api_error(parse_xml(
        "<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</errMsg>"
        "<returnAuthMsg>x</returnAuthMsg></cmmMsgHeader></OpenAPI_ServiceResponse>"))
    assert api_error({"code": -401, "msg": "인증키는 필수 항목 입니다."})
    assert api_error({"errorCode": "e001", "errorMsg": "invalid api key."})
    assert api_error({"page": 1, "data": [], "totalCount": 0}) is None
    assert api_error([{"dsList": []}]) is None


@pytest.mark.parametrize("text, kind, day", [
    ("상시신청", "상시", None),
    ("2026.03.30 ~ 2026.05.29", "기간", "2026-05-29"),
    ("2026년 3월 30일부터 2026년 5월 29일까지", "기간", "2026-05-29"),
    ("예산 소진 시까지", "미정", None),
    ("", "미정", None),
    ("출생일로부터 60일 이내", "기타", None),
    ("2026년 상반기", "기간", "2026-06-30"),
    ("2026년 하반기 중 공고", "기간", "2026-12-31"),
    ("매년 3~4월(※ 자세한 사항은 옥천군 홈페이지 공고문 참고)", "기타", None),
    # 끝 날짜의 연도를 빼고 쓴 범위는 앞 날짜의 연도를 받는다(시작일을 마감으로 읽지 않는다)
    ("2026.11.1.~11.30.", "기간", "2026-11-30"),
    ("2026. 5. 11.(월) ~ 12. 4.(금)", "기간", "2026-12-04"),
    ("[3차] 2026년 10월 26일 ~ 11월 6일", "기간", "2026-11-06"),
    ("2026.12.1.~2.28.", "기간", "2027-02-28"),
    ("2026. 3. 3. ~ 11. 30.(상시신청) ※ 예산 소진 시 마감", "기간", "2026-11-30"),
    # 대상 기준일은 마감이 아니다
    ("상시 (2024.1.1. 이후 출생아)", "상시", None),
    ("2026. 10. 1. 부터 예산 소진시까지", "미정", None),
    ("태아 기형아 검사일로부터 6개월 이내(2026. 1. 1. 이후인 건에 한하여 지원)", "기타", None),
])
def test_parse_deadline(text, kind, day):
    d = parse_deadline(text)
    assert (d["type"], d["date"], d["text"]) == (kind, day, text)


def test_is_closed():
    assert is_closed(parse_deadline("2026.03.30 ~ 2026.05.29"), date(2026, 10, 31))
    assert not is_closed(parse_deadline("상시"), date(2026, 10, 31))
    assert not is_closed(parse_deadline("2026.11.1.~11.30."), date(2026, 11, 15))


@pytest.fixture
def raw(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path)
    monkeypatch.setenv("DATA_GO_KR_KEY", "abc%2Bdef%3D%3D")
    return tmp_path


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_dump_list_pages_until_total_and_hides_key(raw):
    seen = []

    def handler(req: httpx.Request):
        seen.append(req.url.params["serviceKey"])
        page = int(req.url.params["pageNo"])
        body = SSIS_XML if page == 1 else SSIS_XML.replace("A1", "A3").replace(
            "<servList><servId>A2</servId><servNm>신혼 이자</servNm><ctpvNm>서울특별시</ctpvNm></servList>", "")
        return httpx.Response(200, text=body)

    src = dump.LIST_SOURCES["ssis_local"]
    src = src.__class__(**{**src.__dict__, "page_size": 2})
    with client_for(handler) as c:
        meta = dump.dump_list(src, c, None)
    assert seen == ["abc+def==", "abc+def=="]                # 인코딩 키를 풀어서 보낸다
    assert meta["items"] == 3 and meta["pages"] == 2
    assert [x["servId"] for x in load.iter_items("ssis_local", raw)] == ["A1", "A2", "A3"]
    saved = "".join(p.read_text() for p in (raw / "ssis_local").iterdir())
    assert "abc" not in saved                                  # 키는 저장하지 않는다


def test_dump_skips_on_unregistered_key_and_keeps_old(raw):
    (raw / "lh_list").mkdir()
    (raw / "lh_list" / "page-0001.json").write_text(json.dumps([{"dsList": [{"PAN_ID": "old"}]}]))
    err = {"OpenAPI_ServiceResponse": {"cmmMsgHeader": {"errMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR", "returnAuthMsg": "x"}}}
    with client_for(lambda r: httpx.Response(200, json=err)) as c, pytest.raises(dump.Skip, match="승인 전"):
        dump.dump_list(dump.LIST_SOURCES["lh_list"], c, None)
    assert [x["PAN_ID"] for x in load.iter_items("lh_list", raw)] == ["old"]


def test_dump_without_key_skips(raw, monkeypatch, capsys):
    monkeypatch.delenv("DATA_GO_KR_KEY")
    monkeypatch.delenv("YOUTHCENTER_API_KEY", raising=False)
    assert dump.main(["--source", "youth"]) == 1
    assert "YOUTHCENTER_API_KEY 없음" in capsys.readouterr().out


def test_dump_details_resume(raw):
    (raw / "lh_list").mkdir()
    (raw / "lh_list" / "page-0001.json").write_text(json.dumps(
        [{"dsList": [{"PAN_ID": "P1", "AIS_TP_CD": "05"}, {"PAN_ID": "P2"}, {"PAN_ID": "P3"}]}]))
    calls = []

    def handler(req):
        calls.append(req.url.params["PAN_ID"])
        return httpx.Response(200, json=[{"dsAhflInfo": [{"AHFL_URL": "https://x/a.pdf"}]}])

    with client_for(handler) as c:
        dump.dump_details(dump.DETAIL_SOURCES["lh_detail"], c, 2)
        dump.dump_details(dump.DETAIL_SOURCES["lh_detail"], c, 2)
    assert calls == ["P1", "P2", "P3"]
    assert [i for i, _ in load.iter_details("lh_detail", raw)] == ["P1", "P2", "P3"]


def test_odcloud_total_prefers_match_count():
    from backend.data.sources import odcloud_total
    assert odcloud_total({"totalCount": 2929, "matchCount": 293, "data": []}) == 293
    assert odcloud_total({"totalCount": 10942, "data": []}) == 10942
