from datetime import date

from eval.knn_test import baseline_pick, split_holdout


def test_split_holdout_is_fixed_and_disjoint():
    ids = [f"u{i}" for i in range(11)]
    validation, test = split_holdout(ids, 42)
    assert (validation, test) == split_holdout(list(reversed(ids)), 42)
    assert not set(validation) & set(test) and set(validation) | set(test) == set(ids)
    assert len(validation) == 5


def test_baseline_uses_same_filters_and_type_cap():
    rules = [dict(id=str(i), subject="self", benefit_type="cash") for i in range(4)]
    rules.append(dict(id="parent", subject="parent", benefit_type="loan"))
    rules.append(dict(id="busan", subject="self", benefit_type="loan", region={"sido": "부산"}))
    verdicts = {r["id"]: {"verdict": "needs_check"} for r in rules}
    verdicts["0"] = {"verdict": "eligible"}
    verdicts["3"] = {"verdict": "needs_check", "deadline": "2026-10-31"}
    picked = baseline_pick(rules, verdicts, [9, 1, 2, 8, 9, 9], sido="서울", sigungu=None, today=date(2026, 11, 1))
    # 확정·부모·다른 시도·마감 지난 것은 빠지고, 점수 순으로 종류마다 2개까지
    assert picked == ["2", "1"]
