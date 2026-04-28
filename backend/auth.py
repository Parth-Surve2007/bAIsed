from __future__ import annotations

from functools import wraps

from flask import Blueprint, g, jsonify, request

try:
    from .fb_admin import auth_client, db
except ImportError:  # pragma: no cover - direct script fallback
    auth_client = None
    db = None


auth_bp = Blueprint("auth", __name__)


def _not_ready(message: str, status: int = 501):
    return jsonify({"error": message, "status": "not_ready"}), status


def verify_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"error": "Missing bearer token."}), 401

        token = header.split(" ", 1)[1].strip()
        if not token:
            return jsonify({"error": "Missing bearer token."}), 401

        if auth_client is None:
            return _not_ready("Firebase Admin SDK is not initialized.", 503)

        try:
            decoded = auth_client.verify_id_token(token)
        except Exception as exc:  # pragma: no cover - depends on external credentials
            return jsonify({"error": f"Invalid token: {exc}"}), 401

        g.firebase_user = decoded
        return f(*args, **kwargs)

    return decorated


@auth_bp.route("/verify", methods=["OPTIONS"])
@auth_bp.route("/profile", methods=["OPTIONS"])
def auth_preflight():
    return ("", 204)


@auth_bp.post("/verify")
def verify():
    return _not_ready("Token verification scaffolded. Full Firebase auth wiring is pending.")


@auth_bp.get("/profile")
@verify_token
def get_profile():
    if db is None:
        return _not_ready("Firestore is not initialized.", 503)
    return _not_ready("Profile retrieval scaffolded. Firestore profile reads are pending.")


@auth_bp.post("/profile")
@verify_token
def upsert_profile():
    if db is None:
        return _not_ready("Firestore is not initialized.", 503)
    return _not_ready("Profile upsert scaffolded. Firestore profile writes are pending.")
