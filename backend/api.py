from __future__ import annotations

from io import BytesIO
from json import JSONEncoder
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, request, send_file
import json
import math
import numpy as np
import os
import pandas as pd
import shutil
import uuid

try:
    from .analysis import AnalysisError, analyze_dataset, analyze_simple_input, detect_columns, load_dataset
    from .preprocessor import standardize_dataset
    from .simulator import simulate_fairness_scenario
except ImportError:  # pragma: no cover - direct script fallback
    from analysis import AnalysisError, analyze_dataset, analyze_simple_input, detect_columns, load_dataset
    from preprocessor import standardize_dataset
    from simulator import simulate_fairness_scenario


class NaNSafeEncoder(JSONEncoder):
    """JSON encoder that converts NaN and Inf to null."""

    def encode(self, o):
        if isinstance(o, float):
            if math.isnan(o) or math.isinf(o):
                return "null"
        return super().encode(o)

    def iterencode(self, o, _one_shot=False):
        """Encode the given object and yield each string representation as available."""
        for chunk in super().iterencode(o, _one_shot):
            yield chunk


def clean_for_json(obj: Any) -> Any:
    """Recursively clean NaN and Inf values from nested structures."""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean_for_json(item) for item in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.floating, np.integer)):
        val = float(obj) if isinstance(obj, np.floating) else int(obj)
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val
    return obj


SITE_CONTENT: dict[str, dict[str, Any]] = {
    "landing": {
        "hero": {
            "current_score": "84.2%",
            "status": "Moderate Bias Detected",
            "parity_index": "0.842",
            "gender_parity": 92,
            "age_parity": 64,
        }
    },
    "solutions": {
        "hiring": {"pass_rate_ratio": "0.92", "gender_parity": "0.88"},
        "finance": {"compliance_rate": "99.8%"},
        "healthcare": {"adverse_impact": "-12%", "data_density": "4.2M pts"},
    },
    "methodology": {
        "dir_equation": "DIR = min(selection_rate) / max(selection_rate)",
        "threshold_title": "Fairness Threshold: DIR >= 0.8",
        "threshold_copy": (
            "The debugger uses the Four-Fifths Rule as its baseline threshold. "
            "Any group below 80% of the highest observed selection rate is flagged "
            "for deeper localization, simulation, and repair analysis."
        ),
        "statistical_parity": {"group_a": "0.61 Selection", "group_b": "0.43 Selection"},
        "equalized_odds": {"true_positive_rate": "0.08", "false_positive_rate": "0.05"},
        "remediation": {"baseline_dir": 0.62, "optimized_dir": 0.89},
    },
    "case_study": {
        "featured": {
            "title": "Equitable Talent Acquisition at TechCorp",
            "summary": (
                "How a Fortune 500 tech firm reduced demographic disparity in technical "
                "hiring by 42% using our lab-grade auditing toolkit."
            ),
            "bias_reduction": "-42%",
            "hiring_speed": "+18%",
        },
        "secondary": {
            "credit_gap": "-14% to -2%",
            "healthcare_parity": "99.2%",
            "public_sector_audit": "Full",
            "retail_bias": "Zero",
        },
    },
    "pricing_demo": {
        "plans": {
            "researcher": "$0",
            "pro_team": "$0",
            "enterprise": "Free",
        },
        "cta": {
            "headline": "Wait, you actually want to pay? haha ntothing to see here.",
            "body": (
                "We believe in contributing to open source. Code for all. "
                "Enjoy full access to our lab-grade auditing toolkit at no cost."
            ),
        },
    },
    "documentation": {
        "version": "v1.0.4-beta",
        "quickstart": [
            "npm install @baised/core",
            "baised init --project my-model-audit",
        ],
        "search_topics": [
            {
                "title": "Introduction",
                "href": "/methodology",
                "summary": "Overview of the fairness auditing framework and lifecycle coverage.",
            },
            {
                "title": "Quick Start",
                "href": "/methodology",
                "summary": "Install the CLI and bootstrap an audit project.",
            },
            {
                "title": "Architecture Overview",
                "href": "/methodology",
                "summary": "Understand the metrics engine, DIR, and explainability model.",
            },
            {
                "title": "API Reference",
                "href": "/methodology",
                "summary": "Authentication, endpoints, and operational limits.",
            },
        ],
    },
    "about": {
        "mission": "Algorithmic transparency for a fair future.",
        "tagline": "Detect Bias. Ensure Fairness. Automate Integrity.",
    },
}

DEMO_REQUESTS: list[dict[str, Any]] = []

TEMP_DATASETS = Path(__file__).resolve().parent / "temp_datasets"
TEMP_DATASETS.mkdir(exist_ok=True)

api_bp = Blueprint("api", __name__)


def _json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def humanize_column(col: str) -> str:
    """Convert raw column names to UI-friendly labels."""
    mapping = {
        "recsupervisionleveltext": "Supervision Level",
        "recidiviz_decile_score": "Risk Decile Score",
        "race": "Race",
        "sex": "Sex",
        "age_cat": "Age Category",
        "priors_count": "Prior Offenses Count",
        "c_charge_degree": "Charge Severity",
        "score_text": "Risk Score Label",
        "is_recid": "Recidivism Outcome",
        "two_year_recid": "2-Year Recidivism",
    }
    raw = str(col or "").strip()
    return mapping.get(raw.lower(), raw.replace("_", " ").title())


def safe_dataset_summary(df: pd.DataFrame, max_rows: int = 8) -> str:
    """Summarize dataset using complete row objects (no mid-row truncation)."""
    sample = df.head(max_rows).to_dict(orient="records")
    col_samples = {}
    for col in df.columns:
        col_samples[humanize_column(col)] = df[col].dropna().unique()[:5].tolist()
    summary = {
        "columns": [humanize_column(col) for col in df.columns],
        "column_samples": col_samples,
        "row_count": int(len(df)),
        "sample_rows": sample,
    }
    return json.dumps(summary, default=str)


def _compact_ml_summary(analysis_data: dict[str, Any]) -> str:
    metrics = analysis_data.get("metrics", {}) if isinstance(analysis_data.get("metrics"), dict) else {}
    compact = {
        "severity": analysis_data.get("severity"),
        "DIR": analysis_data.get("DIR", metrics.get("DIR")),
        "SPD": analysis_data.get("difference", metrics.get("SPD")),
        "EOD": metrics.get("EOD"),
        "AOD": metrics.get("AOD"),
        "bias_score": analysis_data.get("bias_score"),
        "most_advantaged_group": analysis_data.get("most_advantaged_group"),
        "least_advantaged_group": analysis_data.get("least_advantaged_group"),
        "most_influential_feature": humanize_column(str(analysis_data.get("most_influential_feature", "N/A"))),
        "warnings": (analysis_data.get("warnings") or [])[:5],
        "recommendations": (analysis_data.get("recommendations") or [])[:5],
        "bias_hotspots": (analysis_data.get("bias_hotspots") or [])[:3],
        "feature_impact_ranking": (analysis_data.get("feature_impact_ranking") or [])[:5],
    }
    return json.dumps(clean_for_json(compact), default=str)


def _severity_tokens(value: str) -> tuple[str, str]:
    normalized = str(value or "").strip().upper()
    if normalized in {"HIGH", "SEVERE"}:
        return "HIGH", "red"
    if normalized in {"MODERATE", "MEDIUM"}:
        return "MEDIUM", "amber"
    return "LOW", "green"


def _build_fallback_ai_report(analysis_data: dict[str, Any], row_count: int) -> dict[str, Any]:
    metrics = analysis_data.get("metrics", {}) if isinstance(analysis_data.get("metrics"), dict) else {}
    severity_label, severity_color = _severity_tokens(str(analysis_data.get("severity", "LOW")))
    dir_value = analysis_data.get("DIR", metrics.get("DIR", 0))
    spd_value = analysis_data.get("difference", metrics.get("SPD", 0))
    bias_score = analysis_data.get("bias_score", 0)
    most_advantaged = str(analysis_data.get("most_advantaged_group", "N/A"))
    least_advantaged = str(analysis_data.get("least_advantaged_group", "N/A"))
    top_feature = humanize_column(str(analysis_data.get("most_influential_feature", "N/A")))
    recommendations = [item for item in (analysis_data.get("recommendations") or []) if isinstance(item, str)][:3]
    recommended_actions = [
        {"priority": "IMMEDIATE", "action": recommendations[0] if len(recommendations) > 0 else "Audit threshold disparities for least-advantaged group."},
        {"priority": "SHORT_TERM", "action": recommendations[1] if len(recommendations) > 1 else "Rebalance training distribution and re-run fairness evaluation."},
        {"priority": "LONG_TERM", "action": recommendations[2] if len(recommendations) > 2 else "Set continuous fairness monitoring with group-level alerts."},
    ]

    disparity_ratio = "N/A"
    try:
        ratio = 1 / max(float(dir_value), 1e-6)
        disparity_ratio = f"{ratio:.2f}x"
    except Exception:
        pass

    confidence = "LOW" if row_count < 30 else "MEDIUM" if row_count < 100 else "HIGH"
    return {
        "severity_label": severity_label,
        "severity_color": severity_color,
        "headline": f"{least_advantaged} faces materially lower favorable outcomes than {most_advantaged}.",
        "metrics_summary": f"**DIR**={dir_value}, **SPD**={spd_value}, **Bias Score**={bias_score}. Current run indicates {severity_label} disparity risk.",
        "root_cause": {
            "primary_driver": top_feature,
            "explanation": f"The largest disparity signal aligns with {top_feature}. Feature distribution and threshold effects likely amplify outcome gaps for {least_advantaged}.",
        },
        "group_comparison": {
            "most_advantaged": most_advantaged,
            "least_advantaged": least_advantaged,
            "disparity_ratio": disparity_ratio,
            "plain_english": f"A person in {least_advantaged} is currently less likely to receive the same favorable outcome as someone in {most_advantaged}.",
        },
        "recommended_actions": recommended_actions,
        "compliance_flags": [
            "Potential discrimination risk requires documented mitigation and periodic bias monitoring under applicable fairness governance obligations."
        ],
        "confidence": confidence,
        "confidence_reason": f"Confidence is {confidence} based on sample size ({row_count} rows) and deterministic metric consistency.",
    }


def _normalize_ai_report(report: dict[str, Any], analysis_data: dict[str, Any], row_count: int) -> dict[str, Any]:
    fallback = _build_fallback_ai_report(analysis_data, row_count)
    if not isinstance(report, dict):
        return fallback

    merged = {**fallback, **report}
    root = merged.get("root_cause") if isinstance(merged.get("root_cause"), dict) else {}
    group = merged.get("group_comparison") if isinstance(merged.get("group_comparison"), dict) else {}
    merged["root_cause"] = {
        "primary_driver": humanize_column(str(root.get("primary_driver", fallback["root_cause"]["primary_driver"]))),
        "explanation": str(root.get("explanation", fallback["root_cause"]["explanation"])),
    }
    merged["group_comparison"] = {
        "most_advantaged": str(group.get("most_advantaged", fallback["group_comparison"]["most_advantaged"])),
        "least_advantaged": str(group.get("least_advantaged", fallback["group_comparison"]["least_advantaged"])),
        "disparity_ratio": str(group.get("disparity_ratio", fallback["group_comparison"]["disparity_ratio"])),
        "plain_english": str(group.get("plain_english", fallback["group_comparison"]["plain_english"])),
    }
    actions = merged.get("recommended_actions")
    if not isinstance(actions, list) or not actions:
        merged["recommended_actions"] = fallback["recommended_actions"]
    else:
        normalized_actions = []
        for idx, item in enumerate(actions[:3]):
            if isinstance(item, dict):
                normalized_actions.append(
                    {
                        "priority": str(item.get("priority", fallback["recommended_actions"][min(idx, 2)]["priority"])),
                        "action": str(item.get("action", fallback["recommended_actions"][min(idx, 2)]["action"])),
                    }
                )
        while len(normalized_actions) < 3:
            normalized_actions.append(fallback["recommended_actions"][len(normalized_actions)])
        merged["recommended_actions"] = normalized_actions

    flags = merged.get("compliance_flags")
    if not isinstance(flags, list) or not flags:
        merged["compliance_flags"] = fallback["compliance_flags"]
    else:
        merged["compliance_flags"] = [str(flag) for flag in flags[:3]]

    severity_label, severity_color = _severity_tokens(str(merged.get("severity_label", fallback["severity_label"])))
    merged["severity_label"] = severity_label
    merged["severity_color"] = severity_color
    merged["headline"] = str(merged.get("headline", fallback["headline"]))[:160]
    merged["metrics_summary"] = str(merged.get("metrics_summary", fallback["metrics_summary"]))
    merged["confidence"] = str(merged.get("confidence", fallback["confidence"])).upper()
    merged["confidence_reason"] = str(merged.get("confidence_reason", fallback["confidence_reason"]))
    return merged


def _normalize_action(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _resolve_action_payload(action: str, page: str) -> dict[str, str]:
    workbench_actions = {
        "get started",
        "start free audit",
        "start analyzing your data now",
        "deploy audit",
        "dashboard",
    }
    pricing_actions = {
        "book demo",
        "request demo",
        "request custom demo",
        "schedule a solution briefing",
        "schedule a consultation",
        "contact sales",
        "contact enterprise sales",
    }
    docs_actions = {
        "explore documentation",
        "download whitepaper",
        "view all integration",
        "support",
        "help",
        "security",
        "status",
    }
    login_actions = {
        "login",
        "sign in",
        "sign up",
        "start individual plan",
        "start 14-day free trial",
        "forgot password",
    }
    case_actions = {
        "explore hiring analytics",
        "read case study",
        "view full analysis",
    }

    if action in workbench_actions:
        return {"target": "/workbench", "message": "Opening the live fairness workbench."}
    if action in pricing_actions:
        return {"target": "/pricing", "message": "Routing you to the demo request workspace."}
    if action in docs_actions:
        if action == "download whitepaper":
            return {"target": "/api/downloads/whitepaper", "message": "Preparing the whitepaper download."}
        return {"target": "/methodology", "message": "Opening the documentation hub."}
    if action in login_actions:
        return {"target": "/login", "message": "Opening secure sign-in."}
    if action in case_actions:
        return {"target": "/case-study", "message": "Opening the impact report."}

    page_targets = {
        "landing": "/",
        "solutions": "/solutions",
        "methodology": "/methodology",
        "methodology": "/methodology",
        "about": "/about",
        "case_study": "/case-study",
        "pricing_demo": "/pricing",
        "login": "/login",
        "workbench": "/workbench",
    }
    return {"target": page_targets.get(page, "/"), "message": "Action resolved."}


def _search_docs(query: str) -> list[dict[str, str]]:
    terms = [part for part in _normalize_action(query).split(" ") if part]
    topics = SITE_CONTENT["documentation"]["search_topics"]
    if not terms:
        return topics

    results = []
    for item in topics:
        haystack = f"{item['title']} {item['summary']}".lower()
        if all(term in haystack for term in terms):
            results.append(item)

    return results


@api_bp.route("/analyze", methods=["OPTIONS"])
@api_bp.route("/ai-analyze", methods=["OPTIONS"])
@api_bp.route("/upload", methods=["OPTIONS"])
@api_bp.route("/simulate", methods=["OPTIONS"])
@api_bp.route("/api/demo-request", methods=["OPTIONS"])
@api_bp.route("/api/actions/resolve", methods=["OPTIONS"])
@api_bp.route("/scan", methods=["OPTIONS"])
@api_bp.route("/reset", methods=["OPTIONS"])
def preflight():
    return ("", 204)


@api_bp.get("/api/health")
def health_check():
    return jsonify({"message": "bAIsed API running"})


@api_bp.get("/api/site-content/<page_name>")
def site_content(page_name: str):
    page = SITE_CONTENT.get(page_name)
    if page is None:
        return _json_error("Unknown page.", 404)
    return jsonify(page)


@api_bp.get("/api/search")
def search():
    query = request.args.get("query", "")
    results = _search_docs(query)
    return jsonify({"query": query, "count": len(results), "results": results})


@api_bp.post("/api/actions/resolve")
def resolve_action():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _json_error("Request body must be valid JSON.")

    action = _normalize_action(str(payload.get("action", "")))
    page = str(payload.get("page", "")).strip()
    if not action:
        return _json_error("An action is required.")

    return jsonify(_resolve_action_payload(action, page))


@api_bp.post("/api/demo-request")
def demo_request():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _json_error("Request body must be valid JSON.")

    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip()
    company = str(payload.get("company", "")).strip()
    use_case = str(payload.get("use_case", "")).strip()

    if not name or not email or not company or not use_case:
        return _json_error("Name, email, company, and use case are required.")

    request_record = {
        "id": len(DEMO_REQUESTS) + 1,
        "name": name,
        "email": email,
        "company": company,
        "use_case": use_case,
    }
    DEMO_REQUESTS.append(request_record)

    return jsonify(
        {
            "message": f"Demo request recorded for {company}.",
            "request_id": request_record["id"],
            "redirect": "/workbench",
        }
    )


@api_bp.get("/api/downloads/whitepaper")
def download_whitepaper():
    content = (
        "# bAIsed Whitepaper\n\n"
        "This briefing summarizes the fairness workbench, the disparate impact ratio,\n"
        "and the recommended operational controls for high-stakes model reviews.\n\n"
        "Key ideas:\n"
        "- Use DIR and selection-gap monitoring together.\n"
        "- Audit protected attributes and binary outcomes explicitly.\n"
        "- Re-run fairness checks after remediation before deployment.\n"
    )
    buffer = BytesIO(content.encode("utf-8"))
    return send_file(
        buffer,
        as_attachment=True,
        download_name="baised-whitepaper.md",
        mimetype="text/markdown",
    )


@api_bp.post("/analyze")
def analyze():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be valid JSON."}), 400

    if "groupA" not in payload or "groupB" not in payload:
        return jsonify({"error": "Both groupA and groupB are required."}), 400

    try:
        result = analyze_simple_input(payload["groupA"], payload["groupB"])
    except AnalysisError as exc:
        return jsonify({"error": str(exc)}), 400

    response = result.to_dict()
    response["mode"] = "simple"
    return jsonify(clean_for_json(response))


@api_bp.post("/scan")
def scan():
    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "A file upload is required."}), 400

    try:
        df = load_dataset(file)
        df, preprocessor_report = standardize_dataset(df)

        dataset_id = str(uuid.uuid4())
        temp_path = TEMP_DATASETS / f"{dataset_id}.csv"
        df.to_csv(temp_path, index=False)

        try:
            from .analysis import _profile_columns  # type: ignore
        except ImportError:  # pragma: no cover - direct script fallback
            from analysis import _profile_columns  # type: ignore

        profile = _profile_columns(df)
        return jsonify(
            clean_for_json(
                {
                    "dataset_id": dataset_id,
                    "columns": list(df.columns),
                    "profile": profile,
                    "row_count": int(len(df)),
                    "preprocessor_report": preprocessor_report,
                }
            )
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@api_bp.post("/upload")
def upload():
    dataset_id = request.form.get("dataset_id")
    protected_attribute = request.form.get("protected_attribute")
    outcome_column = request.form.get("outcome_column")
    qualification_column = request.form.get("qualification_column")

    try:
        if dataset_id:
            temp_path = TEMP_DATASETS / f"{dataset_id}.csv"
            if not temp_path.exists():
                return jsonify({"error": "Dataset session expired. Please re-upload."}), 400
            df = pd.read_csv(temp_path)
            preprocessor_report = {"status": "Loaded from standardized workspace"}
        else:
            file = request.files.get("file")
            if file is None:
                return jsonify({"error": "A file upload or dataset ID is required."}), 400
            df = load_dataset(file)
            df, preprocessor_report = standardize_dataset(df)

        resolved_protected, resolved_outcome = detect_columns(
            df,
            protected_attribute=protected_attribute,
            outcome_column=outcome_column,
        )
        result = analyze_dataset(
            df,
            protected_attribute=protected_attribute,
            outcome_column=outcome_column,
            qualification_column=qualification_column,
        )
    except AnalysisError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        import traceback

        print(traceback.format_exc())
        return jsonify({"error": f"Analysis failed: {str(exc)}"}), 500

    response = result.to_dict()
    response["mode"] = "dataset"
    response["protected_attribute"] = resolved_protected
    response["protected_attributes"] = result.stats.get("protected_attributes", [resolved_protected])
    response["derived_protected"] = result.stats.get("derived_protected")
    response["outcome_column"] = resolved_outcome
    response["derived_outcome"] = result.stats.get("derived_outcome")
    response["qualification_column"] = result.stats.get("qualification_column")
    response["row_count"] = int(len(df))

    file_obj = request.files.get("file")
    response["file_name"] = file_obj.filename if file_obj else f"dataset_{dataset_id}.csv"

    response["preprocessor_report"] = preprocessor_report
    return jsonify(clean_for_json(response))


@api_bp.post("/simulate")
def simulate():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be valid JSON."}), 400

    try:
        response = simulate_fairness_scenario(payload)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(clean_for_json(response))


@api_bp.post("/ai-analyze")
def ai_analyze():
    import urllib.error
    import urllib.parse
    import urllib.request
    import time

    file = request.files.get("file")
    if file is None:
        return jsonify({"error": "A file upload is required."}), 400

    analysis_json = request.form.get("analysis_json", "{}")
    try:
        analysis_data = json.loads(analysis_json)
    except Exception:
        analysis_data = {}

    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    if not gemini_api_key:
        return jsonify({"error": "GEMINI_API_KEY is not configured on the server."}), 500

    try:
        df = load_dataset(file)
    except Exception as exc:
        return jsonify({"error": f"File processing failed: {str(exc)}"}), 400

    row_count = int(len(df))
    columns = list(df.columns)

    dataset_summary = safe_dataset_summary(df, max_rows=8)
    ml_summary = _compact_ml_summary(analysis_data)

    system_prompt = (
        "You are an expert AI fairness auditor. Analyze bias in AI/ML systems. "
        "You MUST respond with ONLY valid JSON. No markdown fences. No preamble. "
        "No explanation outside the JSON. Your tone is authoritative, precise, and actionable."
    )
    user_prompt = (
        "Analyze the following bias audit results and produce a structured report.\n\n"
        "=== DATASET CONTEXT ===\n"
        f"{dataset_summary}\n\n"
        "=== ML FAIRNESS ANALYSIS ===\n"
        f"{ml_summary}\n\n"
        "Return ONLY this exact JSON schema (no extra fields, no markdown):\n"
        "{\n"
        '  "severity_label": "HIGH | MEDIUM | LOW",\n'
        '  "severity_color": "red | amber | green",\n'
        '  "headline": "One punchy sentence (max 20 words) describing the core bias finding",\n'
        '  "metrics_summary": "2 sentences max. Mention DIR, SPD, Bias Score. Bold key terms with **.",\n'
        '  "root_cause": {\n'
        '    "primary_driver": "Human-readable feature name (NOT raw column name)",\n'
        '    "explanation": "2-3 sentences explaining WHY this feature causes disparity."\n'
        "  },\n"
        '  "group_comparison": {\n'
        '    "most_advantaged": "group name",\n'
        '    "least_advantaged": "group name",\n'
        '    "disparity_ratio": "e.g. 2.3x",\n'
        '    "plain_english": "1 sentence impact statement for least advantaged group"\n'
        "  },\n"
        '  "recommended_actions": [\n'
        '    {"priority": "IMMEDIATE", "action": "Specific action sentence"},\n'
        '    {"priority": "SHORT_TERM", "action": "Specific action sentence"},\n'
        '    {"priority": "LONG_TERM", "action": "Specific action sentence"}\n'
        "  ],\n"
        '  "compliance_flags": ["One-line compliance concern"],\n'
        '  "confidence": "HIGH | MEDIUM | LOW",\n'
        '  "confidence_reason": "One sentence confidence rationale"\n'
        "}"
    )

    # Try configured model first, then fall back to broadly available models.
    model_candidates = []
    for model in [
        gemini_model,
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-2.0-flash-lite",
    ]:
        if model and model not in model_candidates:
            model_candidates.append(model)

    ai_text = ""
    selected_model = model_candidates[0]
    last_http_error: urllib.error.HTTPError | None = None
    last_reason = ""
    saw_rate_limit = False

    for candidate_model in model_candidates:
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{candidate_model}:generateContent?key={urllib.parse.quote(gemini_api_key)}"
        )
        request_body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json",
            },
        }

        for attempt in range(2):
            req = urllib.request.Request(
                endpoint,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                },
                data=json.dumps(request_body).encode("utf-8"),
            )

            try:
                with urllib.request.urlopen(req) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    ai_text = (
                        resp_data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    if ai_text:
                        selected_model = candidate_model
                        break
                    last_reason = "Gemini response was empty."
            except urllib.error.HTTPError as exc:
                last_http_error = exc
                if exc.code == 401:
                    return jsonify({"error": "Invalid Gemini API key."}), 401
                if exc.code == 403:
                    try:
                        err_msg = exc.read().decode("utf-8")
                    except Exception:
                        err_msg = exc.reason
                    return jsonify({"error": f"Gemini API Error: 403 - Forbidden ({err_msg})"}), 403
                if exc.code == 429:
                    saw_rate_limit = True
                    last_reason = "Rate limit exceeded on Gemini API."
                    if attempt == 0:
                        time.sleep(1.5)
                        continue
                else:
                    last_reason = str(exc.reason)
            except Exception as exc:
                last_reason = str(exc)

            break

        if ai_text:
            break

    if not ai_text and saw_rate_limit:
        fallback_report = _build_fallback_ai_report(analysis_data, row_count)
        fallback_report["_source"] = "deterministic-fallback"
        fallback_report["_warning"] = "Gemini API is currently rate-limited."
        fallback_report["_row_count"] = row_count
        fallback_report["_columns"] = [humanize_column(col) for col in columns]
        return jsonify(clean_for_json(fallback_report))

    if not ai_text:
        if last_http_error is not None:
            return (
                jsonify(
                    {
                        "error": f"Gemini API Error: {last_http_error.code} - {last_http_error.reason}. "
                        f"Tried models: {', '.join(model_candidates)}"
                    }
                ),
                500,
            )
        return jsonify({"error": f"Gemini request failed: {last_reason or 'unknown error'}"}), 500

    try:
        ai_report = json.loads(ai_text)
    except Exception:
        ai_report = {}

    normalized_report = _normalize_ai_report(ai_report, analysis_data, row_count)
    normalized_report["_source"] = selected_model
    normalized_report["_row_count"] = row_count
    normalized_report["_columns"] = [humanize_column(col) for col in columns]
    return jsonify(clean_for_json(normalized_report))


@api_bp.post("/reset")
def reset():
    try:
        files_deleted = 0
        for filename in os.listdir(TEMP_DATASETS):
            file_path = TEMP_DATASETS / filename
            try:
                if file_path.is_file() or file_path.is_symlink():
                    file_path.unlink()
                    files_deleted += 1
                elif file_path.is_dir():
                    shutil.rmtree(file_path)
                    files_deleted += 1
            except Exception as exc:
                print(f"Failed to delete {file_path}. Reason: {exc}")

        return jsonify(
            {
                "message": f"Reset successful. Deleted {files_deleted} temporary datasets.",
                "status": "success",
            }
        )
    except Exception as exc:
        return jsonify({"error": f"Reset failed: {str(exc)}"}), 500
