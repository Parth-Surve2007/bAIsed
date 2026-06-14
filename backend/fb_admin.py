from __future__ import annotations

import os
import json
from pathlib import Path

import firebase_admin as firebase_admin_sdk
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, firestore


BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
SERVICE_ACCOUNT_PATH_VALUE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
if SERVICE_ACCOUNT_PATH_VALUE:
    configured_path = Path(SERVICE_ACCOUNT_PATH_VALUE)
    SERVICE_ACCOUNT_PATH = configured_path if configured_path.is_absolute() else PROJECT_DIR / configured_path
else:
    SERVICE_ACCOUNT_PATH = BACKEND_DIR / "serviceAccountKey.json"
SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()

firebase_app = None
auth_client = None
db = None
init_error = None

credential = None

if SERVICE_ACCOUNT_JSON:
    try:
        credential = credentials.Certificate(json.loads(SERVICE_ACCOUNT_JSON))
    except (json.JSONDecodeError, ValueError) as exc:
        init_error = f"Invalid FIREBASE_SERVICE_ACCOUNT_JSON: {exc}"
        credential = None
elif SERVICE_ACCOUNT_PATH.exists():
    try:
        credential = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))
    except ValueError as exc:
        init_error = f"Invalid Firebase service account file at {SERVICE_ACCOUNT_PATH}: {exc}"
else:
    init_error = f"Firebase service account file not found at {SERVICE_ACCOUNT_PATH}"

if credential is not None:
    try:  # pragma: no cover - depends on local credentials
        firebase_app = firebase_admin_sdk.get_app()
    except ValueError:
        firebase_app = firebase_admin_sdk.initialize_app(credential)

    auth_client = firebase_auth
    try:
        db = firestore.client()
    except Exception as exc:  # pragma: no cover - depends on external credentials
        init_error = f"Firestore client initialization failed: {exc}"
