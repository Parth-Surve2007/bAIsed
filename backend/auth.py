from __future__ import annotations

from functools import wraps
from datetime import datetime, timezone
from uuid import uuid4

from flask import Blueprint, g, jsonify, request

try:
    from .fb_admin import auth_client, db, init_error
except ImportError:  # pragma: no cover - direct script fallback
    try:
        from fb_admin import auth_client, db, init_error
    except ImportError as exc:
        try:
            from backend.fb_admin import auth_client, db, init_error
        except ImportError as final_exc:
            auth_client = None
            db = None
            init_error = f"Unable to import Firebase Admin helper: {final_exc or exc}"


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
            detail = f"Firebase Admin SDK is not initialized. {init_error}" if init_error else "Firebase Admin SDK is not initialized."
            return _not_ready(detail, 503)

        try:
            decoded = auth_client.verify_id_token(token)
        except Exception as exc:  # pragma: no cover - depends on external credentials
            import logging
            logging.getLogger("backend.auth").warning(f"Auth token verification failed: {exc}")
            return jsonify({"error": "Session issue — please refresh the page"}), 401

        g.firebase_user = decoded
        return f(*args, **kwargs)

    return decorated


@auth_bp.route("/verify", methods=["OPTIONS"])
@auth_bp.route("/profile", methods=["OPTIONS"])
@auth_bp.route("/sessions", methods=["OPTIONS"])
@auth_bp.route("/sessions/<session_id>", methods=["OPTIONS"])
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


def _sessions_ref(uid: str):
    return _profile_ref(uid).collection("workbench_sessions")


def _clean_session_payload(payload: dict) -> dict:
    allowed = {
        "title",
        "audit_mode",
        "summary",
        "explanation",
        "audit_result",
        "ai_chat",
        "ai_report_markdown",
        "ai_report_source",
        "dataset_meta",
        "model_meta",
        "workspace_state",
    }
    cleaned = {key: payload.get(key) for key in allowed if key in payload}
    title = str(cleaned.get("title") or "Untitled audit").strip()[:120]
    cleaned["title"] = title or "Untitled audit"

    chat = cleaned.get("ai_chat")
    if isinstance(chat, list):
        cleaned["ai_chat"] = [
            {
                "role": str(item.get("role", ""))[:20],
                "content": str(item.get("content", ""))[:8000],
            }
            for item in chat[:80]
            if isinstance(item, dict)
        ]

    report = cleaned.get("ai_report_markdown")
    if report is not None:
        cleaned["ai_report_markdown"] = str(report)[:60000]

    cleaned["privacy_mode_saved"] = bool(payload.get("privacy_mode_saved", False))
    return cleaned


def _session_from_snapshot(snapshot) -> dict:
    data = snapshot.to_dict() or {}
    data["id"] = snapshot.id
    return data


@auth_bp.get("/sessions")
@verify_token
def list_sessions():
    if db is None:
        return _not_ready("Firestore is not initialized.", 503)
    user = _public_user(g.firebase_user)
    query = (
        _sessions_ref(user["uid"])
        .order_by("updated_at", direction="DESCENDING")
        .limit(30)
    )
    sessions = [_session_from_snapshot(snapshot) for snapshot in query.stream()]
    return jsonify({"status": "ok", "sessions": sessions})


@auth_bp.post("/sessions")
@verify_token
def create_session():
    if db is None:
        return _not_ready("Firestore is not initialized.", 503)
    user = _public_user(g.firebase_user)
    payload = request.get_json(silent=True) or {}
    now = _utc_now_iso()
    session_id = str(payload.get("id") or uuid4())
    data = _clean_session_payload(payload)
    data.update(
        {
            "created_at": now,
            "updated_at": now,
            "owner_uid": user["uid"],
        }
    )
    ref = _sessions_ref(user["uid"]).document(session_id)
    ref.set(data)
    return jsonify({"status": "ok", "session": _session_from_snapshot(ref.get())})


@auth_bp.get("/sessions/<session_id>")
@verify_token
def get_session(session_id: str):
    if db is None:
        return _not_ready("Firestore is not initialized.", 503)
    user = _public_user(g.firebase_user)
    snapshot = _sessions_ref(user["uid"]).document(session_id).get()
    if not snapshot.exists:
        return jsonify({"error": "Session not found."}), 404
    return jsonify({"status": "ok", "session": _session_from_snapshot(snapshot)})


@auth_bp.put("/sessions/<session_id>")
@verify_token
def update_session(session_id: str):
    if db is None:
        return _not_ready("Firestore is not initialized.", 503)
    user = _public_user(g.firebase_user)
    payload = request.get_json(silent=True) or {}
    ref = _sessions_ref(user["uid"]).document(session_id)
    if not ref.get().exists:
        return jsonify({"error": "Session not found."}), 404
    data = _clean_session_payload(payload)
    data["updated_at"] = _utc_now_iso()
    ref.set(data, merge=True)
    return jsonify({"status": "ok", "session": _session_from_snapshot(ref.get())})


@auth_bp.delete("/sessions/<session_id>")
@verify_token
def delete_session(session_id: str):
    if db is None:
        return _not_ready("Firestore is not initialized.", 503)
    user = _public_user(g.firebase_user)
    _sessions_ref(user["uid"]).document(session_id).delete()
    return jsonify({"status": "ok"})
