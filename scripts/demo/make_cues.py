"""scenes.json의 나레이션을 자막 조각(cue)으로 나눠 장면 시간 안에 글자 수만큼 배분한다.
자막과 나레이션은 같은 문장이다. 결과: cues.json(촬영 스크립트가 화면에 띄움), 출력 폴더의 자막.srt."""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
MAX = 34   # 한 조각 최대 글자 수(휴대전화 화면 두 줄)


def pieces(text: str) -> list[str]:
    out = []
    for sentence in re.split(r"(?<=[.?!])\s+", text.strip()):
        parts = [sentence]
        while any(len(p) > MAX for p in parts):   # 긴 문장은 가운데에 가까운 쉼표·띄어쓰기에서 나눈다
            p = next(p for p in parts if len(p) > MAX)
            mid = len(p) // 2
            commas = [m.end() for m in re.finditer(r", ", p) if 0.25 * len(p) <= m.end() <= 0.75 * len(p)]
            cuts = commas or [m.end() for m in re.finditer(r"\s", p)]   # 쉼표(말 쉬는 곳)를 먼저, 없으면 띄어쓰기
            cut = min(cuts, key=lambda c: abs(c - mid)) if cuts else mid
            i = parts.index(p)
            parts[i:i + 1] = [p[:cut].strip(), p[cut:].strip()]
        out += [p for p in parts if p]
    return out


def ts(t: float) -> str:
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


scenes = json.loads((HERE / "scenes.json").read_text())
cues = []
for s in scenes:
    ps = pieces(s["narration"])
    start, end = s["start"] + 0.15, s["end"] - 0.15
    total = sum(len(p) for p in ps)
    t = start
    for p in ps:
        dur = (end - start) * len(p) / total
        cues.append({"start": round(t, 2), "end": round(t + dur - 0.05, 2), "text": p})
        t += dur
(HERE / "cues.json").write_text(json.dumps(cues, ensure_ascii=False, indent=1))
if len(sys.argv) > 1:
    srt = [f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n" for i, c in enumerate(cues, 1)]
    Path(sys.argv[1]).write_text("\n".join(srt))
print(f"자막 {len(cues)}개")
