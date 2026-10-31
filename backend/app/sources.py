"""다른 담당 모듈에서 읽어 오는 것. 그 모듈이 아직 없으면 빈 값으로 돈다.

- 조건표: backend.data.rules.load_rules (임종한, rules/manual·compiled·uploads)
- 근거 줄: backend.notices.store.evidence (임종한, data/notices/*.lines.json)
"""


def load_rules() -> list[dict]:
    try:
        from backend.data.rules import load_rules as load
    except ImportError:
        return []
    return load()


def evidence(ids: list[str]) -> list[dict]:
    try:
        from backend.notices.store import evidence as fill
    except ImportError:
        return [{"id": e, "page": None, "bbox": None, "text": None} for e in ids]
    return fill(ids)
