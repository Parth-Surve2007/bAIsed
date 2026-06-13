import logging
import os

from pathlib import Path
from dotenv import load_dotenv

_ROOT_ENV = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ROOT_ENV, override=True)

logger = logging.getLogger(__name__)

# ── Process 1: Audit Report ────────────────────────────────────────────────────
PROCESS1_API_KEY = os.getenv("PROCESS1_API_KEY")
PROCESS1_MODEL   = os.getenv("PROCESS1_MODEL")

# ── Process 2: Conversational Explainer ───────────────────────────────────────
PROCESS2_API_KEY = os.getenv("PROCESS2_API_KEY")
PROCESS2_MODEL   = os.getenv("PROCESS2_MODEL")

# ── Feature flags ──────────────────────────────────────────────────────────────
ENABLE_AUDIT_REPORT   = os.getenv("ENABLE_AUDIT_REPORT",   "true").lower() == "true"
ENABLE_EXPLAINER_CHAT = os.getenv("ENABLE_EXPLAINER_CHAT", "true").lower() == "true"

# ── Startup warnings ───────────────────────────────────────────────────────────
if not PROCESS1_API_KEY:
    logger.warning(
        "[Process 1 — Audit Report] PROCESS1_API_KEY is not set. "
        "The audit report feature will be disabled until this is configured."
    )

if not PROCESS2_API_KEY:
    logger.warning(
        "[Process 2 — Explainer Chat] PROCESS2_API_KEY is not set. "
        "The conversational explainer feature will be disabled until this is configured."
    )
