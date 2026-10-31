"""공고 투입 (SPEC §9.5, docs/api.md §6). 담당 백엔드2, 읽기는 AI 담당의 compile().

순서: 받기 → 거부 검사(HWP, 스캔 PDF, 주민번호) → 줄 만들기 → compile() → 조건표 저장 → 재판정 알림.
시연 PDF는 결과를 원문 해시로 캐시해 두고, "캐시 재생"을 켜거나 읽기가 실패하면 캐시를 돌려준다.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from backend.data import config
from backend.notices import store

RRN = re.compile(r"(?<!\d)\d{6}\s?-\s?[1-4]\d{6}(?!\d)")   # 주민등록번호 꼴
MAX_BYTES = 30 * 1024 * 1024
NOTICE = "개인 서류를 올리지 마세요. 주민등록번호가 보이면 받지 않습니다."


class Rejected(ValueError):
    """받지 않는 입력. 메시지를 화면에 그대로 보여준다."""


def cache_dir() -> Path:
    return config.NOTICES_DIR / "_ingest_cache"


def upload_rules_dir() -> Path:
    return config.ROOT / "rules" / "compiled"


def _next_doc_id(today: date) -> str:
    prefix = f"upload-{today:%Y%m%d}-"
    used = [d for d in store.list_doc_ids() if d.startswith(prefix)]
    return f"{prefix}{len(used) + 1:02d}"


def _compile():
    """AI 담당의 compile(doc_id, lines, source). 아직 없으면 None."""
    try:
        from backend.compiler import compile as fn   # type: ignore[attr-defined]
    except ImportError:
        return None
    return fn


def summarize(doc_id: str, meta: dict, lines: list[dict], rules: list[dict]) -> dict:
    """compile() 결과에서 docs/api.md §6의 로그를 센다."""
    conds = [c for r in rules for c in r.get("conditions", [])]
    status = Counter(c.get("status") for c in conds)
    fails = []
    for r in rules:
        for c in r.get("conditions", []):
            for check, result in (c.get("checks") or {}).items():
                if isinstance(result, str) and result.startswith("fail"):
                    fails.append({"rule_id": r["id"], "field": c.get("field"), "check": check,
                                  "reason": result.partition(":")[2] or result, "evidence": c.get("evidence", [])})
    unaccounted = [e for c in conds if c.get("reason") == "unaccounted" for e in c.get("evidence", [])]
    compiled = next((r.get("compiled") for r in rules if r.get("compiled")), None) or {}
    return {
        "doc_id": doc_id, "lines": len(lines), "section": meta.get("section"),
        "marked": sum(1 for ln in lines if ln.get("mark")),
        "llm_calls": compiled.get("llm_calls"), "schema_retries": compiled.get("schema_retries"),
        "rules": len(rules), "conditions": len(conds),
        "auto_verified": status.get("auto_verified", 0), "needs_review": status.get("needs_review", 0),
        "fails": fails, "unaccounted": unaccounted, "model": compiled.get("model"), "prompt": compiled.get("prompt"),
    }


def _cache_path(sha: str) -> Path:
    return cache_dir() / f"{sha}.json"


def save_cache(sha: str, result: dict) -> None:
    cache_dir().mkdir(parents=True, exist_ok=True)
    _cache_path(sha).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def load_cache(sha: str) -> dict | None:
    p = _cache_path(sha)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _after_merge(rule_ids: list[str]) -> dict | None:
    """새 조건표로 재판정하고 알림을 만든다(알림 담당 모듈이 생기면 그것을 부른다)."""
    try:
        from backend.notify.api import rebuild   # type: ignore[import-not-found]
    except ImportError:
        return None
    return rebuild(rule_ids=rule_ids)


def _rule_file(rule_id: str) -> Path:
    return upload_rules_dir() / (re.sub(r"[^a-z0-9._-]", "_", rule_id.lower()) + ".json")


def delete_uploads(account_id: str) -> int:
    """회원 탈퇴 때 부른다(docs/api.md 「인증·소유권 계약」). 그 계정이 올린 원문, 조건표, 캐시를 지운다."""
    gone = 0
    for doc_id in store.list_doc_ids():
        meta = store.load_meta(doc_id) or {}
        if meta.get("source") != "upload" or meta.get("uploaded_by") != account_id:
            continue
        for rule_id in meta.get("rules", []):
            _rule_file(rule_id).unlink(missing_ok=True)
        for p in store.paths_of(doc_id):
            p.unlink(missing_ok=True)
        if cache_dir().is_dir():
            for c in cache_dir().glob("*.json"):
                if json.loads(c.read_text(encoding="utf-8")).get("log", {}).get("doc_id") == doc_id:
                    c.unlink()
        gone += 1
    if gone:
        from backend.search.service import reset_index
        reset_index()
    return gone


def ingest(path: Path, filename: str, source_url: str | None = None, replay: bool = False,
           today: date | None = None, uploaded_by: str | None = None) -> dict:
    """올린 파일 하나를 한 바퀴 돌린다. 돌려주는 것: {"log", "rules", "replayed", "notice"}.

    uploaded_by는 로그인 세션의 계정 ID다. 원문 머리에 남겨 탈퇴 때 같이 지운다.
    """
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise Rejected("파일이 너무 큽니다(30MB까지)")
    if data[:5] != b"%PDF-":
        raise Rejected("PDF만 받습니다. HWP와 다른 형식은 받지 않습니다")
    sha = hashlib.sha256(data).hexdigest()

    cached = load_cache(sha)
    if replay:
        if not cached:
            raise Rejected("이 파일의 캐시가 없습니다. 캐시 재생을 끄고 다시 올려 주세요")
        return {**cached, "replayed": True, "replay_reason": "캐시 재생을 켰다"}

    today = today or date.today()
    doc_id = _next_doc_id(today)
    try:
        meta = store.register(path, doc_id, "upload", source_url, Path(filename).stem or doc_id, today.isoformat())
    except ValueError as exc:   # 스캔 PDF 등
        raise Rejected(str(exc)) from exc
    lines = store.load_lines(doc_id) or []
    if any(RRN.search(ln["text"]) for ln in lines):
        for p in store.paths_of(doc_id):
            p.unlink(missing_ok=True)
        raise Rejected("주민등록번호로 보이는 숫자가 있어 받지 않았습니다. " + NOTICE)

    compile_fn = _compile()
    try:
        if compile_fn is None:
            raise RuntimeError("AI 공고 읽기(backend.compiler.compile)가 아직 연결되지 않았다")
        rules = compile_fn(doc_id, lines, "upload")
    except Exception as exc:   # 읽기가 실패하면 캐시가 있을 때 캐시로 같은 화면을 만든다
        if cached:
            return {**cached, "replayed": True, "replay_reason": f"읽기 실패: {exc}"}
        raise RuntimeError(str(exc)) from exc

    out_dir = upload_rules_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    for rule in rules:
        rule.setdefault("source", "upload")
        rule.setdefault("review", {"status": "unreviewed"})
        _rule_file(rule["id"]).write_text(json.dumps(rule, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {**(store.load_meta(doc_id) or meta), "rules": [r["id"] for r in rules], "uploaded_by": uploaded_by}
    store.save_meta(meta)
    from backend.search.service import reset_index
    reset_index()

    result = {"log": summarize(doc_id, meta, lines, rules), "rules": rules, "notice": NOTICE,
              "at": datetime.now().isoformat(timespec="seconds")}
    save_cache(sha, result)
    return {**result, "replayed": False, "alerts": _after_merge([r["id"] for r in rules])}
