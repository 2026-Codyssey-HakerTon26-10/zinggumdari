"""PDF 읽기 테스트용 공고 PDF 두 개를 만든다(macOS 전용, 만든 PDF는 커밋한다).

- notice_text.pdf: 글자 층이 있는 2쪽 공고. 1쪽에 신청자격과 테두리 있는 표(가구원수 | 기준 중위소득 150%),
  2쪽 끝에 테두리 없는 2단 줄(문의 | 접수). HTML을 AppKit(NSTextView, TextKit 1)으로 그려 PDF로 내보내고
  PDFKit으로 쪽을 잇는다. cupsfilter는 HTML·RTF 필터가 없고 텍스트만으로는 표 선을 못 그려서 쓰지 않는다.
- notice_scan.pdf: 글자 층이 없는 1쪽 스캔. Pillow로 AppleSDGothicNeo 글자를 흰 이미지에 그려 PDF로 저장한다.
  notice_scan.txt는 그 정답 글(줄 단위)이고 실제 글자 인식 테스트가 비교에 쓴다.

실행: uv run --project backend python backend/tests/fixtures/make_fixtures.py
내용은 모두 테스트용 가상 공고다.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"

STYLE = """<style>
body { font-family: 'Apple SD Gothic Neo'; font-size: 11pt; }
h2 { font-size: 16pt; }
table.grid { border-collapse: collapse; }
table.grid td { border: 1px solid black; padding: 4px 8px; }
</style>"""

PAGE1 = """
<p>○○시 공고 제2026-123호(테스트용 가상 공고)</p>
<h2>2026년 ○○시 청년 월세 지원 사업 공고</h2>
<p>청년의 주거비 부담을 덜기 위해 아래와 같이 월세를 지원합니다.</p>
<p><b>1. 신청자격</b></p>
<p>○ 공고일 현재 ○○시에 주민등록을 둔 만 19세 이상 34세 이하 무주택 청년<br>
○ 가구 소득이 기준 중위소득 150% 이하인 자(아래 표 참조)<br>
○ 임차보증금 5천만 원 이하 및 월세 60만 원 이하 주택에 거주하는 자</p>
<table class="grid">
<tr><td>가구원수</td><td>기준 중위소득 150%(월)</td></tr>
<tr><td>1인</td><td>3,846,357원</td></tr>
<tr><td>2인</td><td>6,307,170원</td></tr>
<tr><td>3인</td><td>8,051,186원</td></tr>
</table>
<p>※ 다른 주거급여나 월세 지원을 받고 있는 자는 제외</p>
"""

PAGE2 = """
<p><b>2. 지원내용</b></p>
<p>○ 월 최대 20만 원, 최장 12개월 지원</p>
<p><b>3. 신청기간</b></p>
<p>○ 2026. 11. 3.(화) ~ 2026. 11. 27.(금) 18:00까지</p>
<p><b>4. 제출서류</b></p>
<p>○ 신청서, 임대차계약서 사본, 월세 이체 증빙</p>
<table><tr><td width="260">문의: 주거정책과 02-123-4567</td><td>접수: 거주지 행정복지센터</td></tr></table>
"""

# HTML 쪽마다 A4(595×842pt) PDF 한 쪽을 그리고 PDFKit으로 잇는다. argv: 출력 경로, HTML 경로...
JXA = r"""
ObjC.import('AppKit');
ObjC.import('PDFKit');
function run(argv) {
  const doc = $.PDFDocument.alloc.init;
  for (let i = 1; i < argv.length; i++) {
    const html = $.NSString.stringWithContentsOfFileEncodingError(argv[i], $.NSUTF8StringEncoding, null);
    const attr = $.NSAttributedString.alloc.initWithHTMLDocumentAttributes(html.dataUsingEncoding($.NSUTF8StringEncoding), null);
    const tv = $.NSTextView.alloc.initWithFrame($.NSMakeRect(0, 0, 595, 842));
    tv.layoutManager;  // TextKit 1로 바꿔야 표(NSTextTable)가 칸으로 그려진다
    tv.textContainerInset = $.NSMakeSize(60, 60);
    tv.textStorage.setAttributedString(attr);
    const page = $.PDFDocument.alloc.initWithData(tv.dataWithPDFInsideRect(tv.bounds));
    doc.insertPageAtIndex(page.pageAtIndex(0), doc.pageCount);
  }
  return doc.writeToFile(argv[0]) ? 'ok' : 'fail';
}
"""

SCAN_LINES = [
    "○○군 공고 제2026-77호",
    "2026년 ○○군 신혼부부 전세자금 이자 지원 공고(가상)",
    "1. 지원대상",
    "○ 혼인기간 7년 이내 또는 예비 신혼부부(공고일 기준)",
    "○ 부부합산 연소득 7천 5백만 원 이하",
    "○ 임차보증금 3억 원 이하 주택의 무주택 세대주",
    "○ 신청일 현재 ○○군 거주 6개월 이상",
    "2. 지원내용",
    "○ 대출잔액의 연 1.5% 이내, 연 최대 150만 원",
    "3. 신청기간: 2026. 12. 1.(화) ~ 2026. 12. 31.(목)",
    "※ 주택도시기금 버팀목 대출 이용자는 제외",
]
SCAN_TABLE = [["자녀 수", "추가 금리 지원"], ["1명", "0.2%p"], ["2명 이상", "0.5%p"]]


def make_text_pdf(out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        pages = []
        for i, body in enumerate([PAGE1, PAGE2], 1):
            p = Path(tmp) / f"p{i}.html"
            p.write_text(f'<html><head><meta charset="utf-8">{STYLE}</head><body>{body}</body></html>', encoding="utf-8")
            pages.append(str(p))
        script = Path(tmp) / "render.js"
        script.write_text(JXA, encoding="utf-8")
        r = subprocess.run(["osascript", "-l", "JavaScript", str(script), str(out), *pages],
                           capture_output=True, text=True, check=True)
        assert r.stdout.strip() == "ok", r.stdout + r.stderr


def make_scan_pdf(out: Path) -> None:
    dpi = 150
    img = Image.new("L", (int(8.27 * dpi), int(11.69 * dpi)), 255)  # A4
    d = ImageDraw.Draw(img)
    body = ImageFont.truetype(FONT, 30, index=0)
    title = ImageFont.truetype(FONT, 38, index=6)  # Bold
    x, y = 110, 120
    for i, text in enumerate(SCAN_LINES):
        f = title if i == 1 else body
        d.text((x, y), text, font=f, fill=0)
        y += 64 if i < 2 else 52
        if text.startswith("○ 대출잔액"):  # 지원내용 아래 표
            y += 10
            widths = [260, 320]
            for row in SCAN_TABLE:
                cx = x
                for w, cell in zip(widths, row):
                    d.rectangle([cx, y, cx + w, y + 56], outline=0, width=2)
                    d.text((cx + 16, y + 12), cell, font=body, fill=0)
                    cx += w
                y += 56
            y += 30
    img.save(out, "PDF", resolution=dpi)
    truth = SCAN_LINES[:9] + [" | ".join(r) for r in SCAN_TABLE] + SCAN_LINES[9:]
    out.with_suffix(".txt").write_text("\n".join(truth) + "\n", encoding="utf-8")


if __name__ == "__main__":
    make_text_pdf(HERE / "notice_text.pdf")
    make_scan_pdf(HERE / "notice_scan.pdf")
    for name in ("notice_text.pdf", "notice_scan.pdf"):
        print(name, (HERE / name).stat().st_size, "bytes")
