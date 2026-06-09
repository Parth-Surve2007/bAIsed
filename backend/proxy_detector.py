from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _round(value: float) -> float:
    return round(float(value), 4)


def _risk_label(score: float) -> str:
    if score >= 0.65:
        return "HIGH"
    if score >= 0.35:
        return "MEDIUM"
    return "LOW"


def _cramers_v(x: pd.Series, y: pd.Series) -> float:
    table = pd.crosstab(x.astype(str), y.astype(str))
    if table.empty or min(table.shape) < 2:
        return 0.0

    observed = table.to_numpy(dtype=float)
    total = observed.sum()
    if total <= 0:
        return 0.0

    row_totals = observed.sum(axis=1, keepdims=True)
    col_totals = observed.sum(axis=0, keepdims=True)
    expected = row_totals @ col_totals / total
    valid = expected > 0
    chi2 = (((observed - expected) ** 2) / np.where(valid, expected, 1.0))[valid].sum()
    phi2 = chi2 / total
    denominator = max(1, min(table.shape[0] - 1, table.shape[1] - 1))
    return float(np.sqrt(max(0.0, phi2 / denominator)))


def _eta_squared(values: pd.Series, groups: pd.Series) -> float:
    numeric = pd.to_numeric(values, errors="coerce")
    frame = pd.DataFrame({"value": numeric, "group": groups.astype(str)}).dropna()
    if frame.empty or frame["group"].nunique() < 2:
        return 0.0

    grand_mean = frame["value"].mean()
    total_ss = ((frame["value"] - grand_mean) ** 2).sum()
    if total_ss <= 0:
        return 0.0

    between_ss = 0.0
    for _, group_values in frame.groupby("group")["value"]:
        between_ss += len(group_values) * ((group_values.mean() - grand_mean) ** 2)
    return float(max(0.0, min(1.0, between_ss / total_ss)))


def detect_proxy_features(
    df: pd.DataFrame,
    protected_columns: list[str],
    *,
    excluded_columns: list[str] | None = None,
    max_results: int = 8,
) -> list[dict[str, Any]]:
    excluded = {str(column) for column in [*(excluded_columns or []), *protected_columns]}
    findings: list[dict[str, Any]] = []

    for protected_column in protected_columns:
        if protected_column not in df.columns:
            continue

        protected_series = df[protected_column]
        if protected_series.dropna().nunique() < 2:
            continue

        for column in df.columns:
            column_name = str(column)
            if column_name in excluded:
                continue

            series = df[column]
            if series.dropna().nunique() < 2:
                continue

            if pd.api.types.is_numeric_dtype(series):
                score = _eta_squared(series, protected_series)
                method = "eta_squared"
            else:
                score = _cramers_v(series, protected_series)
                method = "cramers_v"

            if score < 0.2:
                continue

            findings.append(
                {
                    "feature": column_name,
                    "proxy_for": str(protected_column),
                    "association_score": _round(score),
                    "risk": _risk_label(score),
                    "method": method,
                    "reason": f"{column_name} is statistically associated with {protected_column}.",
                }
            )

    findings.sort(key=lambda item: item["association_score"], reverse=True)
    return findings[:max_results]
