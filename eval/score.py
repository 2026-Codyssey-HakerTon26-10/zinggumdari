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
    keys = ("field", "op", "value", "as_of", "income_basis", "any_of")
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
        return dict(n=0, precision_at_5=None, recall_at_5=None)
    precision, recall = [], []
    for predicted, gold in zip(predictions, expected):
        selected = set(dict.fromkeys(predicted[:5]))
        gold = set(gold)
        hits = len(selected & gold)
        precision.append(hits / 5)
        if gold:
            recall.append(hits / len(gold))
    return dict(n=len(predictions), precision_at_5=sum(precision) / len(precision),
                recall_at_5=sum(recall) / len(recall) if recall else None)


def score(document):
    return dict(
        verdicts=verdict_score(document.get("verdicts", [])),
        extraction=[extraction_score(pair["gold"], pair["extracted"]) for pair in document.get("extraction", [])],
        basis="가상 인구(가정 분포). 같은 규칙으로 만든 정답이며 분포 가정에 따라 값이 바뀝니다",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", default=Path("eval/results.json"), type=Path)
    args = parser.parse_args()
    result = score(json.loads(args.input.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
