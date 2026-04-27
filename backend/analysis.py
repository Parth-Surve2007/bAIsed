from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any
import warnings

import numpy as np
import pandas as pd
from pandas.api.types import CategoricalDtype


TRUE_VALUES = {"1", "true", "yes", "y", "approved", "selected", "pass", "positive"}
FALSE_VALUES = {"0", "false", "no", "n", "rejected", "not selected", "fail", "negative"}
MIN_GROUP_SAMPLE_SIZE = 5
LOW_TOTAL_SAMPLE_SIZE = 30
FAIRNESS_THRESHOLD = 0.8


class AnalysisError(ValueError):
    """Raised when fairness analysis input is invalid."""


@dataclass(frozen=True)
class FairnessResult:
    bias_detected: bool
    severity: str
    groups: dict[str, float]
    difference: float
    DIR: float
    metrics: dict[str, float]
    most_advantaged_group: str
    least_advantaged_group: str
    most_influential_feature: str
    explanation: str
    bias_score: float
    recommendations: list[str]
    warnings: list[str]
    bias_hotspots: list[dict[str, Any]]
    hidden_bias_detected: bool
    simulations: list[dict[str, Any]]
    repair_suggestions: list[dict[str, Any]]
    feature_impact_ranking: list[dict[str, Any]]
    stats: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "bias_detected": self.bias_detected,
            "severity": self.severity,
            "groups": self.groups,
            "difference": self.difference,
            "DIR": self.DIR,
            "metrics": self.metrics,
            "most_advantaged_group": self.most_advantaged_group,
            "least_advantaged_group": self.least_advantaged_group,
            "most_influential_feature": self.most_influential_feature,
            "explanation": self.explanation,
            "bias_score": self.bias_score,
            "recommendations": self.recommendations,
            "warnings": self.warnings,
            "bias_hotspots": self.bias_hotspots,
            "hidden_bias_detected": self.hidden_bias_detected,
            "simulations": self.simulations,
            "repair_suggestions": self.repair_suggestions,
            "stats": self.stats,
            "feature_impact_ranking": self.feature_impact_ranking,
        }


def _round(value: float) -> float:
    return round(float(value), 4)


def _build_explanation(
    severity: str,
    metrics: dict[str, float],
    high_group: str,
    low_group: str,
    subgroup_summary: str | None = None,
    influential_feature: str | None = None,
    hidden_bias_detected: bool = False,
    hotspot_summary: str | None = None,
    repair_summary: str | None = None,
) -> str:
    dir_text = f"{_round(metrics['DIR']):.4f}".rstrip("0").rstrip(".")
    diff_text = f"{_round(metrics['SPD']):.4f}".rstrip("0").rstrip(".")
    eod_text = f"{_round(metrics['EOD']):.4f}".rstrip("0").rstrip(".")
    aod_text = f"{_round(metrics['AOD']):.4f}".rstrip("0").rstrip(".")
    sentences = [
        (
            f"{severity.title()} bias detected because {low_group} has a lower selection rate than {high_group}. "
            f"The disparate impact ratio is {dir_text}, the statistical parity difference is {diff_text}, "
            f"the equal opportunity difference is {eod_text}, and the average odds difference is {aod_text}."
        )
    ]

    if subgroup_summary:
        sentences.append(subgroup_summary)

    if influential_feature:
        sentences.append(f"The largest overall disparity is associated with the {influential_feature} feature.")

    if hidden_bias_detected:
        sentences.append("Hidden bias is present because at least one subgroup shows high-severity disparity despite the global score appearing less severe.")

    if hotspot_summary:
        sentences.append(hotspot_summary)

    if repair_summary:
        sentences.append(repair_summary)

    return " ".join(sentences)


def _classify(dir_value: float) -> tuple[bool, str]:
    if dir_value < 0.5:
        severity = "HIGH"
    elif dir_value < FAIRNESS_THRESHOLD:
        severity = "MODERATE"
    else:
        severity = "LOW"

    return dir_value < FAIRNESS_THRESHOLD, severity


def _bias_score_from_metrics(metrics: dict[str, float]) -> float:
    dir_gap = max(0.0, 1.0 - float(metrics.get("DIR", 1.0)))
    spd = max(0.0, float(metrics.get("SPD", 0.0)))
    eod = max(0.0, abs(float(metrics.get("EOD", 0.0))))
    aod = max(0.0, abs(float(metrics.get("AOD", 0.0))))
    weighted = (0.45 * dir_gap) + (0.25 * spd) + (0.15 * eod) + (0.15 * aod)
    score = max(0.0, min(100.0, weighted * 100.0))
    return _round(score)


def _build_recommendations(severity: str, difference: float, high_group: str, low_group: str) -> list[str]:
    recommendations = [
        f"Review decision thresholds and feature distributions for {low_group} versus {high_group}.",
        f"Validate whether training data underrepresents {low_group} in positive outcomes.",
    ]

    if severity == "HIGH":
        recommendations.append("Pause high-stakes deployment until the disparity is reduced below the 0.8 DIR threshold.")
    elif severity == "MODERATE":
        recommendations.append("Run remediation experiments and re-measure the selection gap before production release.")
    else:
        recommendations.append("Continue monitoring parity over time to catch emerging disparity early.")

    if difference >= 0.25:
        recommendations.append("Audit proxy variables that may be amplifying group-level outcome gaps.")

    return recommendations


def _canonical_name(column: Any) -> str:
    return str(column).strip().lower()


def _format_group_key(value: Any) -> str:
    if pd.isna(value):
        return "N/A"
    if isinstance(value, tuple):
        return " | ".join(_format_group_key(item) for item in value)
    return str(value)


def _safe_qcut(series: pd.Series, bins: int = 3) -> pd.Series:
    quantiles = min(bins, max(2, int(series.nunique())))
    try:
        categorized = pd.qcut(series, q=quantiles, duplicates="drop")
    except ValueError:
        return series.astype(str)

    labels = []
    for index, interval in enumerate(categorized.cat.categories):
        if index == 0:
            label = "LOW"
        elif index == len(categorized.cat.categories) - 1:
            label = "HIGH"
        else:
            label = "MEDIUM"
        labels.append((interval, label))

    mapped = categorized.astype(object)
    for interval, label in labels:
        mapped = mapped.replace(interval, label)
    return mapped.astype(str)


def _profile_columns(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    row_count = max(1, int(len(df)))

    for column in df.columns:
        name = str(column)
        normalized = _canonical_name(name)
        series = df[name]
        non_null = series.dropna()
        non_null_count = int(len(non_null))
        unique_count = int(non_null.nunique()) if non_null_count else 0
        unique_ratio = (unique_count / non_null_count) if non_null_count else 0.0

        if non_null_count and not pd.api.types.is_numeric_dtype(non_null):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                parsed_dates = pd.to_datetime(non_null, errors="coerce")
        else:
            parsed_dates = pd.Series(dtype="datetime64[ns]")
        date_parse_ratio = float(parsed_dates.notna().mean()) if non_null_count else 0.0

        is_numeric = bool(non_null_count and pd.api.types.is_numeric_dtype(non_null))
        if is_numeric:
            numeric_series = pd.to_numeric(non_null, errors="coerce").dropna()
        else:
            numeric_series = pd.Series(dtype=float)

        binary_like = False
        if non_null_count:
            # Use strict check for profiling - only true binary data (0/1, yes/no, true/false)
            try:
                unique_str_vals = {str(v).strip().lower() for v in non_null.unique()}
                strict_binary = unique_str_vals.issubset(TRUE_VALUES | FALSE_VALUES | {"0", "1", "0.0", "1.0"})
                if strict_binary and len(unique_str_vals) <= 2:
                    binary_like = True
            except:
                binary_like = False

        identifier_like = (unique_count > 20 and unique_ratio >= 0.95)
        categorical_like = bool(
            non_null_count
            and (pd.api.types.is_object_dtype(non_null) or isinstance(non_null.dtype, CategoricalDtype))
            and unique_count >= 2
        )
        groupable_categorical = bool(
            categorical_like
            and unique_count <= max(24, int(row_count * 0.2))
            and unique_ratio < 0.85
        )
        groupable_date = bool(date_parse_ratio >= 0.8 and unique_count >= 2)
        groupable_numeric = bool(
            is_numeric
            and unique_count >= 4
            and (row_count <= 20 or unique_ratio < 0.95)
        )

        numeric_spread = 0.0
        if not numeric_series.empty:
            min_value = float(numeric_series.min())
            max_value = float(numeric_series.max())
            mean_abs = max(1.0, float(np.abs(numeric_series).mean()))
            numeric_spread = max(0.0, (max_value - min_value) / mean_abs)

        group_score = 0.0
        # Common protected attribute patterns
        primary_protected = ["sex", "race", "ethnic", "gender", "age"]
        secondary_protected = ["disability", "marital", "religion", "native", "nationality"]
        
        name_lower = name.lower()
        if any(k in name_lower for k in primary_protected):
            semantic_group_boost = 1.5
        elif any(k in name_lower for k in secondary_protected):
            semantic_group_boost = 1.0
        else:
            semantic_group_boost = 0.0

        if groupable_categorical:
            group_score = (2.5 - min(2.0, abs(unique_count - 6) / 6.0)) + (1.0 - min(1.0, unique_ratio)) + semantic_group_boost
        elif groupable_date:
            group_score = 1.8 + min(0.6, date_parse_ratio) + semantic_group_boost
        elif groupable_numeric:
            group_score = 1.2 + min(1.2, numeric_spread / 4.0) + semantic_group_boost

        outcome_score = 0.0
        # Common outcome patterns
        outcome_keywords = ["outcome", "target", "label", "result", "hired", "pass", "fail", "recid", "arrest", "status", "score", "decile"]
        semantic_outcome_boost = 1.5 if any(k in name.lower() for k in outcome_keywords) else 0.0

        if binary_like:
            # Penalize binary columns that have very low variance (mostly all 1s or all 0s)
            try:
                normalized_values = non_null.map(_normalize_outcome_value)
                balance = float(normalized_values.mean())
                # If the column is constant (all 1s or all 0s), it's useless for analysis
                if balance == 0.0 or balance == 1.0:
                    outcome_score = 0.0
                else:
                    # Penalty is 0 at balance=0.5, and increases as it approaches 0 or 1.
                    variance_penalty = abs(0.5 - balance) * 6.0 
                    outcome_score = max(0.1, 5.0 - variance_penalty) + semantic_outcome_boost
            except:
                outcome_score = 0.0
        elif is_numeric and unique_count >= 4 and not identifier_like:
            outcome_score = 1.0 + min(2.0, numeric_spread / 3.0) + semantic_outcome_boost
        elif categorical_like and not identifier_like and 2 < unique_count <= 10:
            # Ordinal/categorical outcome detection (e.g., Low/Medium/High, Pass/Fail/Pending)
            ordinal_indicators = {"low", "medium", "high", "very high", "very low", "none", "severe", "critical", "minimal"}
            unique_lower = {str(v).strip().lower() for v in non_null.unique()}
            is_ordinal = len(unique_lower & ordinal_indicators) >= 2
            if is_ordinal:
                outcome_score = 4.0 + semantic_outcome_boost  # Strong score for ordinal scales
            elif semantic_outcome_boost > 0:
                outcome_score = 2.0 + semantic_outcome_boost  # Moderate for keyword-matching categoricals


        stats = {
            "mean": None,
            "median": None,
            "min": None,
            "max": None,
            "std": None,
            "missing_count": int(series.isna().sum()),
            "missing_ratio": _round(series.isna().mean()),
            "top_values": {str(k): v for k, v in non_null.value_counts().head(5).to_dict().items()} if not non_null.empty else {}
        }

        if is_numeric and not numeric_series.empty:
            stats.update({
                "mean": _round(numeric_series.mean()),
                "median": _round(numeric_series.median()),
                "min": _round(numeric_series.min()),
                "max": _round(numeric_series.max()),
                "std": _round(numeric_series.std()) if len(numeric_series) > 1 else 0.0
            })

        profiles[name] = {
            "non_null_count": non_null_count,
            "unique_count": unique_count,
            "unique_ratio": _round(unique_ratio),
            "is_numeric": is_numeric,
            "binary_like": binary_like,
            "identifier_like": identifier_like,
            "categorical_like": categorical_like,
            "groupable_categorical": groupable_categorical,
            "groupable_date": groupable_date,
            "groupable_numeric": groupable_numeric,
            "date_parse_ratio": _round(date_parse_ratio),
            "numeric_spread": _round(numeric_spread),
            "group_score": _round(group_score),
            "outcome_score": _round(outcome_score),
            "analysis": stats
        }

    return profiles


def _normalize_group_rates(group_rates: dict[str, float]) -> tuple[dict[str, float], str, str, float, float]:
    if not group_rates:
        raise AnalysisError("At least one group is required for analysis.")

    if len(group_rates) < 2:
        raise AnalysisError("At least two groups are required for comparison.")

    normalized_rates = {str(group): float(rate) for group, rate in group_rates.items()}

    max_group = max(normalized_rates, key=normalized_rates.get)
    min_group = min(normalized_rates, key=normalized_rates.get)
    max_rate = normalized_rates[max_group]
    min_rate = normalized_rates[min_group]

    if max_rate < 0 or min_rate < 0:
        raise AnalysisError("Selection rates cannot be negative.")

    return normalized_rates, str(max_group), str(min_group), max_rate, min_rate


def _build_metrics(
    overall_rates: dict[str, float],
    qualified_rates: dict[str, float] | None = None,
) -> tuple[dict[str, float], str, str, float, float]:
    normalized_rates, max_group, min_group, max_rate, min_rate = _normalize_group_rates(overall_rates)
    dir_value = 1.0 if max_rate == 0 else min_rate / max_rate
    spd = max_rate - min_rate

    if qualified_rates and len(qualified_rates) >= 2:
        qualified_normalized, _, _, qualified_max, qualified_min = _normalize_group_rates(qualified_rates)
        eod = qualified_max - qualified_min
        qualified_dir = 1.0 if qualified_max == 0 else qualified_min / qualified_max
        aod = (spd + eod + abs(dir_value - qualified_dir)) / 3.0
    else:
        eod = spd
        aod = spd

    metrics = {
        "DIR": _round(dir_value),
        "SPD": _round(spd),
        "EOD": _round(eod),
        "AOD": _round(aod),
    }
    return metrics, max_group, min_group, max_rate, min_rate


def _candidate_feature_columns(df: pd.DataFrame, excluded: set[str]) -> list[str]:
    candidates: list[str] = []
    for column in df.columns:
        normalized = _canonical_name(column)
        if normalized in excluded:
            continue

        series = df[column].dropna()
        if series.empty:
            continue

        if pd.api.types.is_object_dtype(series) or isinstance(series.dtype, CategoricalDtype):
            if 2 <= series.nunique() <= 20:
                candidates.append(str(column))
        elif pd.api.types.is_numeric_dtype(series) and series.nunique() >= 4:
            candidates.append(str(column))

    return candidates


def _prepare_feature_series(series: pd.Series, column_name: str) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return _safe_qcut(series.astype(float))
    return series.astype(str).str.strip()


def _selection_rates_from_frame(df: pd.DataFrame, group_columns: list[str], outcome_column: str) -> tuple[dict[str, float], dict[str, int]]:
    grouped = df.groupby(group_columns, dropna=False)[outcome_column]
    rates = (grouped.sum() / grouped.count()).to_dict()
    counts = grouped.count().to_dict()
    formatted_rates = {_format_group_key(key): float(value) for key, value in rates.items()}
    formatted_counts = {_format_group_key(key): int(value) for key, value in counts.items()}
    return formatted_rates, formatted_counts


def _group_dict_from_key(group_columns: list[str], key: Any) -> dict[str, str]:
    if not isinstance(key, tuple):
        key = (key,)
    return {str(column): _format_group_key(value) for column, value in zip(group_columns, key)}


def _impact_score_from_rates(rates: list[float], dir_value: float, difference: float) -> float:
    if not rates:
        return 0.0
    variance = float(np.var(rates)) if len(rates) > 1 else 0.0
    impact = (0.55 * difference) + (0.3 * max(0.0, 1.0 - dir_value)) + (0.15 * min(1.0, variance * 4.0))
    return _round(impact)


def _detect_warnings(
    original_df: pd.DataFrame,
    working_df: pd.DataFrame,
    protected_column: str,
    outcome_column: str,
    group_counts: dict[str, int],
    qualified_group_counts: dict[str, int] | None = None,
    subgroup_counts: dict[str, int] | None = None,
) -> list[str]:
    warnings: list[str] = []

    if len(original_df) < LOW_TOTAL_SAMPLE_SIZE:
        warnings.append("Low sample size may affect reliability.")

    removed_rows = int(len(original_df) - len(working_df))
    if removed_rows > 0:
        warnings.append(f"{removed_rows} rows were excluded due to missing protected attribute or outcome values.")

    smallest_group = min(group_counts.values()) if group_counts else 0
    if 0 < smallest_group < MIN_GROUP_SAMPLE_SIZE:
        warnings.append("One or more groups have very small sample sizes; subgroup estimates may be unstable.")

    if group_counts:
        largest_group = max(group_counts.values())
        if smallest_group > 0 and largest_group / smallest_group >= 4:
            warnings.append("Protected groups are imbalanced, so parity metrics may be dominated by the largest group.")

    if qualified_group_counts:
        qualified_smallest = min(qualified_group_counts.values()) if qualified_group_counts else 0
        if 0 < qualified_smallest < MIN_GROUP_SAMPLE_SIZE:
            warnings.append("Qualified subgroup counts are small, so equal opportunity estimates may be noisy.")

    if subgroup_counts:
        for subgroup, count in subgroup_counts.items():
            if 0 < count < MIN_GROUP_SAMPLE_SIZE:
                warnings.append(f"Low sample size in subgroup: {subgroup}")

    if original_df[protected_column].isna().any():
        warnings.append("Protected attribute contains missing values.")

    if original_df[outcome_column].isna().any():
        warnings.append("Outcome column contains missing values that were excluded from analysis.")

    return warnings


def _detect_qualification_column(
    df: pd.DataFrame,
    excluded_columns: set[str],
    qualification_column: str | None = None,
) -> str | None:
    columns = {_canonical_name(column): str(column) for column in df.columns}
    if qualification_column:
        key = _canonical_name(qualification_column)
        if key not in columns:
            raise AnalysisError(f"Qualification column '{qualification_column}' was not found.")
        return columns[key]

    candidates: list[str] = []
    for column in df.columns:
        name = str(column)
        normalized_name = _canonical_name(name)
        if normalized_name in excluded_columns:
            continue

        series = df[name].dropna()
        if series.empty:
            continue

        is_binary = False
        try:
            series.map(_normalize_outcome_value)
            is_binary = True
        except AnalysisError:
            is_binary = False

        if is_binary or pd.api.types.is_numeric_dtype(series) or series.nunique() <= 12:
            candidates.append(name)

    return candidates[0] if candidates else None


def _prepare_qualification_series(series: pd.Series, column_name: str) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return _safe_qcut(series.astype(float))

    try:
        normalized = series.map(_normalize_outcome_value)
        return normalized.map({1: "QUALIFIED", 0: "NOT_QUALIFIED"}).astype(str)
    except AnalysisError:
        return series.astype(str).str.strip()


def _qualified_subset(frame: pd.DataFrame, qualification_label_column: str | None) -> pd.DataFrame:
    if not qualification_label_column:
        return frame

    labels = frame[qualification_label_column].astype(str).str.upper()
    preferred_labels = {"QUALIFIED", "HIGH", "PASS", "YES", "TRUE", "1"}
    filtered = frame[labels.isin(preferred_labels)]
    if filtered.empty:
        most_common = labels.mode()
        if most_common.empty:
            return frame
        filtered = frame[labels == str(most_common.iloc[0]).upper()]

    return filtered if not filtered.empty else frame


def _context_analysis(
    frame: pd.DataFrame,
    protected_columns: list[str],
    outcome_column: str,
    qualification_label_column: str | None,
) -> dict[str, Any]:
    if not qualification_label_column:
        return {}

    subgroup_results: list[dict[str, Any]] = []
    for label_value, subset in frame.groupby(qualification_label_column):
        if subset.empty:
            continue
        rates, counts = _selection_rates_from_frame(subset, protected_columns, outcome_column)
        if len(rates) < 2:
            continue

        metrics, advantaged, disadvantaged, _, _ = _build_metrics(rates)
        subgroup_results.append(
            {
                "qualification_group": _format_group_key(label_value),
                "metrics": metrics,
                "most_advantaged_group": advantaged,
                "least_advantaged_group": disadvantaged,
                "group_counts": counts,
            }
        )

    if not subgroup_results:
        return {}

    subgroup_results.sort(key=lambda item: (item["metrics"]["DIR"], -item["metrics"]["SPD"]))
    largest_disparity = subgroup_results[0]
    return {
        "subgroups": subgroup_results,
        "largest_disparity_subgroup": largest_disparity,
    }


def _feature_influence_analysis(
    frame: pd.DataFrame,
    outcome_column: str,
    excluded_columns: set[str],
) -> tuple[str, list[dict[str, Any]]]:
    rankings: list[dict[str, Any]] = []

    for column in _candidate_feature_columns(frame, excluded_columns):
        prepared = _prepare_feature_series(frame[column], column)
        candidate_frame = frame[[outcome_column]].copy()
        candidate_frame[column] = prepared
        candidate_frame = candidate_frame.dropna()
        candidate_frame[column] = candidate_frame[column].astype(str).str.strip()
        candidate_frame = candidate_frame[candidate_frame[column] != ""]
        if candidate_frame.empty:
            continue

        rates, counts = _selection_rates_from_frame(candidate_frame, [column], outcome_column)
        if len(rates) < 2:
            continue

        metrics, advantaged, disadvantaged, _, _ = _build_metrics(rates)
        impact = _impact_score_from_rates(list(rates.values()), metrics["DIR"], metrics["SPD"])
        rankings.append(
            {
                "feature": column,
                "impact": impact,
                "metrics": metrics,
                "most_advantaged_group": advantaged,
                "least_advantaged_group": disadvantaged,
                "group_counts": counts,
            }
        )

    if not rankings:
        return "unknown", []

    rankings.sort(key=lambda item: (-item["impact"], item["metrics"]["DIR"], -item["metrics"]["SPD"]))
    return rankings[0]["feature"], rankings


def _bias_hotspot_analysis(
    frame: pd.DataFrame,
    protected_columns: list[str],
    outcome_column: str,
    excluded_columns: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    hotspot_candidates: list[dict[str, Any]] = []
    subgroup_counts: dict[str, int] = {}
    secondary_columns = _candidate_feature_columns(frame, excluded_columns)

    for secondary in secondary_columns:
        group_columns = [*protected_columns, secondary]
        grouped = frame.groupby(group_columns, dropna=False)[outcome_column]
        rates = grouped.mean()
        counts = grouped.count()
        if len(rates) < 2:
            continue

        global_max = float(rates.max())
        for (key, rate), count in zip(rates.items(), counts):
            count = int(count)
            group_dict = _group_dict_from_key(group_columns, key)
            subgroup_label = " + ".join(group_dict.values())
            subgroup_counts[subgroup_label] = count
            dir_value = 1.0 if global_max == 0 else float(rate) / global_max
            difference = max(0.0, global_max - float(rate))
            _, severity = _classify(dir_value)
            hotspot_candidates.append(
                {
                    "group": group_dict,
                    "selection_rate": _round(float(rate)),
                    "DIR": _round(dir_value),
                    "difference": _round(difference),
                    "severity": severity,
                    "sample_size": count,
                    "secondary_attribute": secondary,
                }
            )

    if not hotspot_candidates:
        return [], subgroup_counts

    hotspot_candidates.sort(
        key=lambda item: (item["DIR"], -item["difference"], item["sample_size"])
    )
    return hotspot_candidates[:5], subgroup_counts


def _simulate_counterfactuals(
    metrics: dict[str, float],
    min_group: str,
    max_group: str,
    min_rate: float,
    max_rate: float,
    most_influential_feature: str,
    feature_impact_ranking: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if max_rate <= 0:
        return []

    simulations: list[dict[str, Any]] = []
    target_rate = min(max_rate, FAIRNESS_THRESHOLD * max_rate)
    uplift = max(0.0, target_rate - min_rate)
    uplifted_rate = min(max_rate, min_rate + uplift)
    uplifted_dir = 1.0 if max_rate == 0 else uplifted_rate / max_rate
    simulations.append(
        {
            "scenario": f"increase_{min_group}_selection_rate_to_threshold".replace(" ", "_"),
            "new_DIR": _round(uplifted_dir),
            "bias_reduced": uplifted_dir >= metrics["DIR"],
            "details": f"Raises {min_group} from {_round(min_rate)} to {_round(uplifted_rate)} to meet the {FAIRNESS_THRESHOLD:.1f} DIR threshold.",
        }
    )

    impact = feature_impact_ranking[0]["impact"] if feature_impact_ranking else 0.0
    feature_uplift = min(max_rate, min_rate + max(0.0, (max_rate - min_rate) * min(0.75, impact + 0.15)))
    feature_dir = 1.0 if max_rate == 0 else feature_uplift / max_rate
    simulations.append(
        {
            "scenario": f"remove_{most_influential_feature}_influence".replace(" ", "_"),
            "new_DIR": _round(feature_dir),
            "bias_reduced": feature_dir > metrics["DIR"],
            "details": f"Neutralizes the top disparity driver ({most_influential_feature}) and recomputes the disadvantaged group's expected rate.",
        }
    )

    simulations.append(
        {
            "scenario": "equalize_group_probabilities",
            "new_DIR": 1.0,
            "bias_reduced": True,
            "details": f"Sets {min_group} and {max_group} to a common selection probability for a full parity baseline.",
        }
    )
    return simulations


def _build_repair_suggestions(
    min_group: str,
    max_group: str,
    min_rate: float,
    max_rate: float,
    hotspots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    target_rate = FAIRNESS_THRESHOLD * max_rate
    required_change = max(0.0, target_rate - min_rate)
    suggestions.append(
        {
            "action": f"increase_{min_group}_selection_rate".replace(" ", "_"),
            "required_change": f"+{_round(required_change * 100.0)}%",
            "target_DIR": FAIRNESS_THRESHOLD,
            "reason": f"Bring {min_group} closer to {max_group} with the smallest direct rate adjustment that satisfies the fairness threshold.",
        }
    )

    if hotspots:
        hotspot = hotspots[0]
        secondary = hotspot.get("secondary_attribute")
        if secondary:
            subgroup_text = ", ".join(f"{key}={value}" for key, value in hotspot["group"].items())
            suggestions.append(
                {
                    "action": f"adjust_{secondary}_threshold".replace(" ", "_"),
                    "reason": f"Largest disparity appears in subgroup {subgroup_text}. Review thresholds, scoring cutoffs, or calibration for this segment first.",
                }
            )

    return suggestions


def analyze_group_rates(
    group_rates: dict[str, float],
    *,
    qualified_group_rates: dict[str, float] | None = None,
    warnings: list[str] | None = None,
    context_analysis: dict[str, Any] | None = None,
    feature_influence_rankings: list[dict[str, Any]] | None = None,
    most_influential_feature: str = "unknown",
    bias_hotspots: list[dict[str, Any]] | None = None,
    hidden_bias_detected: bool = False,
    simulations: list[dict[str, Any]] | None = None,
    repair_suggestions: list[dict[str, Any]] | None = None,
) -> FairnessResult:
    normalized_rates, max_group, min_group, max_rate, min_rate = _normalize_group_rates(group_rates)
    metrics, _, _, _, _ = _build_metrics(normalized_rates, qualified_group_rates)
    difference = metrics["SPD"]
    dir_value = metrics["DIR"]
    bias_detected, severity = _classify(dir_value)

    rounded_groups = {group: _round(rate) for group, rate in normalized_rates.items()}
    sorted_groups = [
        {"group": str(group), "selection_rate": _round(rate)}
        for group, rate in sorted(normalized_rates.items(), key=lambda item: item[1], reverse=True)
    ]

    subgroup_summary = None
    if context_analysis and context_analysis.get("largest_disparity_subgroup"):
        subgroup = context_analysis["largest_disparity_subgroup"]
        subgroup_summary = (
            f"The largest disparity occurs in the {subgroup['qualification_group']} subgroup, "
            f"where the subgroup DIR is {subgroup['metrics']['DIR']}."
        )

    hotspot_summary = None
    if bias_hotspots:
        hotspot = bias_hotspots[0]
        hotspot_label = ", ".join(f"{key}={value}" for key, value in hotspot["group"].items())
        hotspot_summary = f"The strongest hotspot is {hotspot_label} with DIR {hotspot['DIR']} and disparity {hotspot['difference']}."

    repair_summary = None
    if repair_suggestions:
        primary_repair = repair_suggestions[0]
        repair_summary = f"Minimum repair path: {primary_repair['action']} with {primary_repair.get('required_change', 'targeted adjustment')}."

    return FairnessResult(
        bias_detected=bias_detected,
        severity=severity,
        groups=rounded_groups,
        difference=_round(difference),
        DIR=_round(dir_value),
        metrics=metrics,
        most_advantaged_group=str(max_group),
        least_advantaged_group=str(min_group),
        most_influential_feature=most_influential_feature,
        explanation=_build_explanation(
            severity,
            metrics,
            str(max_group),
            str(min_group),
            subgroup_summary=subgroup_summary,
            influential_feature=most_influential_feature if most_influential_feature != "unknown" else None,
            hidden_bias_detected=hidden_bias_detected,
            hotspot_summary=hotspot_summary,
            repair_summary=repair_summary,
        ),
        bias_score=_bias_score_from_metrics(metrics),
        recommendations=_build_recommendations(severity, difference, str(max_group), str(min_group)),
        warnings=warnings or [],
        bias_hotspots=bias_hotspots or [],
        hidden_bias_detected=hidden_bias_detected,
        simulations=simulations or [],
        repair_suggestions=repair_suggestions or [],
        feature_impact_ranking=[
            {"feature": item["feature"], "impact": item["impact"]}
            for item in (feature_influence_rankings or [])
        ],
        stats={
            "group_count": len(rounded_groups),
            "max_rate": _round(max_rate),
            "min_rate": _round(min_rate),
            "parity_percent": _round(dir_value * 100.0),
            "selection_gap_percent": _round(difference * 100.0),
            "group_rankings": sorted_groups,
            "context_analysis": context_analysis or {},
            "feature_influence_rankings": feature_influence_rankings or [],
            "bias_hotspots": bias_hotspots or [],
            "hidden_bias_detected": hidden_bias_detected,
            "simulations": simulations or [],
            "repair_suggestions": repair_suggestions or [],
        },
    )


def analyze_simple_input(group_a: Any, group_b: Any) -> FairnessResult:
    try:
        value_a = float(group_a)
        value_b = float(group_b)
    except (TypeError, ValueError) as exc:
        raise AnalysisError("groupA and groupB must be numeric.") from exc

    if value_a < 0 or value_b < 0:
        raise AnalysisError("groupA and groupB must be non-negative.")

    rate_a = value_a / 100.0
    rate_b = value_b / 100.0

    return analyze_group_rates(
        {"groupA": rate_a, "groupB": rate_b},
        qualified_group_rates={"groupA": rate_a, "groupB": rate_b},
        warnings=["Qualification context is unavailable for simple mode, so EOD and AOD mirror overall disparity."],
        most_influential_feature="simple_input",
    )


def load_dataset(file_storage) -> pd.DataFrame:
    filename = (file_storage.filename or "").strip()
    if not filename:
        raise AnalysisError("No file was provided.")

    lowered = filename.lower()
    try:
        # Read file content into BytesIO for pandas compatibility
        file_content = file_storage.read()
        file_buffer = BytesIO(file_content)
        
        if lowered.endswith(".csv"):
            df = pd.read_csv(file_buffer)
        elif lowered.endswith(".xlsx"):
            df = pd.read_excel(file_buffer)
        else:
            raise AnalysisError("Unsupported file type. Please upload a CSV or XLSX file.")
    except AnalysisError:
        raise
    except Exception as exc:
        raise AnalysisError("The uploaded file could not be read.") from exc

    if df.empty:
        raise AnalysisError("The uploaded dataset is empty.")

    # Remove fully empty rows to avoid false positives in dataset shape.
    df = df.dropna(how="all")
    if df.empty:
        raise AnalysisError("The uploaded dataset is empty.")

    return df


def _normalize_outcome_value(value: Any) -> int:
    if pd.isna(value):
        return 0 # Treat NaN as failure/zero in outcome

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1 or value == 1.0: return 1
        if value == 0 or value == 0.0: return 0
        return 1 if value > 0 else 0 # Lenient numeric binarization

    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return 1
    if normalized in FALSE_VALUES:
        return 0
    
    # Fallback for individual row mapping
    return 1 

def _binarize_outcome_series(series: pd.Series) -> tuple[pd.Series, str]:
    """
    Intelligently converts any series into a binary 0/1 series.
    Returns (binarized_series, description_of_mapping)
    """
    # 1. Try standard normalization first (works for pure binary columns)
    try:
        sample = series.dropna().head(100)
        mapped_sample = sample.map(lambda x: str(x).strip().lower())
        if all(v in TRUE_VALUES or v in FALSE_VALUES for v in mapped_sample):
             return series.map(_normalize_outcome_value).fillna(0).astype(int), "standard binary mapping"
    except:
        pass

    unique_vals = [str(v) for v in series.dropna().unique()]
    if not unique_vals:
        return series.fillna(0).astype(int), "empty column"
    
    unique_lower = [v.lower() for v in unique_vals]

    # 2. Ordinal scale detection (e.g., Low/Medium/High)
    ordinal_positive = {"high", "very high", "severe", "critical"}
    ordinal_negative = {"low", "very low", "none", "minimal"}
    
    has_ordinal_positive = any(v in ordinal_positive for v in unique_lower)
    has_ordinal_negative = any(v in ordinal_negative for v in unique_lower)
    
    if has_ordinal_positive and has_ordinal_negative:
        # Map 'High' -> 1, everything else -> 0
        positive_vals = {str(v) for v, vl in zip(unique_vals, unique_lower) if vl in ordinal_positive}
        mapping = {v: (1 if v in positive_vals else 0) for v in series.unique()}
        return series.map(mapping).fillna(0).astype(int), f"mapped {positive_vals} to 1 (ordinal scale), others to 0"

    # 3. Keyword-based positive detection
    positive_keywords = ["pass", "high", "success", "approve", "select", "positive", "recid"]
    positive_candidates = [v for v in unique_vals if v.lower() in TRUE_VALUES or any(k in v.lower() for k in positive_keywords)]
    
    if positive_candidates:
        target = positive_candidates[0]
        mapping = {v: (1 if v == target else 0) for v in series.unique()}
        return series.map(mapping).fillna(0).astype(int), f"mapped '{target}' to 1, others to 0"
    
    # 4. Fallback: Treat the least frequent value as 1 (the "event" of interest)
    counts = series.value_counts()
    if len(counts) > 1:
        least_freq = counts.index[-1]
        mapping = {v: (1 if v == least_freq else 0) for v in series.unique()}
        return series.map(mapping).fillna(0).astype(int), f"mapped least frequent '{least_freq}' to 1, others to 0"
    elif len(counts) == 1:
        return pd.Series(0, index=series.index), f"constant column (all '{counts.index[0]}'), mapped to 0"
    
    return series.fillna(0).astype(int), "fallback zero mapping"


def _candidate_categorical_columns(df: pd.DataFrame) -> list[str]:
    candidates: list[tuple[float, str]] = []
    for column, profile in _profile_columns(df).items():
        if profile["identifier_like"]:
            continue
        if profile["groupable_categorical"]:
            candidates.append((float(profile["group_score"]), str(column)))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [column for _, column in candidates]


def _candidate_groupable_numeric_columns(df: pd.DataFrame, excluded_columns: set[str]) -> list[str]:
    candidates: list[tuple[float, str]] = []
    for column, profile in _profile_columns(df).items():
        normalized = _canonical_name(column)
        if normalized in excluded_columns or profile["identifier_like"]:
            continue
        if profile["groupable_numeric"]:
            candidates.append((float(profile["group_score"]), str(column)))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [column for _, column in candidates]


def _candidate_groupable_date_columns(df: pd.DataFrame, excluded_columns: set[str]) -> list[str]:
    candidates: list[tuple[float, str]] = []
    for column, profile in _profile_columns(df).items():
        normalized = _canonical_name(column)
        if normalized in excluded_columns or profile["identifier_like"]:
            continue
        if profile["groupable_date"]:
            candidates.append((float(profile["group_score"]), str(column)))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [column for _, column in candidates]


def _candidate_outcome_columns(df: pd.DataFrame) -> list[str]:
    candidates: list[tuple[float, str]] = []
    for column, profile in _profile_columns(df).items():
        score = float(profile["outcome_score"])
        if score > 0.0:
            candidates.append((score, str(column)))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [column for _, column in candidates]


def _candidate_numeric_outcome_columns(df: pd.DataFrame, excluded_columns: set[str]) -> list[str]:
    candidates: list[tuple[float, str]] = []
    for column, profile in _profile_columns(df).items():
        normalized = _canonical_name(column)
        if normalized in excluded_columns or profile["identifier_like"]:
            continue
        if profile["is_numeric"] and profile["unique_count"] >= 4:
            candidates.append((float(profile["outcome_score"]), str(column)))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [column for _, column in candidates]


def _derive_binary_outcome_column(
    df: pd.DataFrame,
    *,
    excluded_columns: set[str],
) -> str | None:
    numeric_candidates = _candidate_numeric_outcome_columns(df, excluded_columns)
    if not numeric_candidates:
        return None

    source_column = numeric_candidates[0]
    series = df[source_column].dropna().astype(float)
    if series.empty:
        return None

    threshold = float(series.median())
    derived_column = "__derived_binary_outcome__"
    df[derived_column] = (pd.to_numeric(df[source_column], errors="coerce") >= threshold).astype("Int64")
    df.attrs["derived_outcome_info"] = {
        "source_column": source_column,
        "strategy": "median_threshold",
        "threshold": _round(threshold),
        "derived_column": derived_column,
    }
    return derived_column


def _derive_protected_column(df: pd.DataFrame) -> str | None:
    excluded = {_canonical_name(column) for column in df.columns if str(column).startswith("__derived_")}

    date_candidates = _candidate_groupable_date_columns(df, excluded)
    if date_candidates:
        source_column = date_candidates[0]
        parsed = pd.to_datetime(df[source_column], errors="coerce")
        if parsed.notna().any():
            derived_column = "__derived_protected_group__"
            month_names = parsed.dt.month_name().fillna("UNKNOWN")
            df[derived_column] = month_names.astype(str)
            df.attrs["derived_protected_info"] = {
                "source_column": source_column,
                "strategy": "calendar_month",
                "derived_column": derived_column,
            }
            return derived_column

    numeric_candidates = _candidate_groupable_numeric_columns(df, excluded)
    if numeric_candidates:
        source_column = numeric_candidates[0]
        series = pd.to_numeric(df[source_column], errors="coerce")
        if series.notna().sum() >= 4:
            derived_column = "__derived_protected_group__"
            binned = _safe_qcut(series.dropna().astype(float), bins=4)
            mapped = pd.Series(index=series.dropna().index, data=binned.values)
            df[derived_column] = mapped.reindex(df.index).fillna("UNKNOWN").astype(str)
            df.attrs["derived_protected_info"] = {
                "source_column": source_column,
                "strategy": "quantile_binning",
                "derived_column": derived_column,
            }
            return derived_column

    return None


def _resolve_protected_columns(df: pd.DataFrame, protected_attribute: str | None = None) -> list[str]:
    columns = {str(column).strip().lower(): column for column in df.columns}
    if protected_attribute:
        requested = [item.strip() for item in protected_attribute.split(",") if item.strip()]
        if not requested:
            raise AnalysisError("Protected attribute column was not provided.")

        resolved: list[str] = []
        for item in requested:
            key = item.lower()
            if key not in columns:
                raise AnalysisError(f"Protected attribute column '{item}' was not found.")
            resolved.append(str(columns[key]))
        return resolved

    categorical_columns = _candidate_categorical_columns(df)
    if not categorical_columns:
        derived_protected = _derive_protected_column(df)
        if not derived_protected:
            raise AnalysisError("No protected attribute column could be detected.")
        categorical_columns = [derived_protected]

    protected_columns = categorical_columns[:1]
    return [str(column) for column in protected_columns]


def _detect_intersectional_columns(
    df: pd.DataFrame,
    protected_columns: list[str],
    outcome_column: str,
    qualification_column: str | None = None,
) -> list[str]:
    if len(protected_columns) > 1:
        return protected_columns

    primary = protected_columns[0]
    candidates = _candidate_categorical_columns(df)
    extras = [
        str(column)
        for column in candidates
        if str(column) not in {primary, outcome_column, qualification_column}
    ]
    if not extras:
        return protected_columns

    secondary = extras[0]
    return [primary, secondary]


def detect_columns(
    df: pd.DataFrame,
    protected_attribute: str | None = None,
    outcome_column: str | None = None,
) -> tuple[str, str]:
    protected_columns = _resolve_protected_columns(df, protected_attribute)
    protected_column = protected_columns[0]
    columns = {str(column).strip().lower(): column for column in df.columns}

    if outcome_column:
        key = outcome_column.strip().lower()
        if key not in columns:
            raise AnalysisError(f"Outcome column '{outcome_column}' was not found.")
        resolved_outcome = columns[key]
        # No longer raising error here, we binarize in analyze_dataset
    else:
        excluded_outcome_columns = {_canonical_name(protected_column)}
        derived_protected_info = df.attrs.get("derived_protected_info")
        if isinstance(derived_protected_info, dict) and derived_protected_info.get("source_column"):
            excluded_outcome_columns.add(_canonical_name(derived_protected_info["source_column"]))
        outcome_candidates = [column for column in _candidate_outcome_columns(df) if column != protected_column]
        if not outcome_candidates:
            derived_outcome = _derive_binary_outcome_column(
                df,
                excluded_columns=excluded_outcome_columns,
            )
            if not derived_outcome:
                raise AnalysisError("No binary outcome column could be detected.")
            outcome_candidates = [derived_outcome]

        resolved_outcome = outcome_candidates[0]

    if protected_column == resolved_outcome:
        raise AnalysisError("Protected attribute and outcome column must be different.")

    return str(protected_column), str(resolved_outcome)


def analyze_dataset(
    df: pd.DataFrame,
    protected_attribute: str | None = None,
    outcome_column: str | None = None,
    qualification_column: str | None = None,
) -> FairnessResult:
    # Step 1: Scan all columns and fields (Profile)
    column_profile = _profile_columns(df)
    warnings = []
    
    # Step 2: Resolve metadata (Protected Attributes & Outcome) without hints
    protected_columns = _resolve_protected_columns(df, protected_attribute)
    protected_column = protected_columns[0]
    resolved_outcome = detect_columns(df, protected_attribute, outcome_column)[1]
    
    qualification_resolved = _detect_qualification_column(
        df,
        excluded_columns={_canonical_name(column) for column in [*protected_columns, resolved_outcome]},
        qualification_column=qualification_column,
    )
    
    intersectional_columns = _detect_intersectional_columns(
        df,
        protected_columns,
        resolved_outcome,
        qualification_column=qualification_resolved,
    )

    # Step 3: Prepare Working Data (Keep all columns for full analysis)
    working_df = df.copy()
    
    # We still need to drop rows with missing values in the primary columns for fairness metrics
    working_df = working_df.dropna(subset=[*protected_columns, resolved_outcome])
    if working_df.empty:
        raise AnalysisError("No valid rows remain after removing missing values in protected or outcome columns.")

    for column in protected_columns:
        working_df[column] = working_df[column].astype(str).str.strip()
        working_df = working_df[working_df[column] != ""]
    if working_df.empty:
        raise AnalysisError("Protected attribute column contains no valid group values.")

    binarized_outcome, binarization_msg = _binarize_outcome_series(working_df[resolved_outcome])
    working_df[resolved_outcome] = binarized_outcome
    warnings.append(f"Outcome binarization: {binarization_msg}")
    qualification_label_column = None
    if qualification_resolved:
        qualification_label_column = f"{qualification_resolved}__qualification_bucket"
        working_df[qualification_label_column] = _prepare_qualification_series(working_df[qualification_resolved], qualification_resolved)

    group_rates, group_counts = _selection_rates_from_frame(working_df, protected_columns, resolved_outcome)

    if len(group_rates) < 2:
        raise AnalysisError("Dataset analysis requires at least two protected groups.")

    qualified_subset = _qualified_subset(working_df, qualification_label_column)
    qualified_group_rates: dict[str, float] | None = None
    qualified_group_counts: dict[str, int] | None = None
    if not qualified_subset.empty:
        qualified_group_rates, qualified_group_counts = _selection_rates_from_frame(
            qualified_subset,
            protected_columns,
            resolved_outcome,
        )
        if len(qualified_group_rates) < 2:
            qualified_group_rates = None
            qualified_group_counts = None

    context = _context_analysis(working_df, protected_columns, resolved_outcome, qualification_label_column)
    most_influential_feature, feature_rankings = _feature_influence_analysis(
        working_df,
        resolved_outcome,
        excluded_columns={
            _canonical_name(column)
            for column in [*protected_columns, resolved_outcome, qualification_label_column]
            if column is not None
        },
    )
    bias_hotspots, hotspot_counts = _bias_hotspot_analysis(
        working_df,
        protected_columns,
        resolved_outcome,
        excluded_columns={
            _canonical_name(column)
            for column in [*protected_columns, resolved_outcome, qualification_label_column]
            if column is not None
        },
    )
    intersectional_analysis: dict[str, Any] = {}
    if len(intersectional_columns) > 1:
        intersectional_rates, intersectional_counts = _selection_rates_from_frame(
            working_df,
            intersectional_columns,
            resolved_outcome,
        )
        if len(intersectional_rates) >= 2:
            intersectional_metrics, intersectional_advantaged, intersectional_disadvantaged, _, _ = _build_metrics(
                intersectional_rates
            )
            intersectional_analysis = {
                "attributes": intersectional_columns,
                "groups": {group: _round(rate) for group, rate in intersectional_rates.items()},
                "group_counts": intersectional_counts,
                "metrics": intersectional_metrics,
                "most_advantaged_group": intersectional_advantaged,
                "least_advantaged_group": intersectional_disadvantaged,
            }

    detected_warnings = _detect_warnings(
        df,
        working_df,
        protected_column,
        resolved_outcome,
        group_counts,
        qualified_group_counts=qualified_group_counts,
        subgroup_counts=hotspot_counts,
    )
    warnings.extend(detected_warnings)

    derived_outcome_info = df.attrs.get("derived_outcome_info")
    if derived_outcome_info:
        warnings.append(
            f"Derived binary outcome from {derived_outcome_info['source_column']} using median threshold {derived_outcome_info['threshold']}."
        )

    metrics, max_group, min_group, max_rate, min_rate = _build_metrics(group_rates, qualified_group_rates)
    hidden_bias_detected = (
        _classify(metrics["DIR"])[1] == "LOW"
        and any(hotspot.get("severity") == "HIGH" for hotspot in bias_hotspots)
    )
    simulations = _simulate_counterfactuals(
        metrics,
        min_group,
        max_group,
        min_rate,
        max_rate,
        most_influential_feature,
        feature_rankings,
    )
    repair_suggestions = _build_repair_suggestions(
        min_group,
        max_group,
        min_rate,
        max_rate,
        bias_hotspots,
    )

    result = analyze_group_rates(
        group_rates,
        qualified_group_rates=qualified_group_rates,
        warnings=warnings,
        context_analysis=context,
        feature_influence_rankings=feature_rankings,
        most_influential_feature=most_influential_feature,
        bias_hotspots=bias_hotspots,
        hidden_bias_detected=hidden_bias_detected,
        simulations=simulations,
        repair_suggestions=repair_suggestions,
    )

    stats = dict(result.stats)
    stats["protected_attributes"] = protected_columns
    stats["intersectional_analysis"] = intersectional_analysis
    stats["qualification_column"] = qualification_resolved
    stats["column_profile"] = column_profile
    derived_protected_info = df.attrs.get("derived_protected_info")
    if derived_protected_info:
        stats["derived_protected"] = derived_protected_info
    if derived_outcome_info:
        stats["derived_outcome"] = derived_outcome_info
    if qualification_label_column:
        stats["qualification_groups"] = sorted(working_df[qualification_label_column].dropna().astype(str).unique().tolist())

    return FairnessResult(
        bias_detected=result.bias_detected,
        severity=result.severity,
        groups=result.groups,
        difference=result.difference,
        DIR=result.DIR,
        metrics=result.metrics,
        most_advantaged_group=result.most_advantaged_group,
        least_advantaged_group=result.least_advantaged_group,
        most_influential_feature=result.most_influential_feature,
        explanation=result.explanation,
        bias_score=result.bias_score,
        recommendations=result.recommendations,
        warnings=result.warnings,
        bias_hotspots=result.bias_hotspots,
        hidden_bias_detected=result.hidden_bias_detected,
        simulations=result.simulations,
        repair_suggestions=result.repair_suggestions,
        feature_impact_ranking=result.feature_impact_ranking,
        stats=stats,
    )
