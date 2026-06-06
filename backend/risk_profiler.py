from __future__ import annotations

from typing import Any

import pandas as pd

try:
    from .analysis import FairnessResult
except ImportError:  # pragma: no cover - direct script fallback
    from analysis import FairnessResult


def _risk_label(score: float) -> str:
    if score >= 70:
        return "HIGH"
    if score >= 40:
        return "MEDIUM"
    return "LOW"


def profile_dataset_risk(
    df: pd.DataFrame,
    result: FairnessResult,
    proxy_findings: list[dict[str, Any]],
) -> dict[str, Any]:
    factors: list[dict[str, Any]] = []
    score = 0.0

    missing_ratio = float(df.isna().mean().mean()) if len(df.columns) else 0.0
    if missing_ratio >= 0.15:
        score += 20
        factors.append(
            {
                "factor": "missingness",
                "risk": "HIGH" if missing_ratio >= 0.3 else "MEDIUM",
                "detail": f"Dataset has {missing_ratio:.1%} missing cells before analysis.",
            }
        )

    protected_columns = [
        str(column)
        for column in (result.stats.get("protected_attributes") or [])
        if str(column) in df.columns
    ]
    group_sizes: list[int] = []
    if protected_columns:
        counts = df.groupby(protected_columns, dropna=False).size()
        group_sizes = [int(value) for value in counts.tolist()]
    if group_sizes:
        smallest = min(group_sizes)
        largest = max(group_sizes)
        if smallest < 5:
            score += 25
            factors.append(
                {
                    "factor": "small_subgroup",
                    "risk": "HIGH",
                    "detail": f"Smallest protected group has only {smallest} row(s).",
                }
            )
        if smallest and largest / smallest >= 4:
            score += 15
            factors.append(
                {
                    "factor": "group_imbalance",
                    "risk": "MEDIUM",
                    "detail": "Protected groups are heavily imbalanced.",
                }
            )

    if abs(float(result.difference or 0)) >= 0.25:
        score += 20
        factors.append(
            {
                "factor": "selection_gap",
                "risk": "HIGH",
                "detail": "Selection-rate gap is large enough to require mitigation review.",
            }
        )

    high_proxy_count = sum(1 for item in proxy_findings if item.get("risk") == "HIGH")
    if high_proxy_count:
        score += min(25, high_proxy_count * 12)
        factors.append(
            {
                "factor": "proxy_features",
                "risk": "HIGH",
                "detail": f"{high_proxy_count} high-risk proxy feature(s) were detected.",
            }
        )

    for warning in result.warnings or []:
        if "Low sample size" in warning or "small sample" in warning:
            score += 10

    final_score = round(max(0.0, min(100.0, score)), 1)
    confidence = "LOW" if final_score >= 70 else "MEDIUM" if final_score >= 40 else "HIGH"

    if not factors:
        factors.append(
            {
                "factor": "baseline",
                "risk": "LOW",
                "detail": "No major dataset reliability issues were detected.",
            }
        )

    return {
        "risk_score": final_score,
        "risk_level": _risk_label(final_score),
        "confidence": confidence,
        "factors": factors,
    }
