from __future__ import annotations

from pathlib import Path

from flask import Flask, send_from_directory

try:
    from .api import api_bp
    from .auth import auth_bp
except ImportError:  # pragma: no cover - direct script fallback
    from api import api_bp
    from auth import auth_bp


def create_app() -> Flask:
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    pages_dir = frontend_dir / "pages"

    app = Flask(__name__, static_folder=str(frontend_dir), static_url_path="/frontend")
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response

    @app.get("/")
    def landing_page():
        return send_from_directory(pages_dir, "landing.html")

    @app.get("/solutions")
    def solutions_page():
        return send_from_directory(pages_dir, "solutions.html")

    @app.get("/methodology")
    def methodology_page():
        return send_from_directory(pages_dir, "methodology.html")

    @app.get("/about")
    def about_page():
        return send_from_directory(pages_dir, "about.html")

    @app.get("/case-study")
    def case_study_page():
        return send_from_directory(pages_dir, "case_study.html")

    @app.get("/pricing")
    def pricing_page():
        return send_from_directory(pages_dir, "pricing.html")

    @app.get("/login")
    def login_page():
        return send_from_directory(pages_dir, "login.html")

    @app.get("/signup")
    def signup_page():
        return send_from_directory(pages_dir, "signup.html")

    @app.get("/workbench")
    def workbench_page():
        return send_from_directory(pages_dir, "workbench.html")

    @app.get("/dashboard")
    def dashboard_page():
        return send_from_directory(pages_dir, "dashboard.html")

    @app.errorhandler(404)
    def not_found(_error):
        return send_from_directory(pages_dir, "404.html"), 404

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
