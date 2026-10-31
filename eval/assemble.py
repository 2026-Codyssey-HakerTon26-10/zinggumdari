"""별도 검토 기록을 고정 평가 입력과 결합한다. 입력이 바뀌면 재검토 없이 사용하지 않는다."""

import argparse
import hashlib
import json
from pathlib import Path

from eval.score import score


def apply_grades(input_path, review_path, key):
    raw = Path(input_path).read_bytes()
    source, review = json.loads(raw), json.loads(Path(review_path).read_text())
    if hashlib.sha256(raw).hexdigest() != review["input_sha256"]:
        raise ValueError("채점 후 입력 파일이 바뀌었습니다")
    labels = {(r["rule_id"], r["index"]): r for r in review["rows"]}
    if len(labels) != len(review["rows"]) or len(labels) != len(source[key]):
        raise ValueError("검토 기록이 중복되거나 빠졌습니다")
    rows = []
    for row in source[key]:
        label = labels[(row["rule_id"], row["index"])]
        digest = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if digest != label["row_sha256"] or type(label["correct"]) is not bool:
            raise ValueError("조건이 바뀌었거나 미채점 상태입니다")
        rows.append({**row, "condition_index": row["index"], "correct": label["correct"], "memo": label["memo"]})
    return rows, review["source_commit"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs-dir", required=True, type=Path)
    parser.add_argument("--reviews-dir", type=Path, default=Path("eval/reviews"))
    parser.add_argument("--split", type=Path, default=Path("eval/split.json"))
    parser.add_argument("--agreement", type=Path, help="eval.agreement의 실제 가상 인구 비교 결과")
    parser.add_argument("--output", type=Path, default=Path("eval/results.json"))
    args = parser.parse_args()
    document = json.loads((args.inputs_dir / "score_input.json").read_text())
    sample, sample_commit = apply_grades(args.inputs_dir / "sample50.json", args.reviews_dir / "sample50.json", "sample50")
    verifier, verifier_commit = apply_grades(args.inputs_dir / "verifier_dev.json", args.reviews_dir / "verifier_dev.json", "verifier")
    if sample_commit != verifier_commit:
        parser.error("표본과 검증기 채점의 스냅샷이 다릅니다")
    sample_source = json.loads((args.inputs_dir / "sample50.json").read_text())
    document.update(sample50={"rows": sample, "seed": sample_source["seed"], "population": sample_source["pool"],
                              "population_sha256": None}, verifier=verifier)
    agreement = json.loads(args.agreement.read_text()) if args.agreement else None
    if agreement is not None:
        document["verdicts"] = agreement["verdicts"]
    result = score(document, json.loads(args.split.read_text()))
    result["source_snapshot"] = {"commit": sample_commit, "pr": 54,
                                 "status": "PR 스냅샷 기준; main 병합 여부와 독립 판정 일치 평가를 별도로 확인해야 함",
                                 "inputs_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                                    for p in sorted(args.inputs_dir.glob("*.json"))}}
    if agreement is not None:
        result["agreement_source"] = {k:v for k,v in agreement.items() if k != "verdicts"}
    result["scoring_method"] = "조건 키 엄격 일치(자동 집계) + 원문 근거 대조(Codex 보조 평가); other 근거 겹침만으로 정답 인정하지 않음"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
