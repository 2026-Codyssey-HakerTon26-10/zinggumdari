"""제출 전 읽기 전용 점검. --write는 준비가 끝난 지정 커밋의 소스코드 안내만 만든다."""

import argparse
import json
from pathlib import Path
import re
import subprocess


def audit(root, *, team_name=None, authors_confirmed=False):
    root = Path(root)
    issues = []
    resources = root / "docs/external-resources.md"
    pending = [{"line": i, "text": line} for i, line in enumerate(resources.read_text().splitlines(), 1)
               if line.startswith("|") and "채울 것" in line]
    if pending:
        issues.append("외부 자원 표의 미확정 항목을 확인해야 합니다")
    compiled = list((root / "rules/compiled").glob("*.json"))
    if not compiled:
        issues.append("AI 조건표가 없습니다")
    reviewed = sum(json.loads(p.read_text()).get("review", {}).get("status") == "reviewed" for p in compiled)
    if reviewed < 2:
        issues.append("시연용 검수 완료 AI 조건표 2건이 필요합니다")
    results_path = root / "eval/results.json"
    results = json.loads(results_path.read_text()) if results_path.exists() else None
    if not results or results.get("status") != "scored":
        issues.append("실제 채점 결과가 없습니다")
    else:
        if results.get("evaluation_scope") != "dev_only" or results.get("precision_auto_verified", {}).get("test") is not None:
            issues.append("시험용 채점 제외 계약과 결과가 다릅니다")
        precision = results.get("precision_auto_verified") or {}
        if not precision.get("dev") or not precision.get("sample") or precision["sample"].get("n") != 50:
            issues.append("개발용 또는 표본 50개 채점이 미완료입니다")
        if results.get("agreement_source", {}).get("skipped_parent_rules"):
            issues.append("부모 제도의 가상 인구 판정 일치 평가가 미완료입니다")
        if not results.get("agreement", {}).get("households"):
            issues.append("가구별 판정 일치 평가가 미완료입니다")
    if not list((root / "eval/personas").glob("*.json")):
        issues.append("가상 페르소나 정답이 없습니다")
    if not team_name or not re.fullmatch(r"[\w가-힣 -]+", team_name):
        issues.append("제출 팀명을 확정해야 합니다(파일명에 경로 문자는 허용하지 않습니다)")
    if not authors_confirmed:
        issues.append("5명 git 실명 대응을 확인해야 합니다")
    return {"ready": not issues, "issues": issues, "resource_placeholders": pending,
            "compiled_rules": len(compiled), "reviewed_compiled_rules": reviewed, "evaluation_status": results.get("status") if results else "not_evaluated"}


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--team-name")
    parser.add_argument("--authors-confirmed", action="store_true", help="5명 실명 대응을 실제 확인한 경우에만 사용")
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--write", type=Path, help="점검 통과 시 제출 안내 파일을 만들 디렉터리")
    args = parser.parse_args()
    root = args.root.resolve()
    commit = git(root, "rev-parse", "--verify", args.commit + "^{commit}")
    # 점검한 파일과 제출 대상 파일이 동일해야 한다.
    if commit != git(root, "rev-parse", "HEAD"):
        parser.error("현재 점검하는 HEAD와 제출 커밋이 다릅니다. 지정 커밋을 별도 작업 트리에서 점검하세요")
    report = audit(root, team_name=args.team_name, authors_confirmed=args.authors_confirmed)
    report.update(commit=commit, author_names=sorted(set(git(root, "log", "--format=%an").splitlines())))
    if git(root, "status", "--porcelain"):
        report["issues"].append("작업 트리가 깨끗하지 않습니다")
        report["ready"] = False
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.write:
        if not report["ready"]:
            parser.exit(1, "미완료 항목이 있어 제출 안내 파일을 생성하지 않았습니다\n")
        remote = git(root, "remote", "get-url", "origin")
        if remote.startswith("git@github.com:"):
            remote = "https://github.com/" + remote.split(":", 1)[1]
        if not re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+(?:\.git)?", remote):
            parser.error("공개 GitHub 주소를 확인하세요(인증정보가 든 주소는 내보내지 않습니다)")
        args.write.mkdir(parents=True, exist_ok=True)
        output = args.write / f"{args.team_name}_소스코드.txt"
        if output.exists():
            parser.error("기존 제출 안내 파일은 덮어쓰지 않습니다")
        output.write_text(f"저장소: {remote.removesuffix('.git')}\n커밋: {commit}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
