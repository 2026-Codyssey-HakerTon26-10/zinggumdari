"""원문 → 줄 목록(api.md §8). 스텁: api.md 예시를 그대로 돌려준다."""

from __future__ import annotations


def to_lines(doc_id: str, src: str) -> list[dict]:
    return [
        {"id": "p7-l23", "page": 7, "bbox": [72.0, 418.5, 310.2, 431.0], "text": "청약통장 가입 후 6개월이 지난 분", "mark": True},
        {"id": "p8-l4", "page": 8, "bbox": [72.0, 300.0, 400.0, 312.0], "text": "부부합산 소득이 도시근로자 월평균소득의 120% 이하", "mark": True},
        {"id": "p8-l9", "page": 8, "bbox": [72.0, 380.0, 380.0, 392.0], "text": "총자산 3억 4,500만 원 이하", "mark": True},
    ]
