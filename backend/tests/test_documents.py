"""서류 사전(docs/documents.json)과 조건표 서류명 매핑(api.md §4, SPEC §8)."""

import json

from backend.engine import documents as d


def test_dictionary_shape():
    docs = d.load_dictionary()
    assert len(docs) == 15
    keys = {"doc_id", "name", "aliases", "issuer", "online", "offline", "fee", "validity",
            "who_provides_default", "verified_from", "updated"}
    for doc in docs:
        assert set(doc) == keys, doc["doc_id"]
        assert doc["verified_from"]   # 확인한 출처 없이 발급처를 적지 않는다
    assert len({doc["doc_id"] for doc in docs}) == 15


def test_match_exact_alias_and_noise():
    docs = d.load_dictionary()
    assert d.match("주민등록등본", docs) == ["resident_register"]
    assert d.match("주민등록표 등본", docs) == ["resident_register"]
    # 괄호 안 설명, 띄어쓰기, 가운뎃점이 달라도 같은 서류
    assert d.match("금융 정보 등(금융, 신용, 보험정보) 제공 동의서(본인, 배우자)", docs) == ["financial_consent"]
    assert d.match("소득·재산 신고서", docs) == ["income_property_report"]
    assert d.match("사회복지서비스 및 급여 제공(변경) 신청서", docs) == ["social_service_application"]


def test_match_combined_name():
    docs = d.load_dictionary()
    assert d.match("기초생활수급자‧차상위계층‧한부모가족 증명서(최근 1개월 이내 발급된 증명서)", docs) == \
        ["livelihood_cert", "near_poverty_cert", "single_parent_cert"]


def test_unknown_and_self_held():
    docs = d.load_dictionary()
    assert d.match("의사소견서", docs) == []
    assert d.self_held("신분증") and d.self_held("통장 사본") and d.self_held("임대차계약서")
    assert not d.self_held("주민등록등본")


def test_build_map_and_rows(tmp_path):
    rules = [{"id": "manual:a", "documents": ["주민등록등본", "신분증", "의사소견서"], "documents_official": ["가족관계증명서"]}]
    cache = d.build_map(rules)
    assert cache["주민등록등본"] == {"doc_ids": ["resident_register"], "status": "found"}
    assert cache["신분증"] == {"doc_ids": [], "status": "self_held"}
    assert cache["의사소견서"] == {"doc_ids": [], "status": "unknown"}

    path = tmp_path / "map.json"
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    rows = d.rows(rules[0], cache=d.load_map(path))
    by = {(r["name"], r["doc_id"]): r for r in rows}
    reg = by[("주민등록등본", "resident_register")]
    assert reg["status"] == "found" and reg["who_provides"] == "applicant" and reg["issuer"] and reg["online"]
    assert by[("신분증", None)]["status"] == "self_held"
    assert by[("의사소견서", None)]["status"] == "unknown" and "issuer" not in by[("의사소견서", None)]
    assert by[("가족관계증명서", "family_relation_cert")]["who_provides"] == "official"   # 공무원 확인 서류


def test_rows_without_cache_entry_are_unknown():
    rows = d.rows({"documents": ["처음 보는 확인서"]}, cache={})
    assert rows == [{"name": "처음 보는 확인서", "doc_id": None, "who_provides": "applicant", "status": "unknown"}]


def test_committed_map_covers_committed_rules():
    """커밋된 매핑 캐시가 커밋된 손 조건표의 서류명을 전부 담는다(런타임은 캐시만 읽는다)."""
    from backend.data.rules import load_rules
    cache = d.load_map()
    names = {n for r in load_rules() for n in (r.get("documents") or []) + (r.get("documents_official") or [])}
    assert names <= set(cache)
