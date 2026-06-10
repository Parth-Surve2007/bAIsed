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


def _outcome_positive_rate(df: pd.DataFrame, outcome_column: str | None) -> float | None:
    if not outcome_column or outcome_column not in df.columns:
        return None

    series = df[outcome_column].dropna()
    if series.empty:
        return None

    normalized = series.astype(str).str.strip().str.lower()
    positive_values = {"1", "1.0", "true", "yes", "y", "approved", "selected", "pass", "positive"}
    negative_values = {"0", "0.0", "false", "no", "n", "rejected", "not selected", "fail", "negative"}
    if normalized.isin(positive_values | negative_values).all():
        return float(normalized.isin(positive_values).mean())

    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return float((numeric > 0).mean())


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

    high_hotspot_count = sum(
        1
        for hotspot in (result.bias_hotspots or [])
        if isinstance(hotspot, dict) and hotspot.get("severity") == "HIGH"
    )
    if high_hotspot_count:
        score += 30
        factors.append(
            {
                "factor": "subgroup_hotspots",
                "risk": "HIGH",
                "detail": f"{high_hotspot_count} high-severity subgroup hotspot(s) were detected.",
            }
        )

    outcome_rate = _outcome_positive_rate(df, str(result.stats.get("outcome_column") or ""))
    if outcome_rate is not None:
        minority_rate = min(outcome_rate, 1.0 - outcome_rate)
        if minority_rate <= 0.05:
            score += 20
            factors.append(
                {
                    "factor": "outcome_imbalance",
                    "risk": "HIGH",
                    "detail": "Outcome labels are extremely imbalanced, which can make disparity estimates unstable.",
                }
            )
        elif minority_rate <= 0.15:
            score += 10
            factors.append(
                {
                    "factor": "outcome_imbalance",
                    "risk": "MEDIUM",
                    "detail": "Outcome labels are imbalanced enough to reduce audit reliability.",
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

    sample_warning_count = sum(
        1
        for warning in (result.warnings or [])
        if "Low sample size" in warning or "small sample" in warning
    )
    if sample_warning_count:
        score += min(20, sample_warning_count * 10)
        factors.append(
            {
                "factor": "sample_warnings",
                "risk": "MEDIUM" if sample_warning_count == 1 else "HIGH",
                "detail": f"{sample_warning_count} sample-size warning(s) may reduce audit reliability.",
            }
        )

    if any(item.get("risk") == "HIGH" for item in factors):
        score = max(score, 70.0)
    elif any(item.get("risk") == "MEDIUM" for item in factors):
        score = max(score, 40.0)

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
