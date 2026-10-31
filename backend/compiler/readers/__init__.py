"""원문 형식별 읽기. 각 reader는 줄 후보(텍스트, 쪽, 좌표, 표, 글자 층)를 내고 lines.py가 줄 ID를 붙인다.

reader 출력 모양(공통):
    {"kind": "pdf"|"hwp"|"hwpx"|"text", "pages": int|None, "text_layer": bool, "ocr": None|"tesseract"|"llm",
     "lines": [{"page": int|None, "bbox": [x0, top, x1, bottom]|None, "text": str, "src": "text"|"ocr", "table": str|None}]}
"""


class UnsupportedDocument(ValueError):
    """읽을 수 없는 원문(암호·배포용 HWP, HWP 3.x, 글자 인식 수단이 없는 스캔 PDF 등). 메시지는 화면에 그대로 띄울 한국어."""
