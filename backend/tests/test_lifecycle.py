"""생애주기 알림·리포트 메일: 타임라인을 그대로 옮기고, 다시 만들어도 쌓이지 않고, HTML은 이스케이프한다."""

from datetime import date

from fastapi.testclient import TestClient

from backend.app import main
from backend.notify import lifecycle

TODAY = date(2026, 11, 1)
NAMES = {"r1": "청약 신혼부부 특별공급", "r2": "국민임대 신혼부부", "r3": "기초연금", "r4": "<b>문화누리</b>"}
RESULT = {
    "cards": [{"subject": "self", "verdict": "eligible", "name": "서울 청년 마음건강"},
              {"subject": "self", "verdict": "needs_check", "name": "청년전용 버팀목"}],
    "timeline": {
        "self": [{"step": "newlywed", "opens": ["r1", "r2"], "closes": [], "todo": [{"action": "marriage_registration", "evidence": ["x"]}]},
                 {"step": "child", "opens": [], "closes": []}],
        "parent": [{"step": "age65", "relation": "모", "year": 2031, "apply_from": "2031년 6월부터", "opens": ["r3"]}],
        "dated": [{"what": "<b>문화누리</b> 접수 마감", "date": "2026-11-30"}, {"what": "지난 마감", "date": "2026-10-01"},
                  {"what": "어머니 만 65세", "year": 2031}],
    },
}
PROFILE = {"self": {"nickname": "<지원>", "marital_status": "예비부부", "sido": "서울", "sigungu": "마포구"}, "parents": []}


def test_notifications_follow_timeline():
    items = lifecycle.notifications("U1", RESULT, NAMES, today=TODAY)
    titles = [i["title"] for i in items]
    assert titles[0] == "신혼이 되면 열려요: 청약 신혼부부 특별공급 외 1개 · 미리 해둘 일: 혼인신고"
    assert any(t.startswith("어머니 2031년 만 65세: 기초연금") for t in titles)
    assert any("2026-11-30" in t for t in titles) and not any("지난 마감" in t for t in titles)
    assert len(items) == 3   # 열리는 제도가 없는 단계와 지난 날짜·연도만 있는 날짜는 빠진다
    assert all(i["rule_id"] and i["kind"] == "lifecycle" for i in items)


def test_notification_ids_are_stable():
    a = lifecycle.notifications("U1", RESULT, NAMES, today=TODAY)
    b = lifecycle.notifications("U1", RESULT, NAMES, today=date(2026, 11, 2))
    assert [i["id"] for i in a] == [i["id"] for i in b]


def test_report_escapes_html():
    subject, text, html = lifecycle.report(PROFILE, RESULT, NAMES, today=TODAY)
    assert "생애주기 리포트" in subject and "■ 신혼" in text and "혼인신고" in text
    assert "<b>" not in html and "&lt;b&gt;" in html and "&lt;지원&gt;" in html
    assert lifecycle.DISCLAIMER in text


def test_report_preview_requires_login():
    assert TestClient(main.app).get("/notify/report").status_code == 401
