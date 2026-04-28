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


def _build_fallback_ai_report(analysis_data: dict[str, Any], row_count: int, columns: list[str]) -> str:
    severity = str(analysis_data.get("severity", "UNKNOWN"))
    dir_value = analysis_data.get("DIR", analysis_data.get("metrics", {}).get("DIR", 0))
    spd_value = analysis_data.get("difference", analysis_data.get("metrics", {}).get("SPD", 0))
    bias_score = analysis_data.get("bias_score", 0)
    most_advantaged = analysis_data.get("most_advantaged_group", "N/A")
    least_advantaged = analysis_data.get("least_advantaged_group", "N/A")
    top_feature = analysis_data.get("most_influential_feature", "N/A")
    recommendations = analysis_data.get("recommendations", [])[:3]

    recommendation_lines = "\n".join(
        f"> - {item}" for item in recommendations if isinstance(item, str) and item.strip()
    )
    if not recommendation_lines:
        recommendation_lines = "> - Re-run AI report later when provider quota resets."

    return (
        "### Final Bias Report\n"
        f"**Quota fallback mode** was used because the external AI provider is currently rate-limited. "
        f"This report is generated from deterministic fairness outputs and dataset metadata (**{row_count} rows**, "
        f"**{len(columns)} columns**) so analysis remains available.\n\n"
        f"The current run indicates **{severity}** bias with **DIR={dir_value}**, **SPD={spd_value}**, "
        f"and **Bias Score={bias_score}**. The most advantaged group is **{most_advantaged}**, while the least "
        f"advantaged group is **{least_advantaged}**.\n\n"
        "### Root Causes & Insights\n"
        f"The strongest disparity signal is tied to **{top_feature}** based on feature-impact ranking in your last audit. "
        "Review this driver first along with subgroup-level hotspots and qualification context before model release.\n\n"
        "### Recommended Action\n"
        f"{recommendation_lines}"
    )


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

    summary_lines = []
    summary_lines.append(f"Row count: {row_count}")
    summary_lines.append("Columns and Unique Counts:")
    for col in columns:
        unique_count = int(df[col].nunique())
        top_vals = df[col].value_counts().head(3).index.tolist()
        summary_lines.append(f" - {col}: {unique_count} unique (top: {top_vals})")

    summary_lines.append("\nSample Data:")
    sample_df = df.head(80)
    summary_lines.append(sample_df.to_csv(index=False))

    dataset_summary = "\n".join(summary_lines)
    if len(dataset_summary) > 4000:
        dataset_summary = dataset_summary[:4000] + "\n...[TRUNCATED]"

    ml_summary = json.dumps(analysis_data, indent=2)
    if len(ml_summary) > 4000:
        ml_summary = ml_summary[:4000] + "\n...[TRUNCATED]"

    prompt = (
        "You are an expert AI bias detector and data scientist. You have been provided with two contexts:\n"
        "1. A structural summary and sample rows of the dataset.\n"
        "2. The deterministic Machine Learning Fairness Analysis output (including Disparate Impact Ratio, Bias Scores, Hotspots, and Feature Impacts) calculated by our backend engine.\n\n"
        "Your task is to synthesize our mathematical engine's findings with your own data insights to produce a unified, concise 'Final Bias Report' for the user.\n"
        "The report must be short-form but highly informative (strictly 3 to 4 concise paragraphs). Do not generate a massive wall of text.\n"
        "It must seamlessly blend the hard metrics (like DIR, SPD, and bias score) with plain-English context about the dataset features.\n"
        "Format the output using Markdown. Use **bolding** heavily for key terms, metric names, feature names, and specific group names to make it scannable.\n"
        "Format the output using these concise sections:\n"
        "### Final Bias Report\n"
        "### Root Causes & Insights\n"
        "### Recommended Action\n"
        "> **Note:** For the Recommended Action section, present the actions as a markdown blockquote (using `>`) with bullet points so it stands out visually.\n\n"
        "=== DATASET CONTEXT ===\n"
        f"{dataset_summary}\n\n"
        "=== ML FAIRNESS ANALYSIS ===\n"
        f"{ml_summary}\n"
    )

    # Try configured model first, then fall back to broadly available models.
    model_candidates = []
    for model in [gemini_model, "gemini-2.0-flash", "gemini-2.0-flash-lite"]:
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
        req = urllib.request.Request(
            endpoint,
            method="POST",
            headers={
                "Content-Type": "application/json",
            },
            data=json.dumps(
                {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.35,
                        "maxOutputTokens": 1024,
                    },
                }
            ).encode("utf-8"),
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
                continue
            last_reason = str(exc.reason)
            continue
        except Exception as exc:
            last_reason = str(exc)
            continue

    if not ai_text and saw_rate_limit:
        fallback_text = _build_fallback_ai_report(analysis_data, row_count, columns)
        return jsonify(
            {
                "model": "deterministic-fallback",
                "row_count": row_count,
                "columns": columns,
                "ai_response": fallback_text,
                "warning": "Gemini API is currently rate-limited. Showing fallback report.",
            }
        )

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

    return jsonify(
        {
            "model": selected_model,
            "row_count": row_count,
            "columns": columns,
            "ai_response": ai_text,
        }
    )


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
