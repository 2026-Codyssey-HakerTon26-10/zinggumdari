"""평가 입력은 담당자가 생성한 채점 기록. 미채점 값을 성공으로 채우지 않는다.

실행: python -m eval.score --input <채점기록.json> --output eval/results.json
정답 파일은 CLI에서 명시적으로 지정할 때만 읽는다.
"""

import argparse
from collections import Counter
import json
from pathlib import Path

VERDICTS = {"eligible", "ineligible", "needs_check", "opens_later", "no_rule"}


def condition_key(condition):
    keys = ("field", "op", "value", "as_of", "income_basis", "any_of", "text")
    value = {k: condition[k] for k in keys if k in condition}
    if "any_of" in value:
        value["any_of"] = [[json.loads(condition_key(c)) for c in branch] for branch in value["any_of"]]
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def extraction_score(gold, extracted):
    """중복 조건을 중복 정답으로 세지 않고 근거 줄별 빠짐도 계산한다."""
    available = Counter(condition_key(c) for c in gold)
    automatic, correct = 0, 0
    for c in extracted:
        if c.get("status") == "auto_verified":
            automatic += 1
            key = condition_key(c)
            if available[key] > 0:
                available[key] -= 1
                correct += 1
    all_keys = Counter(condition_key(c) for c in extracted if c.get("reason") != "unaccounted")
    flagged = {line for c in extracted if c.get("reason") == "unaccounted" for line in c.get("evidence", [])}
    missing = []
    for c in gold:
        key = condition_key(c)
        if all_keys[key]:
            all_keys[key] -= 1
        elif not (set(c.get("evidence", [])) & flagged):
            missing.append(c)
    return {"auto_verified": automatic, "correct": correct,
            "precision": correct / automatic if automatic else None,
            "silent_omissions": missing}


def verdict_score(rows):
    counts = Counter(total=0, matched=0, dangerous=0, missed=0)
    for row in rows:
        gold, predicted = row["expected"], row["actual"]
        if gold not in VERDICTS or predicted not in VERDICTS:
            raise ValueError("알 수 없는 판정 값")
        counts["total"] += 1
        counts["matched"] += gold == predicted
        counts["dangerous"] += predicted == "eligible" and gold == "ineligible"
        counts["missed"] += predicted == "ineligible" and gold != "ineligible"
    return dict(counts, accuracy=counts["matched"] / counts["total"] if counts["total"] else None)


def ranking_score(predictions, expected):
    if len(predictions) != len(expected):
        raise ValueError("추천과 정답의 가구 수가 다릅니다")
    if not predictions:
        return dict(n=0, recall_n=0, precision_at_5=None, recall_at_5=None)
    precision, recall = [], []
    for predicted, gold in zip(predictions, expected):
        selected = set(dict.fromkeys(predicted[:5]))
        gold = set(gold)
        hits = len(selected & gold)
        precision.append(hits / 5)
        if gold:
            recall.append(hits / len(gold))
    return dict(n=len(predictions), recall_n=len(recall), precision_at_5=sum(precision) / len(precision),
                recall_at_5=sum(recall) / len(recall) if recall else None)


def score(document, split=None):
    pairs = document.get("extraction", [])
    verdicts = document.get("verdicts", [])
    if (pairs or verdicts) and split is None:
        raise ValueError("개발용 채점에는 개발·시험 split이 필요합니다")
    test_ids = set((split or {}).get("test", []))
    dev_ids = set((split or {}).get("dev", []))
    if test_ids & dev_ids:
        raise ValueError("개발용과 시험용 제도가 겹칩니다")
    outside_ids = {r["id"] if isinstance(r, dict) else r for r in (split or {}).get("outside", [])}
    if outside_ids & (dev_ids | test_ids):
        raise ValueError("outside와 개발·시험 제도가 겹칩니다")
    if len({p["rule_id"] for p in pairs}) != len(pairs):
        raise ValueError("추출 제도가 중복됐습니다")
    seen = set()
    for row in verdicts:
        if not isinstance(row.get("user_id"), str) or not row["user_id"]:
            raise ValueError("판정 채점에는 user_id가 필요합니다")
        key = (row["user_id"], row.get("rule_id"))
        if key in seen:
            raise ValueError("가구·제도 판정이 중복됐습니다")
        seen.add(key)
    for row in pairs + verdicts:
        if row.get("rule_id") not in dev_ids:
            raise ValueError("개발용 rule_id만 채점할 수 있습니다(시험용·outside·미지정 제외)")
    extraction = [dict(rule_id=p["rule_id"], **extraction_score(p["gold"], p["extracted"])) for p in pairs]
    agreement = verdict_score(verdicts)
    sample = document.get("sample50")
    sample_meta = {}
    if isinstance(sample, dict):
        sample_meta = {k: sample.get(k) for k in ("seed", "population", "population_sha256")}
        sample = sample.get("rows")
        if sample is None:
            raise ValueError("표본의 rows가 필요합니다")
    if sample is not None and (len(sample) != 50 or any(type(r.get("correct")) is not bool for r in sample)):
        raise ValueError("표본 채점은 correct 불리언 50개여야 합니다")
    if sample is not None:
        refs = [(r.get("rule_id"), r.get("condition_index")) for r in sample]
        if any(not isinstance(rid, str) or not rid or type(i) is not int or i < 0 for rid, i in refs):
            raise ValueError("표본에는 rule_id와 condition_index가 필요합니다")
        if len(set(refs)) != 50:
            raise ValueError("같은 조건을 표본에서 중복 채점할 수 없습니다")
    verifier_rows = document.get("verifier")
    verifier = None
    if verifier_rows is not None:
        if any(type(r.get("correct")) is not bool or type(r.get("flagged")) is not bool for r in verifier_rows):
            raise ValueError("검증기 기여 채점은 correct·flagged 불리언이 필요합니다")
        verifier = {"llm_wrong": sum(not r["correct"] for r in verifier_rows),
                    "caught": sum(not r["correct"] and r["flagged"] for r in verifier_rows),
                    "llm_right": sum(r["correct"] for r in verifier_rows),
                    "flagged_right": sum(r["correct"] and r["flagged"] for r in verifier_rows)}
    return dict(
        status="scored" if pairs or verdicts or sample is not None or verifier_rows else "not_evaluated",
        evaluation_scope="dev_only",
        limitation="개발용은 프롬프트를 맞춘 집합입니다. 시험용은 채점하지 않았습니다.",
        verdicts=agreement, extraction=extraction,
        split={"dev": len(dev_ids), "test": len(test_ids)},
        precision_auto_verified={"test": None, "dev": {"correct": sum(r["correct"] for r in extraction),
                                          "n": sum(r["auto_verified"] for r in extraction)} if extraction else None,
                                 "sample": {"correct": sum(r["correct"] for r in sample), "n": 50, **sample_meta} if sample is not None else None},
        missed=sum(len(r["silent_omissions"]) for r in extraction) if extraction else None,
        agreement={"households": len({r["user_id"] for r in verdicts}) if verdicts else None,
                   "rules": len({r["rule_id"] for r in verdicts}) if verdicts else None,
                   "same": agreement["matched"] if verdicts else None,
                   "danger": agreement["dangerous"] if verdicts else None,
                   "missed_benefit": agreement["missed"] if verdicts else None},
        verifier=verifier,
        basis="가상 인구(가정 분포). 같은 규칙으로 만든 정답이며 분포 가정에 따라 값이 바뀝니다",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", default=Path("eval/results.json"), type=Path)
    parser.add_argument("--split", type=Path, help="담당자가 관리하는 개발·시험 분할 JSON")
    args = parser.parse_args()
    result = score(json.loads(args.input.read_text()), json.loads(args.split.read_text()) if args.split else None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
