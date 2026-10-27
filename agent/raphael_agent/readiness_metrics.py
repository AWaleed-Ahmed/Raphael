"""Incident-level development ranking metrics, without a rollout decision."""

from __future__ import annotations

import math
import random
from typing import Any


def wilson(successes: int, total: int) -> list[float] | None:
    """Return the two-sided 95% Wilson interval; an empty sample has no rate."""
    if not 0 <= successes <= total:
        raise ValueError("invalid_rate_counts")
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = (
        z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    )
    return [max(0.0, center - half), min(1.0, center + half)]


def file_rank(paths: list[str], relevant: list[str]) -> int | None:
    """Rank distinct source files; multiple anchors in one file count once."""
    unique = list(dict.fromkeys(paths))
    return next(
        (index + 1 for index, path in enumerate(unique) if path in relevant), None
    )


def ranking_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare identical candidate sets, counting generation misses as misses.

    Bootstrap incident clusters rather than candidates or repeated predictions.
    With three incidents these intervals describe development evidence only.
    """
    groups: dict[str, list[float]] = {}
    result: dict[str, Any] = {"incidents": len(cases), "arms": {}}
    for arm in ("baseline", "model"):
        ranks = [file_rank(c[arm], c["relevant_files"]) for c in cases]
        n = len(ranks)
        generated = sum(rank is not None for rank in ranks)
        hits1 = sum(rank == 1 for rank in ranks)
        hits3 = sum(rank is not None and rank <= 3 for rank in ranks)
        result["arms"][arm] = {
            "top_1_hits": hits1,
            "top_3_hits": hits3,
            "all_input_denominator": n,
            "top_1": hits1 / n if n else None,
            "top_3": hits3 / n if n else None,
            "top_1_wilson_95": wilson(hits1, n),
            "top_3_wilson_95": wilson(hits3, n),
            "mrr": sum(1 / rank for rank in ranks if rank) / n if n else None,
            "candidate_generation_hits": generated,
            "conditional_top_1": hits1 / generated if generated else None,
        }
    wins = ties = regressions = 0
    for case in cases:
        if sorted(case["baseline"]) != sorted(case["model"]):
            raise ValueError("ranking_candidate_paths_differ")
        before = file_rank(case["baseline"], case["relevant_files"]) == 1
        after = file_rank(case["model"], case["relevant_files"]) == 1
        delta = float(after) - float(before)
        wins += delta > 0
        regressions += delta < 0
        ties += delta == 0
        groups.setdefault(case["incident_group"], []).append(delta)
    cluster_values = list(groups.values())
    randomizer = random.Random(7801)
    bootstrap = []
    if cluster_values:
        for _ in range(10000):
            sample = [randomizer.choice(cluster_values) for _ in cluster_values]
            bootstrap.append(sum(sum(c) for c in sample) / sum(len(c) for c in sample))
        bootstrap.sort()
    result["paired_top_1"] = {
        "wins": wins,
        "ties": ties,
        "regressions": regressions,
        "delta": (wins - regressions) / len(cases) if cases else None,
        "incident_clusters": len(groups),
        "bootstrap_95": [bootstrap[249], bootstrap[9749]] if bootstrap else None,
        "bootstrap_resamples": 10000,
        "seed": 7801,
    }
    return result
