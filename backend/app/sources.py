"""다른 담당 모듈에서 읽어 오는 것.

- 조건표: backend.data.rules.load_rules (임종한, rules/manual·compiled·uploads)
- 근거 줄: backend.notices.store.evidence (임종한, data/notices/*.lines.json)

사용자 업로드(rules/uploads)는 올린 계정에게만 보인다. owner(계정 ID)를 주면 그 계정의 업로드만 더하고,
안 주면 업로드는 읽지 않는다(로그인 연결 전 /judge는 owner 없이 부른다).
"""

from backend.data.rules import load_rules as _load
from backend.notices.store import evidence as _evidence


def load_rules(owner: str | None = None) -> list[dict]:
    return _load(owner=owner)


def evidence(ids: list[str], owner: str | None = None) -> list[dict]:
    return _evidence(ids, owner=owner)
