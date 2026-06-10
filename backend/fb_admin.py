from __future__ import annotations

import os
import json
from pathlib import Path

import firebase_admin as firebase_admin_sdk
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, firestore


BACKEND_DIR = Path(__file__).resolve().parent
SERVICE_ACCOUNT_PATH = Path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", BACKEND_DIR / "serviceAccountKey.json"))
SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()

firebase_app = None
auth_client = None
db = None

credential = None

if SERVICE_ACCOUNT_JSON:
    try:
        credential = credentials.Certificate(json.loads(SERVICE_ACCOUNT_JSON))
    except (json.JSONDecodeError, ValueError):
        credential = None
elif SERVICE_ACCOUNT_PATH.exists():
    credential = credentials.Certificate(str(SERVICE_ACCOUNT_PATH))

if credential is not None:
    try:  # pragma: no cover - depends on local credentials
        firebase_app = firebase_admin_sdk.get_app()
    except ValueError:
        firebase_app = firebase_admin_sdk.initialize_app(credential)

    auth_client = firebase_auth
    db = firestore.client()
