"""공개 통계에는 원문·개인별 정답 대신 집계만 싣는다."""

from collections import Counter
from pathlib import Path
import json

from fastapi import APIRouter


def coverage(rules, results=None):
    states = Counter()
    manual = ai = unaccounted = 0
    for rule in rules:
        if rule.get("source") == "manual":
            manual += 1
        else:
            ai += 1
        states.update(c.get("status", "needs_review") for c in rule.get("conditions", []))
        unaccounted += rule.get("coverage", {}).get("unaccounted", 0)
    return dict(manual=manual, ai=ai, condition_states=dict(states),
                unaccounted_lines=unaccounted, evaluation=results)


def create_router(load_rules, *, results_path=Path("eval/results.json"), explore_path=Path("eval/explore-results.json")):
    router = APIRouter()

    def read(path):
        return json.loads(path.read_text()) if path.exists() else None

    @router.get("/stats/coverage")
    def stats_coverage():
        return coverage(load_rules(), read(results_path))

    @router.get("/stats/explore")
    def stats_explore():
        return read(explore_path) or {"status": "not_evaluated", "k": None, "precision_at_5": None, "recall_at_5": None}

    return router
