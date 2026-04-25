from __future__ import annotations

from io import BytesIO
from json import JSONEncoder
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_file, send_from_directory
import json
import math
import numpy as np

from analysis import AnalysisError, analyze_dataset, analyze_simple_input, detect_columns, load_dataset
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
    elif isinstance(obj, (list, tuple)):
        return [clean_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, (np.floating, np.integer)):
        return float(obj) if isinstance(obj, np.floating) else int(obj)
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

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response

    @app.route("/analyze", methods=["OPTIONS"])
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

    @app.post("/upload")
    def upload():
        file = request.files.get("file")
        if file is None:
            return jsonify({"error": "A file upload is required."}), 400

        protected_attribute = request.form.get("protected_attribute")
        outcome_column = request.form.get("outcome_column")
        qualification_column = request.form.get("qualification_column")

        try:
            df = load_dataset(file)
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

        response = result.to_dict()
        response["mode"] = "dataset"
        response["protected_attribute"] = resolved_protected
        response["protected_attributes"] = result.stats.get("protected_attributes", [resolved_protected])
        response["derived_protected"] = result.stats.get("derived_protected")
        response["outcome_column"] = resolved_outcome
        response["derived_outcome"] = result.stats.get("derived_outcome")
        response["qualification_column"] = result.stats.get("qualification_column")
        response["row_count"] = int(len(df))
        response["file_name"] = file.filename
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

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
