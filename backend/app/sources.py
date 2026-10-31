"""다른 담당 모듈에서 읽어 오는 것.

- 조건표: backend.data.rules.load_rules (임종한, rules/manual·compiled·uploads)
- 근거 줄: backend.notices.store.evidence (임종한, data/notices/*.lines.json)

사용자 업로드(rules/uploads)는 올린 계정에게만 보여야 한다. 로그인·소유권 연결 전까지는 읽지 않는다.
"""

from backend.data import config
from backend.data.rules import load_rules as _load
from backend.notices.store import evidence as _evidence


def load_rules() -> list[dict]:
    public = tuple(d for d in config.RULES_DIRS if d.name != "uploads")
    return _load(public)


def evidence(ids: list[str]) -> list[dict]:
    return _evidence(ids)
