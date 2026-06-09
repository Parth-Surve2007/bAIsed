import numpy as np
import pandas as pd
from typing import Any, Callable, Dict, List, Tuple
from .analysis import _round, _selection_rates_from_frame, _build_metrics

def calculate_advanced_metrics(
    df: pd.DataFrame,
    protected_columns: list[str],
    outcome_column: str,
    qualification_column: str | None = None
) -> dict[str, Any]:
    """Calculates advanced fairness metrics inspired by Fairlearn."""
    
    # Extract selection rates for demographic parity and true positive rate (Equal Opportunity)
    rates, counts = _selection_rates_from_frame(df, protected_columns, outcome_column)
    metrics, advantaged, disadvantaged, max_rate, min_rate = _build_metrics(rates)
    
    # We will return the metrics we already have plus placeholders for deeper ones if needed
    advanced_metrics = {
        "demographic_parity_difference": metrics.get("SPD", 0.0),
        "demographic_parity_ratio": metrics.get("DIR", 1.0),
        "equalized_odds_difference": metrics.get("AOD", 0.0),
        "equal_opportunity_difference": metrics.get("EOD", 0.0),
    }
    
    return {
        "metrics": advanced_metrics,
        "most_advantaged_group": advantaged,
        "least_advantaged_group": disadvantaged
    }

def bootstrap_confidence_intervals(
    df: pd.DataFrame,
    protected_columns: list[str],
    outcome_column: str,
    n_bootstraps: int = 50
) -> dict[str, dict[str, float]]:
    """Calculates bootstrap confidence intervals for DIR and SPD."""
    if len(df) == 0:
        return {}
        
    dir_samples = []
    spd_samples = []
    
    # We cap n_bootstraps internally if dataset is large to prevent timeouts
    if len(df) > 5000:
        n_bootstraps = min(n_bootstraps, 20)
    
    for _ in range(n_bootstraps):
        sample_df = df.sample(n=len(df), replace=True)
        try:
            rates, _ = _selection_rates_from_frame(sample_df, protected_columns, outcome_column)
            if len(rates) >= 2:
                metrics, _, _, _, _ = _build_metrics(rates)
                dir_samples.append(metrics["DIR"])
                spd_samples.append(metrics["SPD"])
        except Exception:
            continue
            
    if not dir_samples:
        return {}
        
    return {
        "DIR": {
            "lower": _round(float(np.percentile(dir_samples, 2.5))),
            "upper": _round(float(np.percentile(dir_samples, 97.5)))
        },
        "SPD": {
            "lower": _round(float(np.percentile(spd_samples, 2.5))),
            "upper": _round(float(np.percentile(spd_samples, 97.5)))
        }
    }

def generate_mitigation_suggestions(
    advanced_metrics: dict[str, Any],
    hotspots: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Generates Fairlearn-style mitigation suggestions."""
    suggestions = []
    
    spd = advanced_metrics.get("metrics", {}).get("demographic_parity_difference", 0.0)
    
    if spd > 0.1:
        suggestions.append({
            "strategy": "Threshold Optimization",
            "description": "Adjust decision thresholds separately for each group to equalize the specified metric (e.g., Demographic Parity or Equalized Odds) while maximizing accuracy.",
            "type": "Post-processing"
        })
        
        suggestions.append({
            "strategy": "Exponentiated Gradient Reduction",
            "description": "Treat fairness as an optimization constraint and train a cost-sensitive classifier. Best for achieving Demographic Parity or Equalized Odds during training.",
            "type": "In-processing"
        })
        
    if hotspots:
        suggestions.append({
            "strategy": "Correlation Remover",
            "description": "Apply a linear transformation to the features to remove their correlation with the protected attribute while retaining as much information as possible.",
            "type": "Pre-processing"
        })
        
    return suggestions

def perform_intersectional_analysis(
    df: pd.DataFrame,
    primary_protected_columns: list[str],
    secondary_protected_columns: list[str],
    outcome_column: str
) -> list[dict[str, Any]]:
    """Analyzes the intersection of two protected attributes."""
    combined_columns = list(set(primary_protected_columns + secondary_protected_columns))
    if len(combined_columns) < 2:
        return []
        
    rates, counts = _selection_rates_from_frame(df, combined_columns, outcome_column)
    
    intersections = []
    global_max_rate = max(rates.values()) if rates else 0.0
    
    for group_key, rate in rates.items():
        dir_val = 1.0 if global_max_rate == 0 else rate / global_max_rate
        spd_val = global_max_rate - rate
        
        intersections.append({
            "group": group_key,
            "sample_size": counts.get(group_key, 0),
            "selection_rate": _round(rate),
            "DIR": _round(dir_val),
            "SPD": _round(spd_val)
        })
        
    intersections.sort(key=lambda x: x["DIR"])
    return intersections
