"""전수 판정표 캐시. 규칙 엔진을 대체하거나 사용자 입력을 LLM에 보내지 않는다."""

import numpy as np


def build_table(profiles, rules, judge, path):
    ids = [r["id"] for r in rules]
    users = [p["user_id"] for p in profiles]
    if len(set(ids)) != len(ids) or len(set(users)) != len(users):
        raise ValueError("중복 사용자·제도 ID")
    table = np.zeros((len(users), len(ids)), dtype=bool)
    for i, profile in enumerate(profiles):
        results = judge(profile, rules)
        if set(results) != set(ids):
            raise ValueError("엔진 결과에 누락되거나 알 수 없는 제도가 있습니다")
        for j, rule in enumerate(rules):
            # 사람 검수 전 AI 조건표는 eligible로 집계하지 않는다.
            table[i, j] = (results[rule["id"]]["verdict"] == "eligible"
                           and rule.get("review", {}).get("status") == "reviewed")
    np.savez_compressed(path, eligibility=table, user_ids=np.array(users, dtype=str),
                        rule_ids=np.array(ids, dtype=str))
    return table
