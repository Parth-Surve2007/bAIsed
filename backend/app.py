from __future__ import annotations

from io import BytesIO
from json import JSONEncoder
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_file, send_from_directory
import json
import math
import numpy as np
import pandas as pd

from analysis import AnalysisError, analyze_dataset, analyze_simple_input, detect_columns, load_dataset
from simulator import simulate_fairness_scenario
from preprocessor import standardize_dataset
import uuid
import os
import shutil


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
    elif isinstance(obj, (list, tuple)):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, (np.floating, np.integer)):
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
                "href": "/app/documentation#introduction",
                "summary": "Overview of the fairness auditing framework and lifecycle coverage.",
            },
            {
                "title": "Quick Start",
                "href": "/app/documentation#quick-start",
                "summary": "Install the CLI and bootstrap an audit project.",
            },
            {
                "title": "Architecture Overview",
                "href": "/app/documentation#metrics-engine",
                "summary": "Understand the metrics engine, DIR, and explainability model.",
            },
            {
                "title": "API Reference",
                "href": "/app/documentation#api-reference",
                "summary": "Authentication, endpoints, and operational limits.",
            },
        ],
    },
    "about": {
        "mission": "Algorithmic transparency for a fair future.",
        "tagline": "Detect Bias. Ensure Fairness. Automate Integrity.",
    },
}

VALID_LOGIN = {
    "demo@baised.ai": "demo123",
    "analyst@baised.ai": "workbench",
}

DEMO_REQUESTS: list[dict[str, Any]] = []


def _json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


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
        return {"target": "/app/workbench", "message": "Opening the live fairness workbench."}
    if action in pricing_actions:
        return {"target": "/app/pricing_demo", "message": "Routing you to the demo request workspace."}
    if action in docs_actions:
        if action == "download whitepaper":
            return {"target": "/api/downloads/whitepaper", "message": "Preparing the whitepaper download."}
        return {"target": "/app/documentation", "message": "Opening the documentation hub."}
    if action in login_actions:
        return {"target": "/app/login", "message": "Opening secure sign-in."}
    if action in case_actions:
        return {"target": "/app/case_study", "message": "Opening the impact report."}

    return {"target": f"/app/{page}" if page else "/app", "message": "Action resolved."}


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


def create_app() -> Flask:
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    app = Flask(__name__, static_folder=str(frontend_dir), static_url_path="/frontend")
    
    # Global safety for NaN values in JSON
    app.json_encoder = NaNSafeEncoder
    
    app.config['TEMP_DATASETS'] = os.path.join(os.path.dirname(__file__), "temp_datasets")
    os.makedirs(app.config['TEMP_DATASETS'], exist_ok=True)

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response

    @app.route("/analyze", methods=["OPTIONS"])
    @app.route("/ai-analyze", methods=["OPTIONS"])
    @app.route("/upload", methods=["OPTIONS"])
    @app.route("/simulate", methods=["OPTIONS"])
    @app.route("/api/auth/login", methods=["OPTIONS"])
    @app.route("/api/demo-request", methods=["OPTIONS"])
    @app.route("/api/actions/resolve", methods=["OPTIONS"])
    def preflight():
        return ("", 204)

    @app.get("/")
    def health_check():
        return jsonify({"message": "bAIsed API running"})

    @app.get("/api/site-content/<page_name>")
    def site_content(page_name: str):
        page = SITE_CONTENT.get(page_name)
        if page is None:
            return _json_error("Unknown page.", 404)
        return jsonify(page)

    @app.get("/api/search")
    def search():
        query = request.args.get("query", "")
        results = _search_docs(query)
        return jsonify({"query": query, "count": len(results), "results": results})

    @app.post("/api/actions/resolve")
    def resolve_action():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _json_error("Request body must be valid JSON.")

        action = _normalize_action(str(payload.get("action", "")))
        page = str(payload.get("page", "")).strip()
        if not action:
            return _json_error("An action is required.")

        return jsonify(_resolve_action_payload(action, page))

    @app.post("/api/auth/login")
    def login():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _json_error("Request body must be valid JSON.")

        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        if not email or not password:
            return _json_error("Email and password are required.")

        if VALID_LOGIN.get(email) != password:
            return _json_error("Invalid credentials. Try demo@baised.ai / demo123.", 401)

        return jsonify(
            {
                "message": "Authentication successful.",
                "email": email,
                "redirect": "/app/workbench",
                "token": f"demo-session:{email}",
            }
        )

    @app.post("/api/demo-request")
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
                "redirect": "/app/workbench",
            }
        )

    @app.get("/api/downloads/whitepaper")
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

    @app.get("/app")
    def frontend_home():
        return send_from_directory(frontend_dir, "landing_page.html")

    @app.get("/app/<path:page_name>")
    def frontend_page(page_name: str):
        safe_name = Path(page_name).name
        if not safe_name.endswith(".html"):
            safe_name = f"{safe_name}.html"
        return send_from_directory(frontend_dir, safe_name)

    @app.post("/analyze")
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

    @app.post("/scan")
    def scan():
        file = request.files.get("file")
        if file is None:
            return jsonify({"error": "A file upload is required."}), 400
        
        try:
            df = load_dataset(file)
            df, preprocessor_report = standardize_dataset(df)
            
            # Save standardized dataset to a temporary file
            dataset_id = str(uuid.uuid4())
            temp_path = os.path.join(app.config['TEMP_DATASETS'], f"{dataset_id}.csv")
            df.to_csv(temp_path, index=False)
            
            from analysis import _profile_columns
            profile = _profile_columns(df)
            return jsonify(clean_for_json({
                "dataset_id": dataset_id,
                "columns": list(df.columns),
                "profile": profile,
                "row_count": int(len(df)),
                "preprocessor_report": preprocessor_report
            }))
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    @app.post("/upload")
    def upload():
        dataset_id = request.form.get("dataset_id")
        protected_attribute = request.form.get("protected_attribute")
        outcome_column = request.form.get("outcome_column")
        qualification_column = request.form.get("qualification_column")

        try:
            if dataset_id:
                # Use the pre-processed temporary dataset
                temp_path = os.path.join(app.config['TEMP_DATASETS'], f"{dataset_id}.csv")
                if not os.path.exists(temp_path):
                    return jsonify({"error": "Dataset session expired. Please re-upload."}), 400
                df = pd.read_csv(temp_path)
                preprocessor_report = {"status": "Loaded from standardized workspace"}
            else:
                # Fallback to on-the-fly processing if no ID
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
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return jsonify({"error": f"Analysis failed: {str(e)}"}), 500

        response = result.to_dict()
        response["mode"] = "dataset"
        response["protected_attribute"] = resolved_protected
        response["protected_attributes"] = result.stats.get("protected_attributes", [resolved_protected])
        response["derived_protected"] = result.stats.get("derived_protected")
        response["outcome_column"] = resolved_outcome
        response["derived_outcome"] = result.stats.get("derived_outcome")
        response["qualification_column"] = result.stats.get("qualification_column")
        response["row_count"] = int(len(df))
        
        # Get filename safely - file may not exist when using dataset_id
        file_obj = request.files.get("file")
        response["file_name"] = file_obj.filename if file_obj else f"dataset_{dataset_id}.csv"
        
        response["preprocessor_report"] = preprocessor_report
        return jsonify(clean_for_json(response))

    @app.post("/simulate")
    def simulate():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "Request body must be valid JSON."}), 400

        try:
            response = simulate_fairness_scenario(payload)
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        return jsonify(clean_for_json(response))

    @app.post("/ai-analyze")
    def ai_analyze():
        import urllib.request
        import urllib.error

        file = request.files.get("file")
        if file is None:
            return jsonify({"error": "A file upload is required."}), 400

        analysis_json = request.form.get("analysis_json", "{}")
        try:
            analysis_data = json.loads(analysis_json)
        except:
            analysis_data = {}

        groq_api_key = "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"

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

        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            method="POST",
            headers={
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            },
            data=json.dumps({
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}]
            }).encode("utf-8")
        )

        try:
            with urllib.request.urlopen(req) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                ai_text = resp_data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return jsonify({"error": "Invalid Groq API Key."}), 401
            elif e.code == 403:
                # specifically catching 403 to return text and debug
                try:
                    err_msg = e.read().decode("utf-8")
                except:
                    err_msg = e.reason
                return jsonify({"error": f"Groq API Error: 403 - Forbidden ({err_msg})"}), 403
            elif e.code == 429:
                return jsonify({"error": "Rate limit exceeded on Groq API."}), 429
            else:
                return jsonify({"error": f"Groq API Error: {e.code} - {e.reason}"}), 500
        except Exception as e:
            return jsonify({"error": f"Request failed: {str(e)}"}), 500

        return jsonify({
            "model": "llama-3.3-70b-versatile",
            "row_count": row_count,
            "columns": columns,
            "ai_response": ai_text
        })

    @app.post("/reset")
    def reset():
        temp_dir = app.config['TEMP_DATASETS']
        try:
            files_deleted = 0
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                        files_deleted += 1
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        files_deleted += 1
                except Exception as e:
                    print(f"Failed to delete {file_path}. Reason: {e}")
            
            return jsonify({
                "message": f"Reset successful. Deleted {files_deleted} temporary datasets.",
                "status": "success"
            })
        except Exception as e:
            return jsonify({"error": f"Reset failed: {str(e)}"}), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
