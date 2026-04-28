from __future__ import annotations

import os
from pathlib import Path

import firebase_admin as firebase_admin_sdk
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, firestore


BASE_DIR = Path(__file__).resolve().parent.parent
SERVICE_ACCOUNT_PATH = BASE_DIR / os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "serviceAccountKey.json")

firebase_app = None
auth_client = None
db = None

if SERVICE_ACCOUNT_PATH.exists():
    try:  # pragma: no cover - depends on local credentials
        firebase_app = firebase_admin_sdk.get_app()
    except ValueError:
        firebase_app = firebase_admin_sdk.initialize_app(credentials.Certificate(str(SERVICE_ACCOUNT_PATH)))

    auth_client = firebase_auth
    db = firestore.client()
