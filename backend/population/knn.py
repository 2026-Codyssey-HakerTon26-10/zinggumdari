"""결측 칸을 제외하는 결정적 NumPy KNN. 판정은 주입받은 규칙 엔진만 한다."""

from collections import Counter
from datetime import date

import numpy as np

BASIS = "가상 인구(가정 분포)"


def neighbors(matrix, query, k=50, *, exclude=None):
    x, q = np.asarray(matrix, dtype=float), np.asarray(query, dtype=float)
    if x.ndim != 2 or q.shape != (x.shape[1],) or k < 1:
        raise ValueError("행렬·질의 차원과 양수 k를 확인하세요")
    known = np.isfinite(x) & np.isfinite(q)
    count = known.sum(axis=1)
    distances = np.sqrt(np.divide(
        np.where(known, (x - q) ** 2, 0).sum(axis=1), count,
        out=np.full(len(x), np.inf), where=count > 0,
    ))
    if exclude is not None:
        distances[exclude] = np.inf
    valid = np.flatnonzero(np.isfinite(distances))
    if not len(valid):
        return valid
    boundary = np.partition(distances[valid], min(k, len(valid)) - 1)[min(k, len(valid)) - 1]
    chosen = valid[distances[valid] <= boundary]
    return chosen[np.argsort(distances[chosen], kind="stable")]


def recommend(matrix, query, eligibility, rules, verdicts, *, tags, known_fields,
              sido=None, sigungu=None, today=None, k=50):
    """eligibility 행/열은 이웃 후보 행렬/제도 목록과 같은 순서여야 한다.

    verdicts는 rule_id → {verdict, blocking_fields, deadline}인 엔진 결과다.
    지역 미상·개인 판정 누락은 추천하지 않는다. 부모는 별도 인구가 없어 제외한다.
    """
    today = today or date.today()
    y = np.asarray(eligibility)
    if y.shape != (len(matrix), len(rules)) or y.dtype != np.bool_ or len(tags) != len(matrix):
        raise ValueError("인구·제도·판정표·태그 정렬을 확인하세요")
    idx = neighbors(matrix, query, k)
    label, share = "참고", 0.0
    if len(idx):
        group, n = Counter(tuple(sorted(tags[i])) for i in idx).most_common(1)[0]
        label, share = "주로 " + "·".join(group) + " 가구", n / len(idx)
    result = dict(method="knn", features="sheet_minmax", k=k, neighbors=len(idx),
                  basis=BASIS, label=label, label_share=share, known_fields=known_fields,
                  assignment="reference" if known_fields < 3 or share < .5 else "full", items=[])
    if not len(idx):
        return result
    candidates = []
    for j, rule in enumerate(rules):
        mine = verdicts.get(rule["id"], {})
        region = rule.get("region")
        if rule.get("subject") != "self" or mine.get("verdict") != "needs_check":
            continue
        if region and (region.get("unknown") or (region.get("sido") and region["sido"] != sido)
                       or (region.get("sigungu") and region["sigungu"] != sigungu)):
            continue
        deadline = mine.get("deadline")
        end = date.fromisoformat(deadline) if deadline else date.max
        prevalence = float(y[idx, j].mean())
        if end < today or prevalence < .3:
            continue
        fields = sorted(set(mine.get("blocking_fields", [])))
        item = {key: rule[key] for key in ("name", "subject", "benefit_type")}
        item.update(rule_id=rule["id"], prevalence=prevalence,
                    my_verdict="needs_check", blocking_fields=fields)
        candidates.append((-prevalence, len(fields), end, rule["id"], item))
    kinds = Counter()
    for *_, item in sorted(candidates):
        if kinds[item["benefit_type"]] < 2:
            result["items"].append(item)
            kinds[item["benefit_type"]] += 1
        if len(result["items"]) == 5:
            break
    return result
