"""공고 투입 (SPEC §9.5, docs/api.md §6). 담당 백엔드2, 읽기는 AI 담당의 compile().

순서: 받기 → 거부 검사(HWP, 스캔 PDF, 주민번호) → 줄 만들기 → compile() → 조건표 저장 → 재판정 알림.
시연 PDF는 결과를 원문 해시로 캐시해 두고, "캐시 재생"을 켜거나 읽기가 실패하면 캐시를 돌려준다.
"""

from __future__ import annotations

import hashlib
import inspect
import ipaddress
import json
import re
import secrets
import socket
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx

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
    """사용자 업로드 조건표. 커밋하는 AI 조건표(rules/compiled/)와 나누고 커밋하지 않는다."""
    return config.UPLOAD_RULES_DIR


def _new_doc_id(today: date) -> str:
    """upload-YYYYMMDD-<무작위 8자>. 번호를 세지 않아 지운 뒤에도, 동시에 올려도 겹치지 않는다."""
    while True:
        doc_id = f"upload-{today:%Y%m%d}-{secrets.token_hex(4)}"
        if not store.load_meta(doc_id):
            return doc_id


def _delete_raw(doc_id: str) -> None:
    """컴파일러가 남긴 업로드 원응답과 글자 인식 캐시(rules/uploads/_raw/)를 지운다."""
    try:
        from backend.compiler.pipeline import delete_raw   # type: ignore[import-not-found]
    except ImportError:
        return
    delete_raw(doc_id, "upload")


def _discard(doc_id: str) -> None:
    """올린 원문을 흔적 없이 지운다. 메타가 사라지면 계정으로 찾을 수 없으니 원응답도 같이."""
    for p in store.paths_of(doc_id):
        p.unlink(missing_ok=True)
    _delete_raw(doc_id)


MAX_REDIRECTS = 3


def _check_public(url: str) -> None:
    """서버가 대신 받아 오는 주소라 내부망(localhost, 사설·예약 IP)은 막는다."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise Rejected("http(s) 주소만 받습니다")
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise Rejected("주소를 찾지 못했습니다") from exc
    if not infos or any(not ipaddress.ip_address(info[4][0]).is_global for info in infos):
        raise Rejected("내부 주소는 받지 않습니다")


def fetch_url(url: str, transport: httpx.BaseTransport | None = None) -> bytes:
    """URL의 PDF를 받는다. 리다이렉트마다 주소를 다시 검사하고, 받는 도중 30MB를 넘으면 끊는다."""
    with httpx.Client(timeout=30, follow_redirects=False, transport=transport) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _check_public(url)
            with client.stream("GET", url) as res:
                if res.is_redirect:
                    url = urljoin(url, res.headers.get("location", ""))
                    continue
                if res.status_code >= 400:
                    raise Rejected(f"URL을 받지 못했습니다(HTTP {res.status_code})")
                buf = bytearray()
                for chunk in res.iter_bytes():
                    buf += chunk
                    if len(buf) > MAX_BYTES:
                        raise Rejected("파일이 너무 큽니다(30MB까지)")
                return bytes(buf)
    raise Rejected("리다이렉트가 너무 많습니다")


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


def _after_merge(rule_ids: list[str], account_id: str | None = None) -> dict | None:
    """새 조건표로 재판정하고 알림을 만든다(알림 담당 모듈이 있으면 그것을 부른다).

    업로드 조건표는 올린 본인만 본다. 그래서 올린 계정을 같이 넘기고, 계정을 모르거나 알림 쪽이
    계정을 받지 못하면 모든 프로필에 알림이 나가지 않게 부르지 않는다.
    """
    if not account_id:
        return {"status": "skipped", "reason": "올린 계정을 몰라 업로드 알림을 보내지 않았다"}
    try:
        from backend.notify.api import rebuild   # type: ignore[import-not-found]
    except ImportError:
        return None
    if "account_id" not in inspect.signature(rebuild).parameters:
        return {"status": "skipped", "reason": "알림 재판정이 계정을 받지 않아 업로드 알림을 보내지 않았다"}
    return rebuild(rule_ids=rule_ids, account_id=account_id)


def _rule_file(doc_id: str, rule_id: str) -> Path:
    """업로드 조건표 파일. compile()이 업로드마다 같은 id를 내도 다른 업로드를 덮어쓰지 않게 doc_id를 앞에 붙인다."""
    return upload_rules_dir() / f"{doc_id}__{re.sub(r'[^a-z0-9._-]', '_', rule_id.lower())}.json"


def delete_uploads(account_id: str) -> int:
    """회원 탈퇴 때 부른다(docs/api.md 「인증·소유권 계약」). 그 계정이 올린 원문, 조건표, 캐시를 지운다."""
    gone = 0
    for doc_id in store.list_doc_ids():
        meta = store.load_meta(doc_id) or {}
        if meta.get("source") != "upload" or meta.get("uploaded_by") != account_id:
            continue
        for rule_id in meta.get("rules", []):
            _rule_file(doc_id, rule_id).unlink(missing_ok=True)
        _discard(doc_id)
        if cache_dir().is_dir():
            for c in cache_dir().glob("*.json"):
                if json.loads(c.read_text(encoding="utf-8")).get("log", {}).get("doc_id") == doc_id:
                    c.unlink()
        gone += 1
    if gone:
        from backend.search.service import reset_index
        reset_index()
    return gone


def _rebind(rules: list[dict], old: str, new: str) -> list[dict]:
    """캐시의 조건표를 새 원문 ID로. doc_id는 무작위 꼬리라 문자열 치환이 다른 값과 겹치지 않는다.
    같은 PDF는 줄 목록도 같으니 근거 줄 ID(`{doc_id}:p7-l23`)도 그대로 맞는다."""
    return json.loads(json.dumps(rules, ensure_ascii=False).replace(old, new))


def _merge(doc_id: str, meta: dict, lines: list[dict], rules: list[dict], sha: str, uploaded_by: str | None,
           replay_reason: str | None = None, cached_lines: int | None = None) -> dict:
    """조건표를 올린 계정 앞으로 저장하고 카드에 합류시킨다. 새로 읽었을 때만 캐시를 쓴다."""
    out_dir = upload_rules_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    for rule in rules:
        rule.setdefault("source", "upload")
        rule.setdefault("review", {"status": "unreviewed"})
        _rule_file(doc_id, rule["id"]).write_text(json.dumps(rule, ensure_ascii=False, indent=2), encoding="utf-8")
    meta = {**(store.load_meta(doc_id) or meta), "rules": [r["id"] for r in rules]}
    store.save_meta(meta)
    from backend.search.service import reset_index
    reset_index()

    result = {"log": summarize(doc_id, meta, lines, rules), "rules": rules, "notice": NOTICE,
              "at": datetime.now().isoformat(timespec="seconds")}
    if replay_reason is None:
        save_cache(sha, result)
    out = {**result, "replayed": replay_reason is not None}
    if replay_reason is not None:
        out["replay_reason"] = replay_reason
        if cached_lines is not None and cached_lines != len(lines):   # 줄 만들기가 바뀌면 근거 줄이 어긋날 수 있다
            out["replay_warning"] = f"캐시를 만들 때와 줄 수가 다르다({cached_lines} → {len(lines)}). 근거 줄을 확인해야 한다"
    out["alerts"] = _after_merge([r["id"] for r in rules], account_id=uploaded_by)
    return out


def ingest(path: Path, filename: str, source_url: str | None = None, replay: bool = False,
           today: date | None = None, uploaded_by: str | None = None) -> dict:
    """올린 파일 하나를 한 바퀴 돌린다. 돌려주는 것: {"log", "rules", "replayed", "notice", "alerts"}.

    uploaded_by는 로그인 세션의 계정 ID다. 원문 머리에 남겨 탈퇴 때 같이 지운다.
    캐시를 재생할 때(replay를 켰거나 읽기가 실패했을 때)도 지금 올린 계정 앞으로 원문과 조건표를 새로 남겨
    카드에 합류시킨다. 캐시는 원문 해시로 찾으므로 같은 PDF여야 한다.
    """
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise Rejected("파일이 너무 큽니다(30MB까지)")
    if data[:5] != b"%PDF-":
        raise Rejected("PDF만 받습니다. HWP와 다른 형식은 받지 않습니다")
    sha = hashlib.sha256(data).hexdigest()

    cached = load_cache(sha)
    if replay and not cached:
        raise Rejected("이 파일의 캐시가 없습니다. 캐시 재생을 끄고 다시 올려 주세요")

    today = today or date.today()
    doc_id = _new_doc_id(today)
    try:   # 계정은 등록 순간에 남긴다. 뒤에서 실패해도 탈퇴 때 찾을 수 있게
        meta = store.register(path, doc_id, "upload", source_url, Path(filename).stem or doc_id, today.isoformat(),
                              extra={"uploaded_by": uploaded_by})
    except ValueError as exc:   # 스캔 PDF 등
        _discard(doc_id)
        raise Rejected(str(exc)) from exc
    lines = store.load_lines(doc_id) or []
    if any(RRN.search(ln["text"]) for ln in lines):
        _discard(doc_id)
        raise Rejected("주민등록번호로 보이는 숫자가 있어 받지 않았습니다. " + NOTICE)

    def replay_with(reason: str) -> dict:
        rules = _rebind(cached["rules"], cached["log"]["doc_id"], doc_id)
        return _merge(doc_id, meta, lines, rules, sha, uploaded_by, reason, cached["log"].get("lines"))

    if replay:
        return replay_with("캐시 재생을 켰다")

    compile_fn = _compile()
    try:
        if compile_fn is None:
            raise RuntimeError("AI 공고 읽기(backend.compiler.compile)가 아직 연결되지 않았다")
        rules = compile_fn(doc_id, lines, "upload")
    except Exception as exc:   # 읽기가 실패하면 캐시가 있을 때 캐시로 같은 화면을 만들고, 없으면 올린 원문을 지운다
        if cached:
            return replay_with(f"읽기 실패: {exc}")
        _discard(doc_id)
        raise RuntimeError(str(exc)) from exc
    return _merge(doc_id, meta, lines, rules, sha, uploaded_by)
