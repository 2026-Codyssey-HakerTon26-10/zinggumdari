"""AI 공고 읽기(SPEC §9, §10). 진입점 세 개는 docs/api.md 머리의 계약을 따른다.

    to_lines(doc_id, src) -> list[Line]               원문(파일 경로 또는 텍스트) → 줄 목록(api.md §8)
    compile(doc_id, lines, source) -> list[Rule]      자격 구간 → LLM 1회 → 검증기 → 빠짐 검사
    verify(rule, lines) -> Rule                       검증기만. 손 조건표에도 돌린다

Line, Rule은 api.md 모양 그대로의 dict다.
"""

from backend.compiler.lines import to_lines
from backend.compiler.pipeline import compile
from backend.compiler.verify import verify

__all__ = ["to_lines", "compile", "verify"]
