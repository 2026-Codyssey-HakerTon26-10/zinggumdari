"""단계 넘기기(SPEC §7.1). 예정 날짜는 받지 않는다. 다음 단계로 가면 프로필이 이렇게 바뀐다고 가정한다."""

import copy
from datetime import date

STEPS = ("newlywed", "child", "multi_child")


def reached(me: dict, step: str) -> bool:
    children = me.get("children_count") or 0
    if step == "newlywed":
        return me.get("marital_status") in ("신혼", "기혼")
    if step == "child":
        return children >= 1
    return children >= 2


def assume(me: dict, step: str, today: date) -> dict:
    """이 단계에서 바뀌는 칸만."""
    if step == "newlywed":
        return {"marital_status": "신혼", "marriage_date": today.isoformat()}
    if step == "child":
        return {"children_count": (me.get("children_count") or 0) + 1, "youngest_child_age": 0}
    return {"children_count": max((me.get("children_count") or 0) + 1, 2), "youngest_child_age": 0}


def apply_step(profile: dict, step: str, today: date) -> dict:
    """step까지 아직 안 지난 단계를 차례로 적용한 새 프로필. 원본은 바꾸지 않는다."""
    if step not in STEPS:
        raise ValueError(f"알 수 없는 단계: {step}")
    out = copy.deepcopy(profile)
    me = out.setdefault("self", {})
    for s in STEPS[: STEPS.index(step) + 1]:
        if not reached(me, s):
            me.update(assume(me, s, today))
    return out


def upcoming(me: dict) -> list[str]:
    return [s for s in STEPS if not reached(me, s)]
