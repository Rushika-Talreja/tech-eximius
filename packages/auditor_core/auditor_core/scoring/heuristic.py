"""
Heuristic risk scoring engine.
Produces bounded, saturating penalty scores from verified scored findings and privilege tiers.
Label: "heuristic risk indicator".
Unscored items (scored=False) and dismissed findings never count.
"""
from __future__ import annotations

import math
from typing import Any

SCORE_LABEL: str = "heuristic risk indicator"

SCORING_WEIGHTS: dict[str, Any] = {
    "version": "1.0",
    "formula": "bounded_saturating_penalty",
    "saturation_scale": 50.0,
    "findings": {
        "critical": 25,
        "high": 15,
        "medium": 8,
        "low": 3,
        "info": 0,
    },
    "privilege_tiers": {
        "critical": 20,
        "high": 12,
        "medium": 5,
        "low": 0,
        "none": 0,
    },
}


def compute_heuristic_scores(
    findings: list[Any],
    privilege_results: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Computes heuristic security and overall risk score.
    Findings can be Finding DB models or dicts.
    Only findings with scored=True and status != 'dismissed' contribute.
    """
    findings_weights = SCORING_WEIGHTS["findings"]
    priv_weights = SCORING_WEIGHTS["privilege_tiers"]
    scale = float(SCORING_WEIGHTS["saturation_scale"])

    counts: dict[str, int] = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
    }

    findings_penalty = 0.0

    for f in findings:
        # Extract attributes whether model or dict
        status = getattr(f, "status", None) if not isinstance(f, dict) else f.get("status")
        scored = getattr(f, "scored", True) if not isinstance(f, dict) else f.get("scored", True)
        severity = getattr(f, "severity", "info") if not isinstance(f, dict) else f.get("severity", "info")

        if status == "dismissed" or not scored:
            continue

        sev_key = str(severity).lower()
        if sev_key in counts:
            counts[sev_key] += 1

        findings_penalty += findings_weights.get(sev_key, 0)

    # Privilege tier penalty
    privilege_penalty = 0.0
    if privilege_results:
        for pr in privilege_results:
            tier = getattr(pr, "tier", "none") if not isinstance(pr, dict) else pr.get("tier", "none")
            penalty = priv_weights.get(str(tier).lower(), 0)
            if penalty > privilege_penalty:
                privilege_penalty = penalty

    # Bounded saturating penalty curve
    # 0 penalty -> score 100
    # As penalty grows, score smoothly approaches 0
    security_deduction = 100.0 * (1.0 - math.exp(-findings_penalty / scale))
    security_score = max(0, min(100, round(100.0 - security_deduction)))

    total_penalty = findings_penalty + privilege_penalty
    overall_deduction = 100.0 * (1.0 - math.exp(-total_penalty / scale))
    overall_score = max(0, min(100, round(100.0 - overall_deduction)))

    return {
        "overall": overall_score,
        "security": security_score,
        "label": SCORE_LABEL,
        "weights": SCORING_WEIGHTS,
        "counts": counts,
    }

