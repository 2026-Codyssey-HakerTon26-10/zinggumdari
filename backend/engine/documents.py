"""서류 사전(docs/documents.json)과 조건표 서류명 → 사전 매핑(api.md §4, SPEC §8).

매핑은 오프라인에서 미리 만들어 docs/documents_map.json에 캐시하고, 런타임(/judge)은 캐시만 읽는다.
LLM 제안은 쓰지 않는다. 사전에 없으면 "발급처 확인 필요"(status unknown)이고 발급처를 지어내지 않는다.

    uv run --project backend python -m backend.engine.documents      # 커밋된 조건표로 캐시 다시 만들기
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DICTIONARY = ROOT / "docs" / "documents.json"
MAP = ROOT / "docs" / "documents_map.json"

# 본인이 가지고 있는 서류. 발급처를 안내하지 않는다(api.md §3 status self_held)
SELF_HELD = ("신분증", "통장 사본", "통장사본", "임대차계약서", "위임장")

_PAREN = re.compile(r"\([^)]*\)")
_NOISE = re.compile(r"[\s·‧ㆍ･・.,'\"‘’“”]+")
_SPLIT = re.compile(r"[·‧ㆍ･・]")


def _key(name: str) -> str:
    return _NOISE.sub("", _PAREN.sub("", unicodedata.normalize("NFKC", name or "")))


def load_dictionary(path: Path = DICTIONARY) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def self_held(name: str) -> bool:
    k = _key(name)
    return any(_key(s) in k for s in SELF_HELD)


def _parts(name: str) -> list[str]:
    """"기초생활수급자‧차상위계층‧한부모가족 증명서" → 앞 낱말마다 끝 낱말을 붙여 나눈다."""
    base = _PAREN.sub("", unicodedata.normalize("NFKC", name)).strip()
    pieces = [p.strip() for p in _SPLIT.split(base) if p.strip()]
    if len(pieces) < 2 or " " not in pieces[-1]:
        return [name]
    tail = pieces[-1].rsplit(" ", 1)[1]
    return [p if p.endswith(tail) else f"{p} {tail}" for p in pieces[:-1]] + [pieces[-1]]


def match(name: str, docs: list[dict]) -> list[str]:
    """서류명 → 사전 doc_id 목록. 정확히 같은 이름·별칭(괄호·띄어쓰기·가운뎃점 무시)만 맞춘다."""
    keys = {}
    for doc in docs:
        for n in [doc["name"], *doc.get("aliases", [])]:
            keys.setdefault(_key(n), doc["doc_id"])
    whole = keys.get(_key(name))
    if whole:
        return [whole]
    found = []
    for part in _parts(name):
        hit = keys.get(_key(part))
        if hit and hit not in found:
            found.append(hit)
    return found if len(found) > 1 or (found and len(_parts(name)) > 1) else []


def build_map(rules: list[dict], docs: list[dict] | None = None) -> dict[str, dict]:
    """조건표들의 서류명 → {"doc_ids", "status"}. 오프라인에서 한 번 만들어 캐시한다."""
    docs = docs or load_dictionary()
    out = {}
    for rule in rules:
        for name in (rule.get("documents") or []) + (rule.get("documents_official") or []):
            if name in out:
                continue
            if self_held(name):
                out[name] = {"doc_ids": [], "status": "self_held"}
                continue
            ids = match(name, docs)
            out[name] = {"doc_ids": ids, "status": "found" if ids else "unknown"}
    return dict(sorted(out.items()))


def load_map(path: Path = MAP) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def rows(rule: dict, cache: dict[str, dict] | None = None, docs: list[dict] | None = None) -> list[dict]:
    """카드의 documents(api.md §3). 캐시에 없는 서류명은 unknown이다(런타임에 새로 맞추지 않는다)."""
    cache = load_map() if cache is None else cache
    by_id = {d["doc_id"]: d for d in (docs or load_dictionary())}
    official = set(rule.get("documents_official") or [])
    out = []
    for name in (rule.get("documents") or []) + [n for n in rule.get("documents_official") or []
                                                 if n not in (rule.get("documents") or [])]:
        who = "official" if name in official else "applicant"
        hit = cache.get(name) or {"doc_ids": [], "status": "unknown"}
        if hit["status"] == "found":
            for doc_id in hit["doc_ids"]:
                d = by_id[doc_id]
                out.append({"name": name, "doc_id": doc_id, "issuer": d["issuer"], "online": d["online"],
                            "offline": d["offline"], "fee": d["fee"],
                            "who_provides": who if name in official else d["who_provides_default"], "status": "found"})
        else:
            out.append({"name": name, "doc_id": None, "who_provides": who, "status": hit["status"]})
    return out


def missing_from_map() -> list[str]:
    """커밋된 조건표의 서류명 중 캐시에 없는 것."""
    from backend.data.rules import load_rules

    cache = load_map()
    names = {n for r in load_rules() for n in (r.get("documents") or []) + (r.get("documents_official") or [])}
    return sorted(names - set(cache))


def main() -> None:
    from backend.data.rules import load_rules

    cache = build_map([r for r in load_rules() if r.get("source") in ("manual", "gov24", "local", "central")])
    MAP.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    found = sum(1 for v in cache.values() if v["status"] == "found")
    print(f"서류명 {len(cache)}개: 사전 {found}, 본인 소지 "
          f"{sum(1 for v in cache.values() if v['status'] == 'self_held')}, 발급처 확인 필요 "
          f"{sum(1 for v in cache.values() if v['status'] == 'unknown')} → {MAP.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
