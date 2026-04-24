from __future__ import annotations

from typing import Any


CONSTRAINT_SETTINGS: dict[str, dict[str, float]] = {
    "Loose": {"uplift_multiplier": 0.55, "advantaged_drag": 0.01, "accuracy_penalty": 0.4},
    "Optimal": {"uplift_multiplier": 0.85, "advantaged_drag": 0.02, "accuracy_penalty": 0.9},
    "Strict": {"uplift_multiplier": 1.15, "advantaged_drag": 0.035, "accuracy_penalty": 1.6},
}


def _round(value: float, digits: int = 4) -> float:
    return round(float(value), digits)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric


def _normalize_constraint(value: Any) -> str:
    text = str(value or "Optimal").strip().title()
    return text if text in CONSTRAINT_SETTINGS else "Optimal"


def _selection_rates_from_payload(payload: dict[str, Any]) -> tuple[float, float]:
    groups = payload.get("groups")
    if isinstance(groups, dict) and len(groups) >= 2:
        rates = sorted((_safe_float(rate) for rate in groups.values()), reverse=True)
        return max(0.0, rates[0]), max(0.0, rates[-1])

    stats = payload.get("stats")
    if isinstance(stats, dict):
        rankings = stats.get("group_rankings")
        if isinstance(rankings, list) and len(rankings) >= 2:
            ordered = sorted((_safe_float(item.get("selection_rate")) for item in rankings), reverse=True)
            return max(0.0, ordered[0]), max(0.0, ordered[-1])

    dir_value = _safe_float(payload.get("DIR"), 0.62)
    max_rate = 0.78
    min_rate = max_rate * max(0.0, min(1.0, dir_value))
    return max_rate, min_rate


def simulate_fairness_scenario(payload: dict[str, Any]) -> dict[str, Any]:
    diversity_weight = _safe_float(payload.get("diversity_weight"), 0.75)
    if diversity_weight > 1:
        diversity_weight = diversity_weight / 100.0
    diversity_weight = max(0.0, min(1.0, diversity_weight))

    constraint = _normalize_constraint(payload.get("fairness_constraint"))
    settings = CONSTRAINT_SETTINGS[constraint]

    result = payload.get("analysis_result")
    analysis_result = result if isinstance(result, dict) else {}

    max_rate, min_rate = _selection_rates_from_payload(analysis_result)
    baseline_dir = 1.0 if max_rate == 0 else min_rate / max_rate
    baseline_spd = max(0.0, max_rate - min_rate)

    target_gap = max(0.0, max_rate * 0.2)
    current_gap = max(0.0, max_rate - min_rate)
    improvement_window = max(0.0, current_gap - target_gap)

    uplift = improvement_window * diversity_weight * settings["uplift_multiplier"]
    simulated_min_rate = min(max_rate, min_rate + uplift)
    simulated_max_rate = max(simulated_min_rate, max_rate - (settings["advantaged_drag"] * diversity_weight))

    new_dir = 1.0 if simulated_max_rate == 0 else simulated_min_rate / simulated_max_rate
    new_spd = simulated_max_rate - simulated_min_rate
    parity_improvement = max(0.0, (new_dir - baseline_dir) * 100.0)

    estimated_accuracy = 94.8 - (diversity_weight * settings["accuracy_penalty"]) - (0.35 if constraint == "Strict" else 0.0)
    estimated_accuracy = max(84.0, min(99.0, estimated_accuracy))

    bias_reduced = new_dir >= baseline_dir and new_spd <= baseline_spd
    if diversity_weight < 0.15:
        action_text = "Maintain current policy mix with only light monitoring."
    elif constraint == "Strict":
        action_text = f"Increase diversity weight to {diversity_weight:.2f} and tighten decision thresholds for the lowest-performing group."
    else:
        action_text = f"Increase diversity weight to {diversity_weight:.2f} and apply mild reweighting."

    return {
        "scenario": {
            "diversity_weight": _round(diversity_weight, 2),
            "fairness_constraint": constraint,
        },
        "change": action_text,
        "metrics": {
            "baseline_DIR": _round(baseline_dir),
            "baseline_SPD": _round(-baseline_spd),
            "new_DIR": _round(new_dir),
            "new_SPD": _round(-new_spd),
            "estimated_accuracy": _round(estimated_accuracy, 1),
            "parity_improvement_percent": _round(parity_improvement, 1),
        },
        "bias_reduced": bias_reduced,
        "instant_label": "Instant",
    }
