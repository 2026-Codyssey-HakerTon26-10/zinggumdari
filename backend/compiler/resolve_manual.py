"""손 조건표의 quote → evidence(SPEC §10.2). 못 찾으면 실패하고 사람이 quote를 고친다.

    python -m backend.compiler.resolve_manual rules/manual/*.json [--notices data/notices]

quote를 "…"(또는 "...")로 나눈 조각(띄어쓰기 빼고 4자 이상)마다 원문 줄 하나를 찾는다(띄어쓰기 무시).
같은 조각이 여러 줄에 있으면 이미 근거로 적힌 줄, 없으면 앞 줄을 쓴다. 원문은 data/notices/{doc}.lines.json이고
doc은 조건표의 doc_id, 없으면 기존 evidence의 접두어다. 끝에 검증기를 돌려 떨어진 검사를 경고로 찍는다(상태는 바꾸지 않는다).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from backend.compiler.pipeline import REPO_ROOT, rule_json
from backend.compiler.verify import verify

NOTICES = REPO_ROOT / "data/notices"
MIN_CHARS = 4
_ELLIPSIS = re.compile(r"…+|\.{3,}")
_WS = re.compile(r"\s+")


def _key(text: str | None) -> str:
    return _WS.sub("", unicodedata.normalize("NFKC", text or ""))


def doc_of(rule: dict) -> str:
    """원문 doc_id. 조건표의 doc_id, 없으면 기존 evidence 접두어(하나뿐이어야 한다)."""
    if rule.get("doc_id"):
        return rule["doc_id"]
    docs = {e.rsplit(":", 1)[0] for c in rule.get("conditions", []) for e in c.get("evidence") or []
            if isinstance(e, str) and ":" in e}
    if len(docs) == 1:
        return docs.pop()
    raise ValueError("doc_id를 정할 수 없습니다. 조건표에 \"doc_id\"를 적으세요" + (f"(근거 원문 {sorted(docs)})" if docs else ""))


def resolve_rule(rule: dict, lines: list[dict], doc_id: str) -> list[str]:
    """quote가 있는 조건(any_of 묶음 포함)의 evidence를 원문 줄 ID로 다시 쓴다(rule을 고친다). 오류 문구 목록을 돌려준다."""
    keyed = [(l["id"], _key(l.get("text"))) for l in lines]
    order = {lid: n for n, (lid, _) in enumerate(keyed)}
    errors = []
    for i, c in enumerate(rule.get("conditions", [])):
        quote = c.get("quote")
        if not isinstance(quote, str):
            continue
        where = f"{rule.get('id')} 조건 {i}"
        frags = [(s.strip(), k) for s in _ELLIPSIS.split(quote) if len(k := _key(s)) >= MIN_CHARS]
        if not frags:
            errors.append(f"{where}: quote 조각이 너무 짧습니다(띄어쓰기 빼고 {MIN_CHARS}자 이상): {quote!r}")
            continue
        old = {e.rsplit(":", 1)[-1] for e in c.get("evidence") or [] if isinstance(e, str)}
        found, missing = [], []
        for text, k in frags:
            hits = [lid for lid, t in keyed if k in t]
            if hits:
                found.append(next((h for h in hits if h in old), hits[0]))
            else:
                missing.append(text)
        if missing:
            errors += [f"{where}: 원문에서 못 찾음 {m!r} (quote: {quote!r})" for m in missing]
            continue
        c["evidence"] = [f"{doc_id}:{lid}" for lid in sorted(set(found), key=order.__getitem__)]
    return errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m backend.compiler.resolve_manual", description="손 조건표 quote → evidence")
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument("--notices", type=Path, default=NOTICES, help="{doc_id}.lines.json이 있는 폴더")
    a = p.parse_args(argv)
    failed = 0
    for path in a.files:
        rule = json.loads(path.read_text(encoding="utf-8"))
        rid = rule.get("id") or path.name
        try:
            doc = doc_of(rule)
            lines = json.loads((a.notices / f"{doc}.lines.json").read_text(encoding="utf-8"))
        except (ValueError, OSError) as e:
            print(f"실패 {rid}: {e}")
            failed += 1
            continue
        before = rule_json(rule)
        errors = resolve_rule(rule, lines, doc)
        for e in errors:
            print(f"실패 {e}")
        failed += bool(errors)
        if rule_json(rule) != before:
            path.write_text(rule_json(rule), encoding="utf-8")
        log: list = []
        verify(rule, lines, log=log)
        for entry in log:
            bad = ", ".join(f"{k}={v[5:]}" for k, v in entry["checks"].items() if v.startswith("fail:"))
            print(f"경고 {rid} 조건 {entry['index']}: {bad}")
    print(f"조건표 {len(a.files)}개, 실패 {failed}개", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
