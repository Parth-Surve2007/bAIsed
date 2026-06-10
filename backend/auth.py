from __future__ import annotations

from functools import wraps
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

try:
    from .fb_admin import auth_client, db
except ImportError:  # pragma: no cover - direct script fallback
    auth_client = None
    db = None


auth_bp = Blueprint("auth", __name__)


def _not_ready(message: str, status: int = 501):
    return jsonify({"error": message, "status": "not_ready"}), status


def _public_user(decoded: dict) -> dict:
    return {
        "uid": decoded.get("uid"),
        "email": decoded.get("email"),
        "email_verified": bool(decoded.get("email_verified")),
        "name": decoded.get("name"),
        "picture": decoded.get("picture"),
        "provider": decoded.get("firebase", {}).get("sign_in_provider"),
    }


def _profile_ref(uid: str):
    return db.collection("profiles").document(uid)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _profile_from_snapshot(snapshot, fallback_user: dict) -> dict:
    data = snapshot.to_dict() if snapshot.exists else {}
    data = data or {}
    return {
        "uid": fallback_user.get("uid"),
        "email": data.get("email") or fallback_user.get("email"),
        "display_name": data.get("display_name") or fallback_user.get("name"),
        "photo_url": data.get("photo_url") or fallback_user.get("picture"),
        "organization": data.get("organization", ""),
        "role": data.get("role", ""),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "last_login_at": data.get("last_login_at"),
    }


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
@verify_token
def verify():
    return jsonify({"status": "ok", "user": _public_user(g.firebase_user)})


@auth_bp.get("/profile")
@verify_token
def get_profile():
    if db is None:
        return _not_ready("Firestore is not initialized.", 503)
    user = _public_user(g.firebase_user)
    snapshot = _profile_ref(user["uid"]).get()
    return jsonify({"status": "ok", "profile": _profile_from_snapshot(snapshot, user)})


@auth_bp.post("/profile")
@verify_token
def upsert_profile():
    if db is None:
        return _not_ready("Firestore is not initialized.", 503)
    user = _public_user(g.firebase_user)
    payload = request.get_json(silent=True) or {}
    now = _utc_now_iso()

    profile = {
        "email": payload.get("email") or user.get("email"),
        "display_name": payload.get("display_name") or payload.get("name") or user.get("name"),
        "photo_url": payload.get("photo_url") or user.get("picture"),
        "organization": payload.get("organization", ""),
        "role": payload.get("role", ""),
        "last_login_at": now,
        "updated_at": now,
    }
    profile = {key: value for key, value in profile.items() if value is not None}

    ref = _profile_ref(user["uid"])
    snapshot = ref.get()
    if not snapshot.exists:
        profile["created_at"] = now

    ref.set(profile, merge=True)
    return jsonify({"status": "ok", "profile": _profile_from_snapshot(ref.get(), user)})
