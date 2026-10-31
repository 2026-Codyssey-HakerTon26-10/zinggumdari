"""compile(): 자격 구간 → LLM 1회 → 검증기 → 빠짐 검사(SPEC §9.2). 조건표는 api.md §1, 로그는 §6 모양이다.

LLM 원응답은 rules/compiled/_raw/{doc_id}.json에 둔다. 같은 입력(프롬프트 버전 + 모델 + 자격 구간)이면
다시 부르지 않고 원응답을 다시 읽는다(시연의 "캐시 재생").
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.compiler import llm
from backend.compiler.lines import _check_id, has_rrn
from backend.compiler.prompt import OUTPUT_SCHEMA, PROMPT_VERSION, SYSTEM, build_user_content, parse_output
from backend.compiler.section import API_SOURCES, cut_section, find_tracks, mark_lines
from backend.compiler.verify import index_lines, used_lines, verify
from backend.compiler.vocab import LABELS, OPS

REPO_ROOT = llm.REPO_ROOT
OUT_DIR = REPO_ROOT / "rules/compiled"
RAW_DIR = OUT_DIR / "_raw"
UPLOAD_OUT_DIR = REPO_ROOT / "rules/uploads"  # 사용자 업로드의 조건표. 커밋하지 않는다(.gitignore)
UPLOAD_RAW_DIR = UPLOAD_OUT_DIR / "_raw"  # 업로드의 원응답·글자 인식. 탈퇴 때 지운다
MAX_CONTENT = 300_000  # 이보다 긴 자격 구간은 트랙마다 나눠 보낸다
KST = timezone(timedelta(hours=9))
RRN_MESSAGE = "주민등록번호가 있는 문서는 받지 않습니다. 개인 서류를 올리지 마세요."
EMPTY_MESSAGE = "글자를 읽지 못한 문서입니다. 공고문 원본(PDF, HWP, HWPX, 텍스트)을 올려 주세요."
UNACCOUNTED = "원문 조건 미반영"
UNREAD = "읽지 못한 쪽이 있어 그 쪽의 조건이 빠졌을 수 있음"
MALFORMED = "AI가 읽은 조건의 형식이 맞지 않음"

_BRANCH = re.compile(r"b(\d+)\.(\d+):")


class IngestRejected(ValueError):
    """받지 않는 원문(주민등록번호가 있는 문서 등). 메시지는 화면에 그대로 띄울 한국어."""


def resolve_model(model: str | None) -> str:
    """main | bulk | None(main)은 .env의 모델 ID로, 그 밖은 모델 ID 그대로."""
    return llm.model_name(model or "main") if model in (None, "main", "bulk") else model


def out_dir_for(source: str) -> Path:
    """조건표 폴더. 사용자 업로드(upload)는 공개 수집 조건표(rules/compiled)와 섞지 않는다."""
    return UPLOAD_OUT_DIR if source == "upload" else OUT_DIR


def raw_dir_for(source: str) -> Path:
    """원응답·글자 인식 캐시 폴더. 사용자 업로드(upload)는 커밋하는 rules/compiled/_raw와 나눈다."""
    return UPLOAD_RAW_DIR if source == "upload" else RAW_DIR


def delete_raw(doc_id: str, source: str = "upload") -> int:
    """회원 탈퇴 때 그 업로드의 원응답과 글자 인식 캐시를 지운다. 지운 파일 수."""
    _check_id(doc_id)
    gone = 0
    for p in (raw_dir_for(source) / f"{doc_id}.json", raw_dir_for(source) / f"{doc_id}.ocr.json"):
        if p.exists():
            p.unlink()
            gone += 1
    return gone


def compile(doc_id: str, lines: list[dict], source: str = "upload", *, meta: dict | None = None,
            model: str | None = None, use_cache: bool = True, raw_dir: Path | None = None,
            return_log: bool = False) -> list[dict] | tuple[list[dict], dict]:
    """줄 목록 → AI 조건표 목록(api.md §1). return_log면 (조건표, 로그 api.md §6).

    meta(선택): title(프롬프트 머리), org, region(API 메타데이터), source_url(→ detail_url),
    fetched_at(→ updated, 없으면 오늘), sha256(원문 해시), unread_pages(글자를 읽지 못한 쪽. 조건표마다
    지울 수 없는 확인 필요 조건이 붙는다). raw_dir를 안 주면 raw_dir_for(source).
    """
    _check_id(doc_id)
    _check_id(source)
    meta = meta or {}
    if has_rrn(lines):  # LLM에 보내기 전에 거부한다(SPEC §9.5)
        raise IngestRejected(RRN_MESSAGE)
    if not any((l.get("text") or "").strip() for l in lines):
        raise IngestRejected(EMPTY_MESSAGE)
    if any("mark" not in l for l in lines):
        lines = mark_lines(lines)
    section, info = cut_section(lines, source=source)
    parts = _parts(section, meta.get("title"))
    raw_path = Path(raw_dir or raw_dir_for(source)) / f"{doc_id}.json"
    outputs, raw, calls = _llm_outputs(parts, resolve_model(model), use_cache=use_cache, path=raw_path)
    drafts, labels = parse_output(_merge(parts, outputs), doc_id)

    section_ids = {l["id"] for l in section}
    labels = {i: lab for i, lab in labels.items() if i in section_ids}  # 모델이 지어낸 줄 ID는 버린다
    marked = [l["id"] for l in section if l.get("mark")]
    exclusive = [f"{doc_id}:{l['id']}" for l in section if labels.get(l["id"]) == "exclusive"]
    compiled = {"model": raw["model"], "prompt": PROMPT_VERSION,
                "doc_sha256": meta.get("sha256") or _sha("\n".join(l.get("text") or "" for l in lines)),
                "raw": _rel(raw_path), "at": raw["at"]}

    rules = []
    for rid, d in zip(_rule_ids(drafts, doc_id, source), drafts):
        rule = {"id": rid, "source": source, "name": d.get("name") or meta.get("title") or doc_id, "org": meta.get("org"),
                "region": None, "domain": d.get("domain"), "subject": d.get("subject", "self"),
                "benefit_type": d.get("benefit_type"), "aliases": d["aliases"], "conditions": d["conditions"],
                "exclusive_evidence": exclusive, "documents": d["documents"], "detail_url": meta.get("source_url"),
                "updated": meta.get("fetched_at") or datetime.now(KST).date().isoformat(), "review": {"status": "unreviewed"}}
        rule["conditions"] = [_well_formed(c) for c in rule["conditions"]]
        rule = verify(rule, lines)
        rule["region"] = _region(rule["conditions"], source, meta)
        rules.append(rule)

    # 빠짐 검사: 표시된 줄 중 어느 조건표에도 쓰이지 않고 라벨도 없는 줄. auto_verified 조건은 검사가 맞춘 줄만 쓰인 줄이다
    by_id = index_lines(lines)
    used_by = [set().union(*(used_lines(c, r, by_id) for c in r["conditions"])) for r in rules]
    cited = set().union(*used_by)
    unaccounted = [i for i in marked if i not in cited and i not in labels]
    labeled = Counter(labels[i] for i in marked if i in labels)
    unread = sorted(meta.get("unread_pages") or [])
    for r, used in zip(rules, used_by):
        r["conditions"] += [{"field": "other", "text": UNACCOUNTED, "reason": "unaccounted",
                             "evidence": [f"{doc_id}:{i}"], "status": "needs_review"} for i in unaccounted]
        if unread:  # 근거 줄이 없는 쪽이라 evidence는 비고 쪽 번호를 단다. 검수 전에는 판정에서 항상 확인 필요
            r["conditions"].append({"field": "other", "text": UNREAD, "reason": "unread_pages", "pages": unread,
                                    "evidence": [], "status": "needs_review"})
        r["coverage"] = {"marked": len(marked), "used": sum(i in used for i in marked),
                         "labeled": {k: labeled[k] for k in LABELS}, "unaccounted": len(unaccounted)}
        r["compiled"] = dict(compiled)

    if not return_log:
        return rules
    conds = [c for r in rules for c in r["conditions"]]
    status = Counter(c.get("status") for c in conds)
    log = {"doc_id": doc_id, "lines": len(lines), "section": info, "marked": len(marked), **calls,
           "rules": len(rules), "conditions": len(conds), "auto_verified": status["auto_verified"],
           "needs_review": status["needs_review"], "fails": [f for r in rules for f in _fails(r)],
           "unaccounted": [f"{doc_id}:{i}" for i in unaccounted], "unread_pages": unread,
           "model": raw["model"], "prompt": PROMPT_VERSION,
           "usage": raw["usage"]}
    return rules, log


def rule_json(rule: dict) -> str:
    return json.dumps(rule, ensure_ascii=False, indent=1) + "\n"


def write_rules(rules: list[dict], out_dir: Path = OUT_DIR) -> list[Path]:
    """조건표 하나를 파일 하나로(이름은 id의 ":"를 "__"로). 쓴 경로를 돌려준다."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for r in rules:
        path = out_dir / (r["id"].replace(":", "__") + ".json")
        path.write_text(rule_json(r), encoding="utf-8")
        paths.append(path)
    return paths


# --- LLM 입력과 호출 ---

def _parts(section: list[dict], title: str | None) -> list[tuple[str | None, str]]:
    """LLM에 보낼 (트랙, 입력) 목록. 보통 하나다. 너무 길면 첫 트랙 제목 앞의 공통 줄 + 트랙 구간을 트랙마다 보낸다."""
    content = build_user_content(section, title=title)
    tracks = find_tracks(section) if len(content) > MAX_CONTENT else []
    if not tracks:
        return [(None, content)]
    starts = {t["line"]: t["track"] for t in tracks}
    common, groups, cur = [], {}, None
    for l in section:
        cur = starts.get(l["id"], cur)
        (groups.setdefault(cur, []) if cur else common).append(l)
    return [(track, build_user_content(common + seg, title=title)) for track, seg in groups.items()]


def _llm_outputs(parts: list[tuple[str | None, str]], model: str, *, use_cache: bool,
                 path: Path) -> tuple[list[dict], dict, dict]:
    """(출력 목록, 원응답 기록, 로그 조각). 키가 같은 원응답 파일이 있으면 부르지 않는다."""
    key = _sha(PROMPT_VERSION + model + "\n".join(content for _, content in parts))
    if use_cache and path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("key") == key:
                texts = raw["raw_text"] if isinstance(raw["raw_text"], list) else [raw["raw_text"]]
                return [json.loads(t) for t in texts], raw, {"llm_calls": 0, "schema_retries": 0, "cache": True}
        except (OSError, ValueError, KeyError):
            pass  # 깨진 원응답 파일은 새로 받는다
    results = [llm.call_json(SYSTEM, content, OUTPUT_SCHEMA, model=model) for _, content in parts]
    texts = [r.raw_text for r in results]
    raw = {"key": key, "model": results[0].model, "prompt": PROMPT_VERSION, "usage": _sum_usage(r.usage for r in results),
           "raw_text": texts[0] if len(texts) == 1 else texts, "at": datetime.now(KST).strftime("%Y-%m-%dT%H:%M")}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return ([r.data for r in results], raw,
            {"llm_calls": len(results), "schema_retries": sum(r.retries for r in results), "cache": False})


def _merge(parts: list[tuple[str | None, str]], outputs: list[dict]) -> dict:
    """트랙마다 나눠 받은 출력을 하나로. 트랙 구간에서 "main"으로 답한 조건표는 그 트랙 이름을 단다."""
    rules, labels = [], []
    for (track, _), data in zip(parts, outputs):
        for r in data.get("rules") or []:
            rules.append({**r, "track": track} if track and r.get("track") in (None, "", "main") else r)
        labels += data.get("labels") or []
    return {"rules": rules, "labels": labels}


# --- 조건표·로그 ---

def _as_other(c: dict) -> dict:
    """형식이 깨진 조건(field나 op가 없거나 any_of가 비었다)을 other로. 모델이 쓴 문장은 text에 남기고 확인 필요로 둔다."""
    keep = {k: c[k] for k in ("evidence", "as_of") if k in c}
    return {"field": "other", "text": c.get("text") or MALFORMED, "reason": "malformed", **keep}


def _bad(c: dict) -> bool:
    if c.get("field") == "other":
        return False
    return not c.get("field") or c.get("op") not in OPS or "value" not in c


def _region_value(c: dict) -> dict:
    """sido 값은 프로필과 같은 짧은 이름으로("서울특별시" → "서울"). 엔진은 sido 조건을 글자 그대로 비교한다.
    모델이 sido에 시군구("종로구")를 쓴 것은 sigungu 조건으로 옮긴다."""
    if c.get("field") != "sido" or "value" not in c:
        return c
    from backend.search.corpus import short_sido   # corpus가 notices.store를 거쳐 이 모듈을 불러서 여기서 부른다
    values = c["value"] if isinstance(c["value"], list) else [c["value"]]
    short = [short_sido(str(v)) for v in values]
    if all(short):
        fixed = list(dict.fromkeys(short))
        return {**c, "value": fixed if isinstance(c["value"], list) else fixed[0]}
    if not any(short) and all(re.search(r"(시|군|구)$", str(v)) for v in values):
        return {**c, "field": "sigungu"}
    return c


def _well_formed(c: dict) -> dict:
    """판정 엔진과 플래너는 field, op, value가 다 있는 조건만 받는다(없으면 문장을 만들다 멈춘다). 깨진 조건은 other로 바꾼다."""
    if "any_of" in c:
        branches = [[_as_other(x) if _bad(x) else _region_value(x) for x in b] for b in c.get("any_of") or [] if b]
        return {**c, "any_of": branches} if branches else _as_other(c)
    return _as_other(c) if _bad(c) else _region_value(c)


def _rule_ids(drafts: list[dict], doc_id: str, source: str) -> list[str]:
    """조건표가 하나이고 track이 main이면 "{source}:{doc_id}", 아니면 트랙 이름을 붙인다(겹치면 -2, -3).
    API 산문의 doc_id("gov24-WII…")는 앞의 "{source}-"를 떼어 서비스 ID("gov24:WII…", api.md §1·§7)와 맞춘다."""
    if source in API_SOURCES and doc_id.startswith(f"{source}-"):
        doc_id = doc_id[len(source) + 1:]
    slugs = [re.sub(r"[^a-z0-9_-]+", "_", str(d.get("track") or "").lower()).strip("_") or "main" for d in drafts]
    if slugs == ["main"]:
        return [f"{source}:{doc_id}"]
    used, out = set(), []
    for s in slugs:
        sid, n = s, 1
        while sid in used:
            n += 1
            sid = f"{s}-{n}"
        used.add(sid)
        out.append(f"{source}:{doc_id}:{sid}")
    return out


def _region(conds: list[dict], source: str, meta: dict):
    """api.md §1 region. 메타데이터가 먼저, 없으면 검사를 통과한 맨 위 sido(·sigungu) == 조건,
    그것도 없으면 중앙부처 산문은 전국(None), 나머지는 미상."""
    if "region" in meta:
        return meta["region"]
    top = {c.get("field"): c.get("value") for c in conds
           if c.get("op") == "==" and isinstance(c.get("value"), str) and c.get("status") in ("auto_verified", "reviewed")}
    if "sido" in top:
        return {"sido": top["sido"], "sigungu": top.get("sigungu")}
    return None if source == "central" else {"unknown": True}


def _fails(rule: dict) -> list[dict]:
    """떨어진 검사마다 로그 한 줄. any_of 가지의 실패(b가지.조건:사유)는 그 가지 조건의 field를 쓴다."""
    out = []
    for c in rule["conditions"]:
        for check, v in (c.get("checks") or {}).items():
            if not v.startswith("fail:"):
                continue
            reason = v[5:]
            m = _BRANCH.match(reason)
            sub = c["any_of"][int(m[1])][int(m[2])] if m and isinstance(c.get("any_of"), list) else c
            out.append({"rule_id": rule["id"], "field": sub.get("field") or "any_of", "check": check, "reason": reason,
                        "evidence": c.get("evidence") or []})
    return out


def _sum_usage(usages) -> dict:
    out: dict = {}
    for u in usages:
        for k, v in (u or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = out.get(k, 0) + v
    return out


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rel(path: Path) -> str:
    """레포 안이면 레포 루트 기준 경로, 밖이면 절대 경로."""
    try:
        return str(path.resolve().relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())
