"""검색 2단계 구간 정렬(backend/search/rank.py)."""

from datetime import date

from backend.search.rank import MEDIUM, STRONG, WEAK, closed, region_rank, relevance_band, rerank

TODAY = date(2026, 11, 1)


def doc(sid, name, region=None, deadline=None, rule_id=None, aliases="", body=""):
    return {"service_id": sid, "rule_id": rule_id, "name": name, "region": region,
            "fields": {"deadline": deadline, "aliases": aliases, "target": body}}


def names(ranked):
    return [d["service_id"] for d, _ in ranked]


def test_relevance_band():
    assert relevance_band(doc("a", "기초연금"), "기초연금") == STRONG
    assert relevance_band(doc("a", "신혼부부 전용 전세자금", aliases="신혼 특공\n신혼부부 버팀목"), "신혼 특공") == STRONG
    assert relevance_band(doc("a", "청년 월세 지원"), "청년월세") == STRONG
    assert relevance_band(doc("a", "청년 주거 월세 지원"), "청년 월세") == MEDIUM
    assert relevance_band(doc("a", "노인 목욕비", body="기초연금 수급자"), "기초연금") == WEAK


def test_closed_from_dump_text_and_rule():
    assert closed(doc("a", "x", deadline="2026년 상반기"), None, TODAY)
    assert not closed(doc("a", "x", deadline="상시신청"), None, TODAY)
    rule = {"conditions": [{"field": "apply_date", "op": "<=", "value": "2026-05-29"}]}
    assert closed(doc("a", "x"), rule, TODAY)
    assert not closed(doc("a", "x"), {"conditions": [{"field": "apply_date", "op": "<=", "value": "2026-12-31"}]}, TODAY)


def test_region_rank():
    me = ("서울", "마포구")
    assert region_rank(doc("a", "x", {"sido": "서울", "sigungu": "마포구"}), *me) == 0
    assert region_rank(doc("a", "x", {"sido": "서울특별시", "sigungu": None}), *me) == 1
    assert region_rank(doc("a", "x", None), *me) == 2
    assert region_rank(doc("a", "x", {"unknown": True}), *me) == 3
    assert region_rank(doc("a", "x", {"sido": "서울", "sigungu": "강남구"}), *me) == 4
    assert region_rank(doc("a", "x", {"sido": "경기", "sigungu": None}), *me) == 4
    assert region_rank(doc("a", "x", {"sido": "경기"}), None, None) == 0   # 프로필에 지역이 없으면 보지 않는다


def test_order_relevance_then_closed_then_region_then_badge():
    hits = [
        (doc("weak-mine", "노인 목욕비", {"sido": "서울", "sigungu": "마포구"}, body="기초연금"), 9.0),
        (doc("strong-closed", "기초연금 특별", None, deadline="2026년 상반기"), 8.0),
        (doc("strong-other", "기초연금 장제", {"sido": "경남", "sigungu": "사천시"}), 7.0),
        (doc("strong-national", "기초연금", None, rule_id="r1"), 1.0),
        (doc("strong-mine", "마포 기초연금 안내", {"sido": "서울", "sigungu": "마포구"}, rule_id="r2"), 2.0),
    ]
    badges = {"strong-national": "needs_check", "strong-mine": "ineligible"}
    out = names(rerank(hits, "기초연금", rules={}, badges=badges, sido="서울", sigungu="마포구", today=TODAY))
    assert out == ["strong-mine", "strong-national", "strong-other", "strong-closed", "weak-mine"]
    # 지역이 같으면 배지가 순서를 정한다. 해당 안 됨도 숨기지 않고 내린다
    same = [(doc("x", "기초연금 가", None, rule_id="a"), 1.0), (doc("y", "기초연금 나", None, rule_id="b"), 5.0)]
    assert names(rerank(same, "기초연금", rules={}, badges={"x": "eligible", "y": "ineligible"}, today=TODAY)) == ["x", "y"]
    assert names(rerank(same, "기초연금", rules={}, badges={}, today=TODAY)) == ["y", "x"]   # 로그인 전엔 점수 순


def test_same_name_collapses_and_keeps_best():
    hits = [(doc(f"g{i}", "장수수당", {"sido": s, "sigungu": None}), 5.0) for i, s in enumerate(["충남", "경기", "서울", "전북"])]
    ranked = rerank(hits, "장수수당", rules={}, badges={}, sido="서울", today=TODAY)
    assert [(d["service_id"], n) for d, n in ranked] == [("g2", 3)]   # 내 시도 것을 대표로 남기고 나머지 셋을 센다


def test_rule_backed_doc_is_never_collapsed():
    """전국 제도의 조건표가 붙은 문서는 이름이 같은 시군구 사업 밑으로 묶이지 않는다."""
    hits = [(doc("local:1", "청년 월세 지원", {"sido": "경기", "sigungu": "수원시"}), 5.0),
            (doc("gov24:161300000099", "청년월세 지원", None, deadline="2026년 상반기", rule_id="manual:youth-rent-2026"), 9.0),
            (doc("local:2", "청년 월세 지원", {"sido": "충북", "sigungu": "옥천군"}), 4.0)]
    ranked = rerank(hits, "청년월세 지원", rules={}, badges={}, today=TODAY)
    assert [(d["service_id"], n) for d, n in ranked] == [("local:1", 1), ("gov24:161300000099", 0)]
