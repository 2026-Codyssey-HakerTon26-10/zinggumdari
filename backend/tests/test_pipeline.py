"""compile 파이프라인, CLI 대량 실행, 손 조건표 quote 해석(SPEC §9.2, §10.2). LLM은 가짜 응답으로 바꾼다. 오프라인."""

import json
from pathlib import Path

import pytest

from backend.compiler import llm, pipeline
from backend.compiler.lines import to_lines
from backend.compiler.llm import LLMResult
from backend.compiler.pipeline import IngestRejected, compile, write_rules
from backend.compiler.resolve_manual import doc_of, resolve_rule
from backend.compiler.resolve_manual import main as resolve_main
from backend.compiler.readers import UnsupportedDocument
from backend.compiler.run import main as run_main
from backend.compiler.run import run_one
from backend.compiler.verify import CHECKS

DOC = "lh-demo"
SCAN = Path(__file__).parent / "fixtures" / "notice_scan.pdf"
NOTICE = """2026년 마포 신혼희망타운 입주자 모집공고
Ⅰ. 사업개요
공급위치: 서울특별시 마포구 일원, 총 120호
Ⅱ. 신청자격
1. 신혼부부 특별공급
○ 공고일 현재 무주택세대구성원
○ 혼인기간 7년 이내인 신혼부부
○ 만 19세 이상 39세 이하, 연소득 5천만 원 이하
○ 부부합산 연소득 7,500만 원 이하(본인 또는 배우자 연소득 5,000만 원 이하도 가능)
○ 총자산 3억 4,500만 원 이하
○ 해당 지역 거주자 우선
2. 청년 공급
○ 만 19세 이상 39세 이하인 미혼 무주택자
※ 무주택세대구성원이란 세대원 전원이 주택을 소유하지 않은 세대를 말합니다.
○ 다른 공공주택과 중복 신청 불가
Ⅲ. 신청방법
인터넷 청약: LH청약플러스
"""


def c(field, op=None, value=None, ev=(), basis=None, as_of=None, text=None, any_of=None):
    """모델 출력 모양의 조건(모든 칸이 있고 null)."""
    return {"field": field, "op": op, "value": value, "income_basis": basis, "as_of": as_of, "text": text,
            "evidence": list(ev), "any_of": any_of}


def sub(field, op, value, basis=None):
    return {"field": field, "op": op, "value": value, "income_basis": basis, "as_of": None, "text": None}


def r(track, conditions, name="마포 신혼희망타운"):
    return {"track": track, "name": name, "subject": "self", "domain": "subscription", "benefit_type": "rent",
            "aliases": ["신혼희망타운"], "conditions": conditions, "documents": []}


NEWLYWED = r("newlywed", [
    c("is_homeless", "==", "Y", ["l6"], as_of="notice_date"),
    c("marriage_years", "<=", 7, ["l7"]),
    c("age", ">=", 19, ["l8"]),
    c("age", "<=", 39, ["l8"]),
    c("age", "<=", 5000, ["l8"]),                                   # 틀린 조건: 소득 금액을 나이로
    c("income_self", "<=", 5000, ["l8"], basis="absolute_annual"),
    c(None, ev=["l9", "l7"], any_of=[                                # 신혼(l7)과 소득(l9)
        [sub("income_couple", "<=", 7500, "absolute_annual")],
        [sub("marital_status", "in", ["신혼"]), sub("income_self", "<=", 5000, "absolute_annual")],
        [sub("marital_status", "in", ["신혼"]), sub("income_spouse", "<=", 5000, "absolute_annual")],
    ]),
    c("other", ev=["l10"], text="총자산 3억 4,500만 원 이하"),
], name="마포 신혼희망타운 신혼부부 특별공급")
YOUTH = r("youth", [
    c("age", ">=", 19, ["l13"]),
    c("age", "<=", 39, ["l13"]),
    c("is_homeless", "==", "Y", ["l13"]),
    c("marital_status", "in", ["미혼"], ["l13"]),
], name="마포 신혼희망타운 청년")
LABELS = [{"line": "l5", "label": "not_condition"}, {"line": "l14", "label": "definition"},
          {"line": "l15", "label": "exclusive"}, {"line": "l99", "label": "procedure"}]   # l99는 없는 줄
OUTPUT = {"rules": [NEWLYWED, YOUTH], "labels": LABELS}           # l11(거주)은 근거도 라벨도 없다


class FakeLLM:
    """llm.call_json 대신. respond(content) → 출력 dict."""

    def __init__(self, respond):
        self.respond, self.contents = respond, []

    def __call__(self, system, content, schema, *, model=None, **kw):
        self.contents.append(content)
        data = self.respond(content)
        return LLMResult(data=data, raw_text=json.dumps(data, ensure_ascii=False), model="claude-test-1",
                         usage={"input_tokens": 1000, "output_tokens": 200}, retries=0)


@pytest.fixture
def fake(monkeypatch):
    def install(respond=lambda content: OUTPUT):
        f = FakeLLM(respond)
        monkeypatch.setattr(llm, "call_json", f)
        return f
    return install


@pytest.fixture
def lines():
    return to_lines(DOC, NOTICE)


def run(lines, tmp_path, **kw):
    return compile(DOC, lines, "upload", meta={"org": "LH", "source_url": "https://example.test/n/1", "fetched_at": "2026-10-31"},
                   model="claude-test", raw_dir=tmp_path / "raw", return_log=True, **kw)


# --- 한 바퀴 ---

def test_end_to_end(fake, lines, tmp_path):
    f = fake()
    rules, log = run(lines, tmp_path)
    assert len(f.contents) == 1
    assert "l4\t \tⅡ. 신청자격" in f.contents[0] and "l17" not in f.contents[0]   # 자격 구간만 보낸다
    assert [x["id"] for x in rules] == [f"upload:{DOC}:newlywed", f"upload:{DOC}:youth"]

    nw, youth = rules
    assert nw["source"] == "upload" and nw["org"] == "LH" and nw["region"] == {"unknown": True}  # sido 조건이 없다
    assert nw["detail_url"] == "https://example.test/n/1" and nw["updated"] == "2026-10-31"
    assert nw["review"] == {"status": "unreviewed"}
    assert nw["exclusive_evidence"] == youth["exclusive_evidence"] == [f"{DOC}:l15"]
    statuses = [x["status"] for x in nw["conditions"]]
    assert statuses == ["auto_verified"] * 4 + ["needs_review", "auto_verified", "auto_verified"] + ["needs_review"] * 2
    wrong = nw["conditions"][4]
    assert wrong["value"] == 5000 and wrong["checks"]["unit"] == "fail:unit_mismatch"
    assert set(wrong["checks"]) == set(CHECKS)
    any_of = nw["conditions"][6]
    assert len(any_of["any_of"]) == 3 and any_of["evidence"] == [f"{DOC}:l9", f"{DOC}:l7"]
    assert nw["conditions"][0]["as_of"] == "notice_date"
    assert [x["status"] for x in youth["conditions"]] == ["auto_verified"] * 4 + ["needs_review"]

    # 빠짐 검사: l11은 모든 조건표에 미반영 조건으로
    for rule in rules:
        assert rule["conditions"][-1] == {"field": "other", "text": "원문 조건 미반영", "reason": "unaccounted",
                                          "evidence": [f"{DOC}:l11"], "status": "needs_review"}
    labeled = {"definition": 1, "procedure": 0, "exclusive": 1, "out_of_scope": 0, "not_condition": 1}
    assert nw["coverage"] == {"marked": 10, "used": 5, "labeled": labeled, "unaccounted": 1}
    assert youth["coverage"] == {"marked": 10, "used": 1, "labeled": labeled, "unaccounted": 1}

    comp = nw["compiled"]
    assert comp["model"] == "claude-test-1" and comp["prompt"] == pipeline.PROMPT_VERSION
    assert len(comp["doc_sha256"]) == 64 and len(comp["at"]) == 16
    raw = json.loads((tmp_path / "raw" / f"{DOC}.json").read_text(encoding="utf-8"))
    assert comp["raw"] == str((tmp_path / "raw" / f"{DOC}.json").resolve())   # 레포 밖이면 절대 경로
    assert set(raw) == {"key", "model", "prompt", "usage", "raw_text", "at"} and json.loads(raw["raw_text"]) == OUTPUT

    assert list(log) == ["doc_id", "lines", "section", "marked", "llm_calls", "schema_retries", "cache", "rules", "conditions",
                         "auto_verified", "needs_review", "fails", "unaccounted", "unread_pages", "model", "prompt", "usage"]
    assert log["section"]["from"] == "l4" and log["section"]["found_by"] == "heading"
    assert (log["lines"], log["marked"], log["llm_calls"], log["cache"], log["rules"]) == (17, 10, 1, False, 2)
    assert (log["conditions"], log["auto_verified"], log["needs_review"]) == (14, 10, 4)
    assert log["unaccounted"] == [f"{DOC}:l11"]
    assert {(x["rule_id"], x["field"], x["check"], x["reason"]) for x in log["fails"]} == {
        (f"upload:{DOC}:newlywed", "age", "unit", "unit_mismatch"),
        (f"upload:{DOC}:newlywed", "age", "keyword", "keyword_not_in_clause")}
    assert log["fails"][0]["evidence"] == [f"{DOC}:l8"]
    assert log["usage"] == {"input_tokens": 1000, "output_tokens": 200}


def test_any_of_branch_failure_names_branch_field(fake, lines, tmp_path):
    bad = r("main", [c(None, ev=["l9"], any_of=[[sub("income_couple", "<=", 7500, "absolute_annual")],
                                                [sub("income_spouse", "<=", 6000, "absolute_annual")]])])
    fake(lambda content: {"rules": [bad], "labels": []})
    rules, log = run(lines, tmp_path)
    assert rules[0]["conditions"][0]["status"] == "needs_review"
    assert {(x["field"], x["check"], x["reason"]) for x in log["fails"]} >= {("income_spouse", "value", "b1.0:not_in_evidence")}


def test_cache_replay(fake, lines, tmp_path):
    f = fake()
    first, _ = run(lines, tmp_path)
    again, log = run(lines, tmp_path)
    assert len(f.contents) == 1                       # 두 번째는 원응답 파일을 다시 읽는다
    assert log["cache"] is True and log["llm_calls"] == 0 and log["model"] == "claude-test-1"
    assert again == first
    run(lines, tmp_path, use_cache=False)
    assert len(f.contents) == 2
    changed = [dict(l, text=l["text"].replace("7년", "5년")) for l in lines]   # 입력이 바뀌면 키가 바뀐다
    run(changed, tmp_path)
    assert len(f.contents) == 3


def test_rrn_rejected_before_llm(fake, lines, tmp_path):
    f = fake()
    bad = lines + [{"id": "l18", "page": None, "bbox": None, "text": "신청인 000101-3000000", "mark": False}]
    with pytest.raises(IngestRejected, match="주민등록번호"):
        run(bad, tmp_path)
    assert f.contents == [] and not (tmp_path / "raw").exists()
    with pytest.raises(IngestRejected, match="글자를 읽지 못한"):
        run([], tmp_path)


def test_marks_added_when_missing(fake, lines, tmp_path):
    fake()
    bare = [{k: v for k, v in l.items() if k != "mark"} for l in lines]
    _, log = run(bare, tmp_path)
    assert log["marked"] == 10


def test_rule_ids(fake, lines, tmp_path):
    fake(lambda content: {"rules": [r("main", YOUTH["conditions"])], "labels": []})
    rules, _ = run(lines, tmp_path, use_cache=False)
    assert [x["id"] for x in rules] == [f"upload:{DOC}"]
    fake(lambda content: {"rules": [NEWLYWED, NEWLYWED, r("Special Track!", [])], "labels": []})
    rules, _ = run(lines, tmp_path, use_cache=False)
    assert [x["id"] for x in rules] == [f"upload:{DOC}:newlywed", f"upload:{DOC}:newlywed-2", f"upload:{DOC}:special_track"]


def test_zero_rules_still_logs(fake, lines, tmp_path):
    fake(lambda content: {"rules": [], "labels": []})
    rules, log = run(lines, tmp_path)
    assert rules == []
    assert log["rules"] == 0 and log["conditions"] == 0 and len(log["unaccounted"]) == 10


def test_long_section_split_by_track(fake, lines, tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline, "MAX_CONTENT", 100)
    f = fake(lambda content: {"rules": [r("main", YOUTH["conditions"] if "청년 공급" in content else NEWLYWED["conditions"])],
                              "labels": LABELS})
    rules, log = run(lines, tmp_path)
    assert len(f.contents) == 2 and log["llm_calls"] == 2
    assert all("l4\t" in x for x in f.contents)                         # 공통 줄은 트랙마다
    assert "l7\t" in f.contents[0] and "l7\t" not in f.contents[1]
    assert "l13\t" in f.contents[1] and "l13\t" not in f.contents[0]
    assert [x["id"] for x in rules] == [f"upload:{DOC}:newlywed", f"upload:{DOC}:youth"]
    assert log["usage"] == {"input_tokens": 2000, "output_tokens": 400}
    _, again = run(lines, tmp_path)                                     # 나눠 받은 원응답도 캐시 재생
    assert again["cache"] is True and len(f.contents) == 2


def test_write_rules(fake, lines, tmp_path):
    fake()
    rules, _ = run(lines, tmp_path)
    paths = write_rules(rules, tmp_path / "out")
    assert [p.name for p in paths] == [f"upload__{DOC}__newlywed.json", f"upload__{DOC}__youth.json"]
    text = paths[0].read_text(encoding="utf-8")
    assert "신혼부부" in text                                             # ensure_ascii=False
    assert json.loads(text) == rules[0]


# --- CLI ---

def test_cli_src(fake, tmp_path, capsys):
    fake()
    src = tmp_path / "notice.txt"
    src.write_text(NOTICE, encoding="utf-8")
    code = run_main(["--src", str(src), "--doc-id", DOC, "--model", "claude-test", "--out", str(tmp_path / "out"),
                     "--raw-dir", str(tmp_path / "raw")])
    assert code == 0
    log = json.loads(capsys.readouterr().out)
    assert log["rules"] == 2 and log["needs_review"] == 4
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [f"upload__{DOC}__newlywed.json", f"upload__{DOC}__youth.json"]
    rule = json.loads((tmp_path / "out" / f"upload__{DOC}__newlywed.json").read_text(encoding="utf-8"))
    assert len(rule["compiled"]["doc_sha256"]) == 64


def test_cli_bulk_resume(fake, tmp_path, capsys):
    out = {"rules": [{"track": "main", "name": "노인 돌봄", "subject": "parent", "domain": "elderly", "benefit_type": "service",
                      "aliases": [], "documents": [], "conditions": [c("age", ">=", 65, ["l1"])]}], "labels": []}
    f = fake(lambda content: out)
    items = [
        {"doc_id": "WII001", "source": "gov24", "text": "지원대상: 만 65세 이상 노인\n신청방법: 주민센터 방문", "title": "노인 돌봄"},
        {"doc_id": "WII002", "source": "gov24", "text": "지원대상: 만 65세 이상 기초연금 수급자"},
        {"doc_id": "WII003", "source": "gov24", "text": "지원대상: 중소기업 근로자"},          # 단계 말이 없어 걸러진다
        {"doc_id": "WII004", "source": "gov24", "text": "노인 지원 문의 000101-3000000"},   # 주민번호 → 실패
    ]
    path = tmp_path / "gov24.jsonl"
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items), encoding="utf-8")
    args = ["--bulk", str(path), "--stage-filter", "--workers", "2", "--model", "claude-test",
            "--out", str(tmp_path / "out"), "--raw-dir", str(tmp_path / "raw")]
    assert run_main(args) == 0
    summary = json.loads(capsys.readouterr().out)
    assert {k: summary[k] for k in ("items", "done", "skipped", "failed", "rules")} == \
        {"items": 3, "done": 2, "skipped": 0, "failed": 1, "rules": 2}
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["gov24__WII001.json", "gov24__WII002.json"]
    rule = json.loads((tmp_path / "out" / "gov24__WII001.json").read_text(encoding="utf-8"))
    assert rule["id"] == "gov24:WII001" and rule["conditions"][0]["status"] == "auto_verified"
    failures = [json.loads(s) for s in (tmp_path / "raw" / "bulk_failures.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["doc_id"] for x in failures] == ["WII004"] and "IngestRejected" in failures[0]["error"]
    assert len(f.contents) == 2

    assert run_main(args) == 0                                          # 다시 돌리면 이미 만든 건은 건너뛴다
    summary = json.loads(capsys.readouterr().out)
    assert (summary["done"], summary["skipped"], summary["failed"]) == (0, 2, 1)
    assert len(f.contents) == 2


# --- 손 조건표 quote ---

NOTICE_LINES = [{"id": f"l{i}", "page": None, "bbox": None, "text": t, "mark": True} for i, t in enumerate([
    "○ 혼인기간 7년 이내인 신혼부부",
    "무주택 세대주",
    "부부합산 연소득 7,500만 원 이하",
    "무주택 세대주로서 신청한 자",
], 1)]


def manual(*conds, **kw):
    return {"id": "manual:demo", "source": "manual", "conditions": list(conds), **kw}


def test_resolve_found_whitespace_insensitive():
    rule = manual({"field": "marriage_years", "op": "<=", "value": 7, "quote": "…혼인 기간 7년이내…", "status": "reviewed"})
    assert resolve_rule(rule, NOTICE_LINES, "nhuf") == []
    assert rule["conditions"][0]["evidence"] == ["nhuf:l1"]
    assert rule["conditions"][0]["quote"] == "…혼인 기간 7년이내…"


def test_resolve_multi_fragment_any_of_ordered():
    group = {"any_of": [[{"field": "income_couple", "op": "<=", "value": 7500, "income_basis": "absolute_annual"}]],
             "quote": "부부합산 연소득 7,500만 원 이하...혼인기간 7년 이내…무주택 세대주", "evidence": ["nhuf:l4"]}
    rule = manual(group)
    assert resolve_rule(rule, NOTICE_LINES, "nhuf") == []
    assert group["evidence"] == ["nhuf:l1", "nhuf:l3", "nhuf:l4"]   # 원문 순서. "무주택 세대주"는 이미 적힌 l4를 쓴다


def test_resolve_not_found_keeps_evidence():
    rule = manual({"field": "marriage_years", "op": "<=", "value": 5, "quote": "혼인기간 7년…혼인기간 5년 이내",
                   "evidence": ["nhuf:l1"]},
                  {"field": "is_homeless", "op": "==", "value": "Y", "quote": "무주택"})          # 4자 미만
    errors = resolve_rule(rule, NOTICE_LINES, "nhuf")
    assert len(errors) == 2 and "혼인기간 5년 이내" in errors[0] and "manual:demo 조건 0" in errors[0]
    assert rule["conditions"][0]["evidence"] == ["nhuf:l1"] and "evidence" not in rule["conditions"][1]


def test_doc_of():
    assert doc_of(manual(doc_id="x")) == "x"
    assert doc_of(manual({"evidence": ["nhuf:l1"]}, {"evidence": ["nhuf:l3"]})) == "nhuf"
    with pytest.raises(ValueError):
        doc_of(manual({"quote": "무주택 세대주"}))


def test_resolve_manual_cli(tmp_path, capsys):
    notices = tmp_path / "notices"
    notices.mkdir()
    (notices / "nhuf.lines.json").write_text(json.dumps(NOTICE_LINES, ensure_ascii=False), encoding="utf-8")
    good = tmp_path / "good.json"
    good.write_text(json.dumps(manual({"field": "marriage_years", "op": "<=", "value": 5, "quote": "혼인기간 7년 이내",
                                       "status": "reviewed"}, doc_id="nhuf"), ensure_ascii=False), encoding="utf-8")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(manual({"field": "age", "op": ">=", "value": 19, "quote": "만 19세 이상"}, doc_id="nhuf"),
                              ensure_ascii=False), encoding="utf-8")
    assert resolve_main([str(good), str(bad), "--notices", str(notices)]) == 1
    printed = capsys.readouterr().out
    assert "실패 manual:demo 조건 0: 원문에서 못 찾음 '만 19세 이상'" in printed
    assert "경고 manual:demo 조건 0: value=not_in_evidence" in printed     # 값 5가 근거 줄에 없다(상태는 그대로)
    saved = json.loads(good.read_text(encoding="utf-8"))
    assert saved["conditions"][0]["evidence"] == ["nhuf:l1"] and saved["conditions"][0]["status"] == "reviewed"
    assert "checks" not in saved["conditions"][0]


# --- 검토 지적 재현 ---

SHORT = """Ⅱ. 신청자격
○ 공고일 현재 무주택세대구성원
○ 전년도 도시근로자 가구원수별 월평균소득 120% 이하
Ⅲ. 신청방법
인터넷 청약
"""


def _ids(lines, *needles):
    return [next(l["id"] for l in lines if n in l["text"]) for n in needles]


def test_piggyback_evidence_does_not_hide_dropped_condition(fake, tmp_path):
    # 소득 줄을 무주택 조건의 근거에 끼워 넣고 소득 조건을 빼도, 소득 줄은 미반영으로 남는다
    lines = to_lines("d", SHORT)
    homeless, income = _ids(lines, "무주택세대구성원", "120%")
    fake(lambda content: {"rules": [r("main", [c("is_homeless", "==", "Y", [homeless, income])])], "labels": []})
    (rule,), log = compile("d", lines, "upload", model="m", raw_dir=tmp_path, return_log=True)
    assert rule["conditions"][0]["status"] == "auto_verified"
    assert log["unaccounted"] == [f"d:{income}"]
    assert rule["coverage"]["used"] == 1


def test_unmarked_condition_lines_are_unaccounted(fake, tmp_path):
    notice = SHORT.replace("Ⅲ.", "○ 세대구성원 전원이 주택을 소유하고 있지 아니할 것\n○ 공고일 현재 서울특별시에 주민등록이 되어 있는 자\n"
                           "○ 접수기간: 2026. 11. 3. ~ 2026. 11. 14. 18:00까지\n※ 대학생은 이 공고로 신청할 수 없습니다.\nⅢ.")
    lines = to_lines("d", notice)
    homeless, income = _ids(lines, "무주택세대구성원", "120%")
    fake(lambda content: {"rules": [r("main", [c("is_homeless", "==", "Y", [homeless]),
                                               c("income_household", "<=", 120, [income], "urban_worker_pct")])],
                          "labels": []})
    _, log = compile("d", lines, "upload", model="m", raw_dir=tmp_path, return_log=True)
    want = _ids(lines, "소유하고 있지", "주민등록", "접수기간", "대학생")
    assert log["unaccounted"] == [f"d:{i}" for i in want]


def test_region(fake, tmp_path):
    lines = to_lines("d", "Ⅱ. 신청자격\n○ 공고일 현재 서울특별시에 거주하는 무주택 청년\n")
    seoul = c("sido", "==", "서울특별시", ["l2"])
    fake(lambda content: {"rules": [r("main", [seoul])], "labels": []})
    assert compile("d", lines, "upload", raw_dir=tmp_path)[0]["region"] == {"sido": "서울특별시", "sigungu": None}
    assert compile("d", lines, "upload", meta={"region": None}, raw_dir=tmp_path)[0]["region"] is None  # 메타데이터가 먼저
    fake(lambda content: {"rules": [r("main", [c("sido", "==", "부산광역시", ["l2"])])], "labels": []})
    assert compile("d", lines, "upload", use_cache=False, raw_dir=tmp_path)[0]["region"] == {"unknown": True}  # 검사 실패
    fake(lambda content: {"rules": [r("main", [])], "labels": []})
    assert compile("d", lines, "central", use_cache=False, raw_dir=tmp_path)[0]["region"] is None


def test_updated_defaults_to_today(fake, lines, tmp_path):
    fake()
    rule = compile(DOC, lines, "upload", raw_dir=tmp_path)[0]
    assert rule["updated"] == pipeline.datetime.now(pipeline.KST).date().isoformat()


def test_api_rule_id_matches_service_id(fake, tmp_path):
    fake(lambda content: {"rules": [r("main", [])], "labels": []})
    lines = to_lines("gov24-WII000001", "만 19세 이상 39세 이하 청년")
    assert compile("gov24-WII000001", lines, "gov24", raw_dir=tmp_path)[0]["id"] == "gov24:WII000001"
    lines = to_lines("upload-20261031-01", "만 19세 이상 39세 이하 청년")   # 업로드는 doc_id 그대로(api.md §6)
    assert compile("upload-20261031-01", lines, "upload", raw_dir=tmp_path)[0]["id"] == "upload:upload-20261031-01"


def test_cli_missing_src_file_fails_without_llm(fake, tmp_path, capsys):
    f = fake()
    code = run_main(["--src", str(tmp_path / "notices/mapo.pdf"), "--doc-id", "mapo", "--out", str(tmp_path / "out"),
                     "--raw-dir", str(tmp_path / "raw")])
    assert code == 1 and f.contents == []
    assert run_main(["--text", NOTICE, "--doc-id", DOC, "--out", str(tmp_path / "out"), "--raw-dir", str(tmp_path / "raw")]) == 0
    assert len(f.contents) == 1


def test_saved_meta_shape(fake, tmp_path, monkeypatch):
    from backend.compiler import run as run_mod
    from backend.compiler.lines import save_lines
    monkeypatch.setattr(run_mod, "save_lines", lambda d, ls, meta=None: save_lines(d, ls, meta, out_dir=tmp_path / "notices"))
    fake()
    src = tmp_path / "n.txt"
    src.write_text(NOTICE, encoding="utf-8")
    run_one(src, DOC, save=True, title="마포 공고", url="https://example.test/1", out_dir=tmp_path / "out", raw_dir=tmp_path / "raw")
    meta = json.loads((tmp_path / "notices" / f"{DOC}.meta.json").read_text(encoding="utf-8"))
    assert meta["section"]["found_by"] == "heading" and meta["rules"] == [f"upload:{DOC}:newlywed", f"upload:{DOC}:youth"]
    assert (meta["source"], meta["title"], meta["source_url"]) == ("upload", "마포 공고", "https://example.test/1")
    assert isinstance(meta["lines"], list) and meta["n_lines"] == len(meta["lines"]) == 17   # 텍스트는 줄 목록(api.md §8)


def test_scan_ocr_counted_and_cached(fake, tmp_path, monkeypatch):
    monkeypatch.setenv("ZINGGUM_OCR", "llm")
    calls = []

    def ocr_ok(png, *, model=None):
        calls.append(png)
        return LLMResult(data={"lines": ["1. 지원대상", "○ 만 19세 이상 39세 이하 무주택 청년"]}, raw_text="", model="ocr-model",
                         usage={"input_tokens": 5000})
    monkeypatch.setattr(llm, "ocr_page", ocr_ok)
    fake(lambda content: {"rules": [], "labels": []})
    kw = {"out_dir": tmp_path / "out", "raw_dir": tmp_path / "raw", "source": "lh"}   # 우리가 넣는 공고 원문만 네이토 글자 인식
    log, _ = run_one(SCAN, "scan-c", **kw)
    assert len(calls) == 1 and log["llm_calls"] == 2 and log["ocr_calls"] == 1      # 글자 인식 1 + 조건 읽기 1
    assert (log["ocr"], log["ocr_model"], log["ocr_usage"]) == ("llm", "ocr-model", {"input_tokens": 5000})

    def offline(png, *, model=None):
        raise llm.LLMError("network down")
    monkeypatch.setattr(llm, "ocr_page", offline)
    log, _ = run_one(SCAN, "scan-c", **kw)                                         # 캐시 재생: 다시 부르지 않는다
    assert log["cache"] is True and log["llm_calls"] == 0 and log.get("ocr_calls") is None
    with pytest.raises(UnsupportedDocument, match="글자 인식에 실패"):           # 캐시를 안 쓰면 인식 실패를 알린다
        run_one(SCAN, "scan-c", use_cache=False, **kw)


def test_upload_raw_goes_to_uncommitted_dir(fake, tmp_path, monkeypatch):
    """사용자 업로드 원응답은 커밋하는 rules/compiled/_raw가 아니라 rules/uploads/_raw에 쓰고, 탈퇴 때 지운다."""
    monkeypatch.setattr(pipeline, "UPLOAD_RAW_DIR", tmp_path / "uploads_raw")
    monkeypatch.setattr(pipeline, "RAW_DIR", tmp_path / "compiled_raw")
    fake(lambda content: {"rules": [], "labels": []})
    lines = to_lines("upload-1", "1. 신청자격\n○ 만 19세 이상 무주택자")
    compile("upload-1", lines, "upload")
    compile("lh-1", to_lines("lh-1", "1. 신청자격\n○ 만 19세 이상 무주택자"), "lh")
    assert (tmp_path / "uploads_raw" / "upload-1.json").exists()
    assert (tmp_path / "compiled_raw" / "lh-1.json").exists()
    assert not (tmp_path / "compiled_raw" / "upload-1.json").exists()
    (tmp_path / "uploads_raw" / "upload-1.ocr.json").write_text("{}")
    assert pipeline.delete_raw("upload-1") == 2
    assert list((tmp_path / "uploads_raw").iterdir()) == []


@pytest.mark.parametrize("field", ["qual_code", "history"])
def test_unverifiable_code_does_not_hide_missing_condition(fake, tmp_path, field):
    """원문에 없는 자격·이력 코드를 나이 줄의 근거로 대도 auto_verified가 아니고, 빠진 나이 조건의 줄은 미반영으로 남는다."""
    lines = to_lines("d", "1. 신청자격\n○ 신청자는 만 19세 이상이어야 합니다.")
    (age,) = _ids(lines, "만 19세")
    fake(lambda content: {"rules": [r("main", [c(field, "in", ["가공의자격"], [age])])], "labels": []})
    (rule,), log = compile("d", lines, "upload", model="m", raw_dir=tmp_path, return_log=True)
    cond = rule["conditions"][0]
    assert cond["status"] == "needs_review" and cond["checks"]["value"] == "fail:unverifiable"
    assert log["unaccounted"] == [f"d:{age}"]
    assert rule["coverage"]["used"] == 0


def test_unread_pages_add_needs_review_condition(fake, lines, tmp_path):
    """글자를 읽지 못한 쪽이 있으면 조건표마다 근거 없는 확인 필요 조건이 붙는다(그 쪽의 조건은 빠짐 검사로도 못 잡는다)."""
    fake()
    rules, log = compile(DOC, lines, "upload", meta={"unread_pages": [5, 3]}, model="m", raw_dir=tmp_path, return_log=True)
    assert log["unread_pages"] == [3, 5]
    for rule in rules:
        last = rule["conditions"][-1]
        assert last == {"field": "other", "text": pipeline.UNREAD, "reason": "unread_pages", "pages": [3, 5],
                        "evidence": [], "status": "needs_review"}
    rules, log = compile(DOC, lines, "upload", model="m", raw_dir=tmp_path, return_log=True)
    assert log["unread_pages"] == [] and not any(c.get("reason") == "unread_pages" for r_ in rules for c in r_["conditions"])


def test_upload_rules_go_to_uncommitted_dir(fake, tmp_path, monkeypatch):
    """CLI 한 건도 source가 upload면 조건표를 rules/compiled가 아니라 rules/uploads에 쓴다."""
    monkeypatch.setattr(pipeline, "UPLOAD_OUT_DIR", tmp_path / "uploads")
    monkeypatch.setattr(pipeline, "OUT_DIR", tmp_path / "compiled")
    fake()
    _, paths = run_one(NOTICE, "upload-2", raw_dir=tmp_path / "raw")
    assert paths and all(p.parent == tmp_path / "uploads" for p in paths)
    _, paths = run_one(NOTICE, "lh-2", source="lh", raw_dir=tmp_path / "raw")
    assert paths and all(p.parent == tmp_path / "compiled" for p in paths)
