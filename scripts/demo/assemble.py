"""screencast 프레임(가변 간격)을 30fps MP4로. 프레임마다 다음 프레임까지 보여준다."""
import json
import subprocess
import sys
from pathlib import Path

rec, out = Path(sys.argv[1]), Path(sys.argv[2])
meta = json.loads((rec / "frames.json").read_text())
t0, end, ts = meta["t0"], meta["end"], meta["frames"]
times = [max(0.0, t - t0) for t in ts]
lines = []
for i, start in enumerate(times):
    nxt = times[i + 1] if i + 1 < len(times) else end
    dur = max(0.001, min(nxt, end) - (0 if i == 0 else start))
    lines.append(f"file 'frames/f{i:05d}.jpg'\nduration {dur:.4f}")
lines.append(f"file 'frames/f{len(times) - 1:05d}.jpg'")
(rec / "concat.txt").write_text("\n".join(lines) + "\n")
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(rec / "concat.txt"),
                "-vf", "fps=30,scale=786:1704:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-movflags", "+faststart", "-t", str(end), str(out)], check=True)
print(out)
