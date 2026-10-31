"""공고 투입 뒤 호출하는 연결점. 인증된 수집·앱 코드에서만 연결한다."""

from datetime import date

_handler = None


def connect(handler):
    """handler(*, rule_ids, today)는 저장소와 service.rebuild를 연결한다."""
    global _handler
    _handler = handler


def rebuild(*, rule_ids, today=None):
    if _handler is None:
        return {"status": "not_connected", "notifications": 0}
    return _handler(rule_ids=list(dict.fromkeys(rule_ids)), today=today or date.today())
