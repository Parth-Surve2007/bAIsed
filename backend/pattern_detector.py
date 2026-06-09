from __future__ import annotations

from typing import Any

try:
    from .analysis import FairnessResult
except ImportError:  # pragma: no cover - direct script fallback
    from analysis import FairnessResult


def detect_bias_pattern(
    result: FairnessResult,
    proxy_findings: list[dict[str, Any]],
    dataset_risk: dict[str, Any],
) -> dict[str, Any]:
    evidence: list[str] = []
    pattern_type = "NO_SIGNIFICANT_BIAS"
    confidence = 0.55
    recommended_action = "Continue monitoring fairness metrics over future audits."

    high_proxy = next((item for item in proxy_findings if item.get("risk") == "HIGH"), None)
    if high_proxy:
        pattern_type = "PROXY_BIAS"
        confidence = 0.82
        evidence.append(
            f"{high_proxy['feature']} is strongly associated with {high_proxy['proxy_for']}."
        )
        recommended_action = "Review or constrain high-risk proxy features before deployment."

    elif result.hidden_bias_detected or any(
        hotspot.get("severity") == "HIGH" for hotspot in (result.bias_hotspots or [])
    ):
        pattern_type = "INTERSECTIONAL_HIDDEN_BIAS"
        confidence = 0.78
        evidence.append("At least one subgroup hotspot has high-severity disparity.")
        recommended_action = "Prioritize subgroup-level mitigation and collect more subgroup samples."

    elif dataset_risk.get("risk_level") == "HIGH":
        pattern_type = "SMALL_SAMPLE_UNRELIABLE"
        confidence = 0.72
        evidence.append("Dataset reliability risks may make the audit unstable.")
        recommended_action = "Increase sample size and rebalance protected groups before relying on the result."

    elif result.bias_detected and float(result.DIR or 1) < 0.8:
        pattern_type = "GLOBAL_SELECTION_DISPARITY"
        confidence = 0.76
        evidence.append(f"Global DIR is {result.DIR}, below the 0.8 fairness threshold.")
        recommended_action = "Adjust thresholds or selection policy for the least-advantaged group."

    elif abs(float(result.difference or 0)) >= 0.1:
        pattern_type = "THRESHOLD_DRIVEN_DISPARITY"
        confidence = 0.64
        evidence.append("Selection-rate gap exists even though global severity is not high.")
        recommended_action = "Run threshold what-if simulation and monitor drift."

    if result.least_advantaged_group and result.most_advantaged_group:
        evidence.append(
            f"{result.least_advantaged_group} trails {result.most_advantaged_group} in favorable outcomes."
        )

    return {
        "pattern_type": pattern_type,
        "confidence": round(confidence, 2),
        "evidence": evidence[:4],
        "recommended_action": recommended_action,
    }
