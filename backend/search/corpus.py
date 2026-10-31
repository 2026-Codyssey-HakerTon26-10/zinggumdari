"""검색 문서 만들기. 덤프 전체와 조건표를 같은 모양의 문서로 펼친다.

문서 하나: service_id, rule_id, name, org, region, subject, stage_tags, detail_url, updated,
fields(색인할 글 칸들). 조건표의 id가 덤프 항목과 같거나(gov24:WII…) 손 조건표의 same_as가 그 항목을
가리키면 한 문서로 합친다. 손 조건표의 same_as에 걸린 서비스의 AI 조건표는 검색에 쓰지 않는다(SPEC §9.4).
사용자 업로드 조건표(source: upload)도 쓰지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from backend.data import config
from backend.data.load import iter_items
from backend.data.rules import load_rules
from backend.notices.store import evidence

SIDO = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주",
    "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원특별자치도": "강원",
    "강원도": "강원", "충청북도": "충북", "충청남도": "충남", "전북특별자치도": "전북", "전라북도": "전북",
    "전라남도": "전남", "경상북도": "경북", "경상남도": "경남", "제주특별자치도": "제주",
}
SHORT = set(SIDO.values())

# 정본은 docs/stage_keywords.json이다. 파일이 없을 때만 이 기본값을 쓴다. 조건표가 없는 덤프 항목에만 붙인다.
DEFAULT_STAGE_KEYWORDS = {
    "youth": ["청년"],
    "marriage_planned": ["예비부부", "예비신혼", "결혼"],
    "newlywed": ["신혼"],
    "child": ["임신", "출산", "신생아", "영아", "육아", "양육", "아동"],
    "multi_child": ["다자녀", "둘째", "셋째"],
    "parent": ["노인", "어르신", "기초연금", "장기요양", "65세"],
}


def short_sido(name: str | None) -> str | None:
    if not name:
        return None
    name = name.strip()
    if name in SHORT:
        return name
    for full, short in SIDO.items():
        if name.startswith(full) or name.startswith(short):
            return short
    return None


def stage_keywords(docs_dir: Path | None = None) -> dict[str, list[str]]:
    path = (docs_dir or config.DOCS_DIR) / "stage_keywords.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {k: list(v) for k, v in data.items() if isinstance(v, list)}
        except json.JSONDecodeError:
            pass
    return DEFAULT_STAGE_KEYWORDS


def guess_tags(text: str, keywords: dict[str, list[str]]) -> list[str]:
    return [tag for tag, words in keywords.items() if any(w in text for w in words)]


def _region_from_org(org: str | None, org_type: str | None = None) -> dict | None:
    """gov24 지역은 소관기관명에서 추정한다. 실패하면 전국이 아니라 미상."""
    sido = short_sido(org)
    if sido:
        rest = (org or "").split(maxsplit=1)
        return {"sido": sido, "sigungu": rest[1] if len(rest) > 1 else None}
    if org_type and "중앙" in org_type:
        return None
    return {"unknown": True}


def _bokjiro(serv_id: str, kind: str) -> str:
    return ("https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do"
            f"?wlfareInfoId={quote(serv_id)}&wlfareInfoReldBztpCd={kind}")


def _doc(**kw) -> dict:
    base = {"service_id": None, "rule_id": None, "name": "", "org": None, "region": None, "subject": "self",
            "stage_tags": [], "detail_url": None, "updated": None, "source": None, "fields": {}}
    base.update(kw)
    return base


def from_gov24(item: dict) -> dict:
    return _doc(
        service_id=f"gov24:{item.get('서비스ID')}", source="gov24",
        name=item.get("서비스명") or "", org=item.get("소관기관명"),
        region=_region_from_org(item.get("소관기관명"), item.get("소관기관유형")),
        detail_url=item.get("상세조회URL"), updated=(item.get("수정일시") or "")[:10] or None,
        fields={"summary": item.get("서비스목적요약"), "target": item.get("지원대상"),
                "criteria": item.get("선정기준"), "benefit": item.get("지원내용"), "deadline": item.get("신청기한")},
    )


def from_ssis(item: dict, central: bool) -> dict:
    serv_id = item.get("servId") or ""
    sido = None if central else short_sido(item.get("ctpvNm"))
    region = None if central else ({"sido": sido, "sigungu": item.get("sggNm") or None} if sido else {"unknown": True})
    return _doc(
        service_id=f"{'central' if central else 'local'}:{serv_id}", source="ssis_central" if central else "ssis_local",
        name=item.get("servNm") or "", org=item.get("jurMnofNm") or item.get("bizChrDeptNm"), region=region,
        detail_url=item.get("servDtlLink") or _bokjiro(serv_id, "01" if central else "02"),
        updated=item.get("lastModYmd") or item.get("svcfrstRegTs"),
        fields={"summary": item.get("servDgst"), "life": item.get("lifeNmArray") or item.get("lifeArray"),
                "target": item.get("trgterIndvdlNmArray") or item.get("trgterIndvdlArray"),
                "theme": item.get("intrsThemaNmArray") or item.get("intrsThemaArray"),
                "region": " ".join(filter(None, [item.get("ctpvNm"), item.get("sggNm")]))},
    )


def from_youth(item: dict) -> dict:
    no = item.get("plcyNo") or ""
    return _doc(
        service_id=f"youth:{no}", source="youth", name=item.get("plcyNm") or "",
        org=item.get("sprvsnInstCdNm") or item.get("operInstCdNm"), region={"unknown": True},
        stage_tags=["youth"], detail_url=item.get("refUrlAddr1") or item.get("aplyUrlAddr"),
        updated=(item.get("lastMdfcnDt") or "")[:10] or None,
        fields={"summary": item.get("plcyExplnCn"), "benefit": item.get("plcySprtCn"),
                "keywords": item.get("plcyKywdNm"), "target": item.get("addAplyQlfcCndCn")},
    )


def from_lh(item: dict) -> dict:
    return _doc(
        service_id=f"lh:{item.get('PAN_ID')}", source="lh", name=item.get("PAN_NM") or "",
        org="한국토지주택공사", region={"sido": s, "sigungu": None} if (s := short_sido(item.get("CNP_CD_NM"))) else None,
        detail_url=item.get("DTL_URL"), updated=item.get("PAN_NT_ST_DT"),
        fields={"type": item.get("AIS_TP_CD_NM"), "region": item.get("CNP_CD_NM"), "state": item.get("PAN_SS")},
    )


def from_applyhome(item: dict) -> dict:
    return _doc(
        service_id=f"applyhome:{item.get('PBLANC_NO')}", source="applyhome", name=item.get("HOUSE_NM") or "",
        org=item.get("BSNS_MBY_NM"), region={"sido": s, "sigungu": None} if (s := short_sido(item.get("SUBSCRPT_AREA_CODE_NM"))) else None,
        stage_tags=[], detail_url=item.get("PBLANC_URL"), updated=item.get("RCRIT_PBLANC_DE"),
        fields={"summary": "아파트 입주자모집공고 청약", "region": item.get("HSSPLY_ADRES"),
                "type": item.get("HOUSE_SECD_NM")},
    )


def _flat(conditions: list[dict]) -> list[dict]:
    """any_of 가지 안의 조건까지 한 줄로."""
    out = []
    for c in conditions or []:
        out.append(c)
        for branch in c.get("any_of") or []:
            out.extend(branch)
    return out


def rule_stage_tags(rule: dict) -> list[str]:
    """제도의 단계 태그는 조건에서 계산한다(docs/api.md §1 「조건표에 쓰지 않고 계산하는 것」)."""
    tags = []
    for c in _flat(rule.get("conditions")):
        field, op, value = c.get("field"), c.get("op"), c.get("value")
        values = value if isinstance(value, list) else [value]
        if field == "age" and op in ("<=", "<") and isinstance(value, (int, float)) and value <= 39:
            tags.append("youth")
        if field == "marital_status" and op in ("==", "in") and "예비부부" in values:
            tags.append("marriage_planned")
        if field == "marriage_years" or (field == "marital_status" and op in ("==", "in") and "신혼" in values):
            tags.append("newlywed")
        if (field == "children_count" and value == 1) or field in ("youngest_child_age", "pregnant", "due_month"):
            tags.append("child")
        if field == "children_count" and isinstance(value, (int, float)) and value >= 2:
            tags.append("multi_child")
    if rule.get("subject") == "parent":
        tags.append("parent")
    return list(dict.fromkeys(tags))


def _criteria_text(rule: dict) -> str:
    """색인할 조건 문장. 손 조건표는 quote, AI 조건표는 근거 줄의 원문."""
    parts, ids = [], []
    for c in _flat(rule.get("conditions")):
        if c.get("quote"):
            parts.append(c["quote"])
        elif c.get("text"):
            parts.append(c["text"])
        ids.extend(c.get("evidence") or [])
    if ids and not parts:
        parts = [e["text"] for e in evidence(list(dict.fromkeys(ids))) if e["text"]]
    return " ".join(parts)


def from_rule(rule: dict) -> dict:
    region = rule.get("region")
    return _doc(
        service_id=rule["id"], rule_id=rule["id"], source=rule.get("source"), name=rule.get("name") or "",
        org=rule.get("org"), region=region, subject=rule.get("subject") or "self",
        stage_tags=rule_stage_tags(rule), detail_url=rule.get("detail_url"), updated=rule.get("updated"),
        fields={"aliases": " ".join(rule.get("aliases") or []), "benefit": rule.get("benefit_text"),
                "criteria": _criteria_text(rule),
                "region": (region or {}).get("sido") if isinstance(region, dict) else None},
    )


def build_corpus(raw_dir: Path | None = None, rules: list[dict] | None = None,
                 docs_dir: Path | None = None) -> tuple[list[dict], dict[str, dict]]:
    """(문서들, rule_id → 조건표)."""
    keywords = stage_keywords(docs_dir)
    docs: dict[str, dict] = {}
    makers = [
        ("gov24_serviceList", from_gov24),
        ("ssis_local", lambda it: from_ssis(it, central=False)),
        ("ssis_central", lambda it: from_ssis(it, central=True)),
        ("youth", from_youth),
        ("lh_list", from_lh),
        ("applyhome_detail", from_applyhome),
    ]
    for name, make in makers:
        for item in iter_items(name, raw_dir):
            doc = make(item)
            docs.setdefault(doc["service_id"], doc)

    rules = load_rules() if rules is None else rules
    # 사용자 업로드 조건표는 공용 색인에 넣지 않는다(올린 본인에게만 판정 카드로 합류한다, 인증·소유권 계약)
    rules = [r for r in rules if r.get("source") != "upload"]
    manual_same = {sid: r for r in rules if r.get("source") == "manual" for sid in r.get("same_as") or []}
    rules = [r for r in rules if r.get("source") == "manual" or r["id"] not in manual_same]
    by_id = {r["id"]: r for r in rules}
    for rule in rules:
        rdoc = from_rule(rule)
        targets = [rule["id"], *(rule.get("same_as") or [])] if rule.get("source") == "manual" else [rule["id"]]
        target = next((t for t in targets if t in docs), None)
        if target:   # 덤프 항목에 조건표를 붙인다. URL은 덤프 원문을 남기고, 손 조건표면 이름도 손 조건표 것
            doc = docs[target]
            doc["rule_id"] = rule["id"]
            doc["subject"] = rdoc["subject"]
            doc["stage_tags"] = rdoc["stage_tags"] or doc["stage_tags"]
            if rule.get("source") == "manual":
                doc["name"] = rdoc["name"] or doc["name"]
            doc["fields"].update({k: v for k, v in rdoc["fields"].items() if v})
        else:
            docs[rule["id"]] = rdoc

    for doc in docs.values():
        if not doc["rule_id"] and not doc["stage_tags"]:
            doc["stage_tags"] = guess_tags(doc["name"] + " " + " ".join(str(v) for v in doc["fields"].values() if v), keywords)
        if not doc["rule_id"] and "parent" in doc["stage_tags"] and len(doc["stage_tags"]) == 1:
            doc["subject"] = "parent"
    return list(docs.values()), by_id
