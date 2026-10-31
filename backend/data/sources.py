"""공공데이터 소스 정의와 응답 파싱.

덤프(dump.py)와 읽기(load.py)가 같은 정의를 쓴다. 엔드포인트 경로는 2026-10-31에
키 없이 호출해 확인했다(data.go.kr은 없는 경로면 NO_OPENAPI_SERVICE_ERROR, 있는 경로면
SERVICE_KEY_IS_NULL을 준다). api.odcloud.kr(행안부 혜택, 청약홈)는 키 없이는 구분이 안 돼
첫 응답으로 확인한다.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Callable

DATA_GO_KR = "DATA_GO_KR_KEY"
YOUTHCENTER = "YOUTHCENTER_API_KEY"


def parse_xml(text: str) -> dict:
    """XML을 dict로. 같은 태그가 여러 번 나오면 리스트, 잎은 문자열."""

    def walk(el: ET.Element) -> Any:
        children = list(el)
        if not children:
            return (el.text or "").strip()
        out: dict[str, Any] = {}
        for child in children:
            value = walk(child)
            if child.tag in out:
                if not isinstance(out[child.tag], list):
                    out[child.tag] = [out[child.tag]]
                out[child.tag].append(value)
            else:
                out[child.tag] = value
        return out

    root = ET.fromstring(text)
    return {root.tag: walk(root)}


def parse(fmt: str, text: str) -> Any:
    return parse_xml(text) if fmt == "xml" else json.loads(text)


def as_list(value: Any) -> list:
    if value is None or value == "":
        return []
    return value if isinstance(value, list) else [value]


def to_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def api_error(parsed: Any) -> str | None:
    """응답 본문 안의 오류. 없으면 None. data.go.kr은 200으로 오류를 줄 때가 있다."""
    if isinstance(parsed, dict):
        header = parsed.get("OpenAPI_ServiceResponse")
        if isinstance(header, dict):
            msg = header.get("cmmMsgHeader", header)
            return f"{msg.get('errMsg')} ({msg.get('returnAuthMsg')})"
        if "code" in parsed and to_int(parsed.get("code")) not in (None, 0) and "data" not in parsed:
            return f"{parsed.get('code')} {parsed.get('msg')}"
        if parsed.get("errorCode"):
            return f"{parsed.get('errorCode')} {parsed.get('errorMsg')}"
        if parsed.get("resultCode") not in (None, "", "0", "00", 200, "200", "SUCCESS"):
            return f"{parsed.get('resultCode')} {parsed.get('resultMessage')}"
        for value in parsed.values():
            if isinstance(value, dict) and value.get("resultCode") not in (None, "", "0", "00"):
                return f"{value.get('resultCode')} {value.get('resultMessage')}"
    return None


def lh_dataset(parsed: Any, name: str) -> list:
    """LH 응답은 [{"dsSch": …}, {"dsList": […], "resHeader": …}] 모양이다. 이름으로 찾는다."""
    for block in as_list(parsed):
        if isinstance(block, dict) and name in block:
            return as_list(block[name])
    return []


def odcloud_items(p: Any) -> list:
    return as_list(p.get("data")) if isinstance(p, dict) else []


def odcloud_total(p: Any) -> int | None:
    """cond[...]로 거르면 totalCount는 거르기 전 전체, matchCount가 걸러진 수다(청약홈 2026 공고: 2929 / 293)."""
    if not isinstance(p, dict):
        return None
    return to_int(p.get("matchCount")) if p.get("matchCount") is not None else to_int(p.get("totalCount"))


def ssis_root(p: Any) -> dict:
    if isinstance(p, dict) and len(p) == 1:
        inner = next(iter(p.values()))
        if isinstance(inner, dict):
            return inner
    return p if isinstance(p, dict) else {}


def ssis_items(p: Any) -> list:
    return as_list(ssis_root(p).get("servList"))


def ssis_total(p: Any) -> int | None:
    return to_int(ssis_root(p).get("totalCount"))


def lh_items(p: Any) -> list:
    return lh_dataset(p, "dsList")


def lh_total(p: Any) -> int | None:
    rows = lh_items(p)
    return to_int(rows[0].get("ALL_CNT")) if rows else None


def youth_items(p: Any) -> list:
    result = p.get("result", {}) if isinstance(p, dict) else {}
    return as_list(result.get("youthPolicyList"))


def youth_total(p: Any) -> int | None:
    result = p.get("result", {}) if isinstance(p, dict) else {}
    return to_int((result.get("pagging") or {}).get("totCount"))


@dataclass(frozen=True)
class ListSource:
    """페이지로 넘기는 목록 API 하나."""

    name: str
    dataset: str
    url: str
    fmt: str
    key_env: str
    key_param: str
    page_param: str
    size_param: str
    page_size: int
    items: Callable[[Any], list]
    total: Callable[[Any], int | None]
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DetailSource:
    """목록 덤프의 항목마다 한 번씩 부르는 상세 API."""

    name: str
    dataset: str
    url: str
    fmt: str
    key_env: str
    key_param: str
    parent: str
    item_id: Callable[[dict], str | None]
    params: Callable[[dict], dict]
    default_limit: int


ODCLOUD_GOV24 = "https://api.odcloud.kr/api/gov24/v3"
ODCLOUD_APPLYHOME = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"
SSIS = "https://apis.data.go.kr/B554287"
LH = "https://apis.data.go.kr/B552555"


def _gov24(endpoint: str) -> ListSource:
    return ListSource(
        name=f"gov24_{endpoint}", dataset="15113968", url=f"{ODCLOUD_GOV24}/{endpoint}", fmt="json",
        key_env=DATA_GO_KR, key_param="serviceKey", page_param="page", size_param="perPage",
        page_size=500, items=odcloud_items, total=odcloud_total,
    )


def _lh_params(item: dict) -> dict:
    return {
        "SPL_INF_TP_CD": item.get("SPL_INF_TP_CD"),
        "CCR_CNNT_SYS_DS_CD": item.get("CCR_CNNT_SYS_DS_CD"),
        "PAN_ID": item.get("PAN_ID"),
        "UPP_AIS_TP_CD": item.get("UPP_AIS_TP_CD"),
        "AIS_TP_CD": item.get("AIS_TP_CD"),
    }


LIST_SOURCES: dict[str, ListSource] = {
    s.name: s
    for s in [
        _gov24("serviceList"),
        _gov24("serviceDetail"),
        _gov24("supportConditions"),
        ListSource(
            name="ssis_local", dataset="15108347", url=f"{SSIS}/LocalGovernmentWelfareInformations/LcgvWelfarelist",
            fmt="xml", key_env=DATA_GO_KR, key_param="serviceKey", page_param="pageNo", size_param="numOfRows",
            page_size=500, items=ssis_items, total=ssis_total,
        ),
        ListSource(
            name="ssis_central", dataset="15090532", url=f"{SSIS}/NationalWelfareInformationsV001/NationalWelfarelistV001",
            fmt="xml", key_env=DATA_GO_KR, key_param="serviceKey", page_param="pageNo", size_param="numOfRows",
            page_size=500, items=ssis_items, total=ssis_total, extra={"callTp": "L", "srchKeyCode": "003"},
        ),
        ListSource(
            name="applyhome_detail", dataset="15098547", url=f"{ODCLOUD_APPLYHOME}/getAPTLttotPblancDetail",
            fmt="json", key_env=DATA_GO_KR, key_param="serviceKey", page_param="page", size_param="perPage",
            page_size=500, items=odcloud_items, total=odcloud_total,
            extra={"cond[RCRIT_PBLANC_DE::GTE]": "2026-01-01"},
        ),
        ListSource(
            name="applyhome_mdl", dataset="15098547", url=f"{ODCLOUD_APPLYHOME}/getAPTLttotPblancMdl",
            fmt="json", key_env=DATA_GO_KR, key_param="serviceKey", page_param="page", size_param="perPage",
            page_size=500, items=odcloud_items, total=odcloud_total,
        ),
        ListSource(
            name="lh_list", dataset="15058530", url=f"{LH}/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1",
            fmt="json", key_env=DATA_GO_KR, key_param="serviceKey", page_param="PAGE", size_param="PG_SZ",
            page_size=100, items=lh_items, total=lh_total,
        ),
        ListSource(
            name="youth", dataset="youthcenter", url="https://www.youthcenter.go.kr/go/ythip/getPlcy",
            fmt="json", key_env=YOUTHCENTER, key_param="apiKeyNm", page_param="pageNum", size_param="pageSize",
            page_size=100, items=youth_items, total=youth_total, extra={"rtnType": "json"},
        ),
    ]
}

DETAIL_SOURCES: dict[str, DetailSource] = {
    s.name: s
    for s in [
        DetailSource(
            name="ssis_local_detail", dataset="15108347", url=f"{SSIS}/LocalGovernmentWelfareInformations/LcgvWelfaredetailed",
            fmt="xml", key_env=DATA_GO_KR, key_param="serviceKey", parent="ssis_local",
            item_id=lambda it: it.get("servId"), params=lambda it: {"servId": it.get("servId")},
            default_limit=300,   # 개발계정 1,000건/일
        ),
        DetailSource(
            name="ssis_central_detail", dataset="15090532", url=f"{SSIS}/NationalWelfareInformationsV001/NationalWelfaredetailedV001",
            fmt="xml", key_env=DATA_GO_KR, key_param="serviceKey", parent="ssis_central",
            item_id=lambda it: it.get("servId"), params=lambda it: {"callTp": "D", "servId": it.get("servId")},
            default_limit=80,    # 개발계정 100건/일
        ),
        DetailSource(
            name="lh_detail", dataset="15057999", url=f"{LH}/lhLeaseNoticeDtlInfo1/getLeaseNoticeDtlInfo1",
            fmt="json", key_env=DATA_GO_KR, key_param="serviceKey", parent="lh_list",
            item_id=lambda it: it.get("PAN_ID"), params=_lh_params, default_limit=200,
        ),
        DetailSource(
            name="lh_supply", dataset="15056765", url=f"{LH}/lhLeaseNoticeSplInfo1/getLeaseNoticeSplInfo1",
            fmt="json", key_env=DATA_GO_KR, key_param="serviceKey", parent="lh_list",
            item_id=lambda it: it.get("PAN_ID"), params=_lh_params, default_limit=50,
        ),
    ]
}

# --source 에 쓰는 묶음 이름. 하나씩 이름으로 불러도 된다.
GROUPS: dict[str, list[str]] = {
    "gov24": ["gov24_serviceList", "gov24_serviceDetail", "gov24_supportConditions"],
    "ssis_local": ["ssis_local", "ssis_local_detail"],
    "ssis_central": ["ssis_central", "ssis_central_detail"],
    "applyhome": ["applyhome_detail", "applyhome_mdl"],
    "lh": ["lh_list", "lh_detail", "lh_supply"],
    "youth": ["youth"],
}
GROUPS["all"] = [name for names in GROUPS.values() for name in names]
