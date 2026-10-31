"""자격 구간 자르기, 신호어 표시, 추출 프롬프트(SPEC §9.2 1~3단계). 오프라인."""

import json

import pytest

from backend.compiler import vocab
from backend.compiler.prompt import OUTPUT_SCHEMA, PROMPT_VERSION, SYSTEM, build_user_content, parse_output
from backend.compiler.section import cut_section, find_tracks, is_heading, is_marked, mark_lines


def _lines(rows):
    out = []
    for row in rows:
        lid, text, *table = row
        page = int(lid[1:].split("-")[0])
        line = {"id": lid, "page": page, "bbox": [72.0, 100.0, 300.0, 112.0], "text": text, "mark": False}
        if table:
            line["table"] = table[0]
        out.append(line)
    return out


# LH 공고 모양: 사업개요 → 신청자격(트랙 둘) → 소득 및 자산 → 신청방법 → 제출서류 → 유의사항
LH = _lines([
    ("p1-l1", "2026년 마포 행복주택 입주자 모집공고"),
    ("p1-l2", "Ⅰ. 사업개요"),
    ("p1-l3", "공급위치: 서울특별시 마포구 일원"),
    ("p1-l4", "공급호수: 총 120호"),
    ("p2-l1", "Ⅱ. 신청자격"),
    ("p2-l2", "1. 신혼부부 특별공급"),
    ("p2-l3", "○ 공고일 현재 무주택세대구성원으로서 혼인기간 7년 이내인 분"),
    ("p2-l4", "○ 청약통장 가입기간 2년 이상"),
    ("p2-l5", "2. 청년 공급"),
    ("p2-l6", "○ 만 19세 이상 39세 이하인 미혼 무주택자"),
    ("p3-l1", "Ⅲ. 소득 및 자산 기준"),
    ("p3-l2", "구분 | 소득기준 | 총자산", "p3-t1"),
    ("p3-l3", "신혼부부 | 도시근로자 월평균소득 100% 이하 | 3억 4,500만 원 이하", "p3-t1"),
    ("p4-l1", "Ⅳ. 신청방법"),
    ("p4-l2", "인터넷 청약: LH청약플러스"),
    ("p5-l1", "Ⅴ. 제출서류"),
    ("p5-l2", "주민등록등본, 가족관계증명서"),
    ("p6-l1", "Ⅵ. 유의사항"),
    ("p6-l2", "중복 신청 시 모두 무효 처리합니다."),
])


def _ids(lines):
    return [l["id"] for l in lines]


# --- 신호어 표시 ---

def test_mark_signal_words_and_numbers():
    texts = {
        "공고일 현재 무주택세대구성원": True,
        "만 19세": True,                 # "만 " + 수
        "19세~39세": True,               # 수 + 세
        "가입기간 24개월": True,
        "5천만 원": True,
        "120%": True,
        "무 주 택 세 대 주": True,       # 자간을 벌린 글
        "세 가지 유형으로 나눈다": False,  # 수에 붙지 않은 "세 "
        "공급위치: 서울특별시 마포구 일원": False,
        "": False,
    }
    lines = [{"id": f"l{i}", "page": None, "bbox": None, "text": t, "mark": not want} for i, (t, want) in enumerate(texts.items())]
    marked = mark_lines(lines)
    assert [l["mark"] for l in marked] == list(texts.values())
    assert [l["mark"] for l in lines] == [not v for v in texts.values()]   # 원본은 그대로
    assert marked[0] is not lines[0]


def test_mark_table_rows_like_lines():
    rows = [l for l in mark_lines(LH) if l.get("table")]
    assert [l["mark"] for l in rows] == [True, True]      # "소득", "자산"·"이하"
    assert rows[0]["table"] == "p3-t1"
    marked = {l["id"] for l in mark_lines(LH) if l["mark"]}
    assert {"p2-l3", "p2-l4", "p2-l6", "p6-l2"} <= marked
    assert not {"p1-l3", "p1-l4", "p2-l5"} & marked     # 신호어 없는 줄과 "2. 청년 공급"


# --- 제목 ---

def test_is_heading():
    yes = ["1. 신청자격", "1) 소득기준", "Ⅱ. 신청자격 및 입주자 선정기준", "Ⅲ 공급일정", "가. 신혼부부 특별공급",
           "□ 지원대상", "■ 유의사항", "◆ 제출서류", "◇ 자산기준", "▣ 신청방법", "▶ 문의처", "<신청자격>",
           "[소득 및 자산 기준]", "【 제출서류 】", "제2장 공급대상", "II. 입주자격", "Ⅱ. 신 청 자 격"]
    no = ["1. 공고일 현재 무주택세대구성원이어야 합니다.", "가. 신청은 인터넷으로만 가능해요", "1) 무주택자일 것",
          "○ 무주택세대구성원", "- 지원대상", "※ 유의사항", "신청자격", "2026. 3. 30. 공고", "1.5배 이내",
          "1. 신청자격 " + "가" * 40, ""]
    assert [t for t in yes if not is_heading(t)] == []
    assert [t for t in no if is_heading(t)] == []


# --- 자격 구간 ---

def test_cut_section_lh_multi_track():
    kept, info = cut_section(LH, source="lh")
    assert _ids(kept) == ["p2-l1", "p2-l2", "p2-l3", "p2-l4", "p2-l5", "p2-l6", "p3-l1", "p3-l2", "p3-l3", "p5-l1", "p5-l2"]
    assert info == {"from": "p2-l1", "to": "p5-l2", "found_by": "heading", "lines": 11}


def test_cut_section_start_word_keeps_section_open():
    lines = _lines([
        ("p1-l1", "1. 지원대상"), ("p1-l2", "○ 무주택 세대주"),
        ("p1-l3", "2. 신청자격 관련 유의사항"), ("p1-l4", "○ 중복 지원 불가"),   # 시작 말이 있어 닫지 않는다
        ("p1-l5", "3. 문의"), ("p1-l6", "콜센터 1600-1004"),
    ])
    kept, info = cut_section(lines, source="upload")
    assert _ids(kept) == ["p1-l1", "p1-l2", "p1-l3", "p1-l4"]
    assert info["found_by"] == "heading"


def test_cut_section_api_source_whole_text():
    lines = [{"id": f"l{i}", "page": None, "bbox": None, "text": t, "mark": False}
             for i, t in enumerate(["지원대상: 만 65세 이상", "신청방법: 주민센터 방문"], 1)]
    for src in ("gov24", "local", "central", "api"):
        kept, info = cut_section(lines, source=src)
        assert kept == lines
        assert info == {"from": "l1", "to": "l2", "found_by": "api", "lines": 2}


def test_cut_section_not_found_uses_all():
    lines = _lines([("p1-l1", "Ⅰ. 사업개요"), ("p1-l2", "무주택 세대주"), ("p1-l3", "Ⅱ. 신청방법")])
    kept, info = cut_section(lines, source="upload")
    assert kept == lines
    assert info == {"from": "p1-l1", "to": "p1-l3", "found_by": "none", "lines": 3}


def test_find_tracks():
    lines = LH + _lines([("p7-l1", "다. 생애최초·신혼부부 특별공급"), ("p7-l2", "라. 노부모 부양 특별공급"),
                         ("p7-l3", "□ 다자녀가구"), ("p7-l4", "[신생아 우선공급]"), ("p7-l5", "▶ 기관추천 특별공급"),
                         ("p7-l6", "◆ 일반공급"), ("p7-l7", "신혼부부는 혼인기간 7년 이내")])
    got = find_tracks(lines)
    assert [(t["line"], t["track"]) for t in got] == [
        ("p2-l2", "newlywed"), ("p2-l5", "youth"), ("p7-l1", "first_home"), ("p7-l2", "elderly_parent"),
        ("p7-l3", "multi_child"), ("p7-l4", "newborn"), ("p7-l5", "institution"), ("p7-l6", "general"),
    ]
    assert got[0]["title"] == "1. 신혼부부 특별공급"


# --- 프롬프트 ---

def test_system_names_vocab():
    assert PROMPT_VERSION == "v1"
    for word in vocab.FIELDS + vocab.LABELS + vocab.INCOME_BASIS + vocab.DOMAINS + vocab.BENEFIT_TYPES:
        assert word in SYSTEM, word


def test_build_user_content():
    lines = mark_lines([
        {"id": "p2-l5", "page": 2, "bbox": None, "text": "2. 청년 공급", "mark": False},
        {"id": "p2-l3", "page": 2, "bbox": None, "text": "공고일 현재\t무주택\n세대구성원", "mark": False},
        {"id": "p3-l3", "page": 3, "bbox": None, "text": "신혼부부 | 100% 이하", "mark": False, "table": "p3-t1"},
    ])
    out = build_user_content(lines, title="마포 행복주택")
    rows = out.splitlines()
    assert rows[0] == "공고 제목: 마포 행복주택"
    assert "줄ID<TAB>표시<TAB>본문" in rows[1]
    assert rows[-3:] == ["p2-l5\t \t2. 청년 공급", "p2-l3\t*\t공고일 현재 무주택 세대구성원", "p3-l3\t*\t신혼부부 | 100% 이하"]
    assert not build_user_content(lines).startswith("공고 제목")


def test_parse_output():
    nul = {"income_basis": None, "as_of": None, "text": None}
    data = {
        "rules": [{
            "track": "newlywed", "name": "마포 행복주택 신혼부부", "subject": "self", "domain": "housing", "benefit_type": "rent",
            "aliases": ["신혼 행복주택", "신혼부부 임대", "행복주택 신혼", "넷째"],
            "conditions": [
                {"field": "marriage_years", "op": "<=", "value": 7.0, **nul, "as_of": "notice_date", "evidence": ["p2-l3"], "any_of": None},
                {"field": None, "op": None, "value": None, **nul, "evidence": ["p3-l3", "p3-l4", "p3-l3"], "any_of": [
                    [{"field": "income_couple", "op": "<=", "value": 100, **nul, "income_basis": "urban_worker_pct"}],
                    [{"field": "employment_type", "op": "==", "value": "맞벌이", **nul},
                     {"field": "income_couple", "op": "<=", "value": 120, **nul, "income_basis": "urban_worker_pct"}],
                ]},
                {"field": "income_self", "op": "<=", "value": 645.833, **nul, "income_basis": "absolute_monthly", "evidence": ["p3-l5"], "any_of": None},
                {"field": "other", "op": None, "value": None, **nul, "text": "총자산 3억 4,500만 원 이하", "evidence": ["lh-mapo:p3-l3"], "any_of": None},
            ],
            "documents": ["주민등록등본"],
        }],
        "labels": [{"line": "p6-l2", "label": "exclusive"}, {"line": "lh-mapo:p4-l2", "label": "procedure"}],
    }
    drafts, labels = parse_output(data, "lh-mapo")
    d = drafts[0]
    assert {k: d[k] for k in ("track", "name", "subject", "domain", "benefit_type", "documents")} == {
        "track": "newlywed", "name": "마포 행복주택 신혼부부", "subject": "self", "domain": "housing",
        "benefit_type": "rent", "documents": ["주민등록등본"]}
    assert d["aliases"] == ["신혼 행복주택", "신혼부부 임대", "행복주택 신혼"]
    c0, c1, c2, c3 = d["conditions"]
    assert c0 == {"field": "marriage_years", "op": "<=", "value": 7, "as_of": "notice_date", "evidence": ["lh-mapo:p2-l3"]}
    assert type(c0["value"]) is int
    assert c1 == {"any_of": [
        [{"field": "income_couple", "op": "<=", "value": 100, "income_basis": "urban_worker_pct"}],
        [{"field": "employment_type", "op": "==", "value": "맞벌이"},
         {"field": "income_couple", "op": "<=", "value": 120, "income_basis": "urban_worker_pct"}],
    ], "evidence": ["lh-mapo:p3-l3", "lh-mapo:p3-l4"]}
    assert c2["value"] == 645.833 and c2["income_basis"] == "absolute_monthly"
    assert c3 == {"field": "other", "text": "총자산 3억 4,500만 원 이하", "evidence": ["lh-mapo:p3-l3"]}
    assert labels == {"p6-l2": "exclusive", "p4-l2": "procedure"}


def _walk(schema, path="$"):
    if isinstance(schema, dict):
        yield path, schema
        for k, v in schema.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(schema, list):
        for i, v in enumerate(schema):
            yield from _walk(v, f"{path}[{i}]")


def test_output_schema_strict():
    json.dumps(OUTPUT_SCHEMA)
    objects = [(p, s) for p, s in _walk(OUTPUT_SCHEMA) if s.get("type") == "object"]
    assert len(objects) >= 5
    for path, s in objects:
        assert s["additionalProperties"] is False, path
        assert s["required"] == list(s["properties"]), path
    for path, s in _walk(OUTPUT_SCHEMA):
        assert not {"minimum", "maximum", "minLength", "maxLength", "pattern"} & set(s), path
    cond = OUTPUT_SCHEMA["properties"]["rules"]["items"]["properties"]["conditions"]["items"]
    assert set(cond["required"]) == {"field", "op", "value", "income_basis", "as_of", "text", "evidence", "any_of"}
    sub = cond["properties"]["any_of"]["anyOf"][0]["items"]["items"]
    assert set(sub["required"]) == {"field", "op", "value", "income_basis", "as_of", "text"}
    assert sub["properties"]["field"]["enum"] == vocab.FIELDS
    value_types = [a.get("type") for a in cond["properties"]["value"]["anyOf"]]
    assert value_types == ["number", "string", "array", "null"]  # true/false가 아니라 "Y"/"N"(api.md §1)


@pytest.mark.parametrize("text", [
    "세대구성원 전원이 주택을 소유하고 있지 아니할 것",          # 무주택 정의
    "본인과 배우자 모두 주택을 소유하지 않은 자",
    "공고일 현재 서울특별시에 주민등록이 되어 있는 자",          # 지역 요건
    "생애최초로 주택을 구입하는 자",
    "○ 접수기간: 2026. 11. 3. ~ 2026. 11. 14. 18:00까지(인터넷 접수)",
    "3. 신청기간: 2026. 12. 1.(화) ~ 2026. 12. 31.(목)",
    "※ 대학생은 이 공고로 신청할 수 없으며 별도 공고를 확인하시기 바랍니다.",
])
def test_condition_lines_without_old_signal_words_are_marked(text):
    assert is_marked(text)
