"""공고 투입 뒤 호출하는 연결점. 인증된 수집·앱 코드에서만 연결한다."""

from datetime import date
import inspect

_handler = None


def connect(handler):
    """handler(*, rule_ids, today, account_id)는 저장소와 service.rebuild를 연결한다."""
    global _handler
    _handler = handler


def rebuild(*, rule_ids, today=None, account_id=None):
    ids = list(dict.fromkeys(rule_ids))
    if any(rid.startswith("upload:") for rid in ids) and not account_id:
        return {"status": "skipped", "notifications": 0, "reason": "업로드 계정 범위가 없습니다"}
    if _handler is None:
        return {"status": "not_connected", "notifications": 0}
    kwargs = dict(rule_ids=ids, today=today or date.today())
    scoped = "account_id" in inspect.signature(_handler).parameters
    if account_id and not scoped:
        return {"status": "skipped", "notifications": 0, "reason": "handler가 계정 범위를 지원하지 않습니다"}
    if scoped:
        kwargs["account_id"] = account_id
    return _handler(**kwargs)
