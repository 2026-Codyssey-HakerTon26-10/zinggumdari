"""평가에 사용한 코드/파일의 바이트 해시. 원문·프로필 내용은 출력하지 않는다."""

import hashlib
import json
from pathlib import Path


def digest_files(root, paths):
    root = Path(root)
    entries = {str(p): hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sorted(paths)}
    return hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()


def engine_digest(root):
    root = Path(root)
    paths = [p.relative_to(root) for folder in ("backend/engine", "backend/planner")
             for p in (root / folder).glob("*.py")]
    paths.append(Path("backend/search/corpus.py"))
    return digest_files(root, paths)


def scorer_digest(root):
    return digest_files(root, [Path("eval/score.py"), Path("eval/assemble.py")])
