"""규칙 엔진. 다른 모듈(검색 배지, 가상 인구 전수 판정)은 `judge()`만 쓴다."""

import copy
from datetime import date

from backend.engine.stub_data import EXAMPLE_CARD


def judge(profile: dict, rules: list[dict], today: date | None = None) -> list[dict]:
    """프로필 하나를 조건표 목록으로 판정해 카드 목록(docs/api.md §3 `cards[]`)을 낸다.

    profile: docs/api.md §2 모양. rules: docs/api.md §1 조건 JSON 목록. today: None이면 오늘.
    스텁: 지금은 입력과 무관하게 api.md 예시 카드 하나를 돌려준다.
    """
    return [copy.deepcopy(EXAMPLE_CARD)]
