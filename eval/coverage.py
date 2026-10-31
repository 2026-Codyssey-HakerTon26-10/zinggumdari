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
    return dict(manual=manual, compiled=dict(rules=ai, conditions=sum(states.values()),
                auto_verified=states["auto_verified"], needs_review=states["needs_review"], unaccounted_lines=unaccounted),
                eval={k: results.get(k) for k in ("status", "evaluation_scope", "limitation", "source_snapshot", "scoring_method", "agreement_source", "split", "precision_auto_verified", "missed", "agreement", "verifier")} if results else None)


def create_router(load_rules, *, results_path=Path("eval/results.json"), explore_path=Path("eval/explore-results.json")):
    router = APIRouter()

    def read(path):
        return json.loads(path.read_text()) if path.exists() else None

    @router.get("/stats/coverage")
    def stats_coverage():
        return coverage(load_rules(), read(results_path))

    @router.get("/stats/explore")
    def stats_explore():
        result = read(explore_path)
        if result and result.get("purpose") == "test":
            return result
        return {"status": "not_evaluated", "k": None, "precision_at_5": None, "recall_at_5": None,
                "baseline_popular": None, "baseline_random": None, "baseline_question_only": None, "variant_rule_bins": None}

    return router
