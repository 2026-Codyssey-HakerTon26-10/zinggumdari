"""LH 상세정보(15057999) 응답에서 첨부 파일 찾기.

2026-10-31 첫 덤프(상세 200건)로 확인: 첨부는 `dsAhflInfo`의 `AHFL_URL`(주소), `CMN_AHFL_NM`(파일 이름),
`SL_PAN_AHFL_DS_CD_NM`(구분: 공고문(PDF), 공고문(hwp), 정정공고문(PDF), 카탈로그, 기타 첨부파일).
기타 첨부파일에는 위임장·동의서 같은 서식 PDF가 섞여 있어 공고문은 구분 값으로 고른다.
이름이 바뀌어도 찾게 모든 ds* 블록에서 URL 값을 가진 줄을 찾고 블록·키를 같이 돌려준다.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote, urlparse

from backend.data.sources import as_list


def _blocks(parsed: Any) -> list[tuple[str, dict]]:
    out = []
    for block in as_list(parsed):
        if not isinstance(block, dict):
            continue
        for name, rows in block.items():
            for row in as_list(rows):
                if isinstance(row, dict):
                    out.append((name, row))
    return out


def file_kind(*texts: str | None) -> str:
    """pdf | hwp | other. 파일 이름, URL, 구분 이름 중 아무 데서나 확장자를 찾는다."""
    for text in texts:
        low = unquote(text or "").lower()
        path = urlparse(low).path if low.startswith("http") else low
        if path.endswith(".pdf") or "(pdf)" in low:
            return "pdf"
        if path.endswith((".hwp", ".hwpx")) or "(hwp)" in low:
            return "hwp"
    return "other"


def find_attachments(parsed: Any) -> list[dict]:
    found = []
    for block, row in _blocks(parsed):
        for key, value in row.items():
            if not (isinstance(value, str) and value.startswith("http") and "URL" in key.upper()):
                continue
            names = [v for k, v in row.items() if isinstance(v, str) and k.upper().endswith("NM")]
            file_name = next((n for n in names if file_kind(n) != "other"), names[0] if names else None)
            label = next((v for k, v in row.items() if isinstance(v, str) and k.upper().endswith("DS_CD_NM")), None)
            found.append({
                "block": block, "url_key": key, "url": value, "name": file_name, "label": label,
                "kind": file_kind(file_name, value, *names), "row_keys": sorted(row.keys()),
            })
    return found
