"""
backend/llm/process1.py

Process 1 — Audit Report Generator.

One-shot call: receives computed bias metrics and dataset metadata,
returns a structured narrative report as a plain string.

This file reads PROCESS1_API_KEY and PROCESS1_MODEL exclusively.
It never touches PROCESS2_API_KEY or any Process 2 configuration.
"""

import logging

from google import genai

try:
    from backend.config import PROCESS1_API_KEY, PROCESS1_MODEL
except ImportError:
    from config import PROCESS1_API_KEY, PROCESS1_MODEL

logger = logging.getLogger(__name__)


def _get_client():
    """
    Returns a genai.Client configured with the Process 1 API key.
    Called once per request to ensure isolation.
    """
    if not PROCESS1_API_KEY:
        raise ValueError(
            "PROCESS1_API_KEY is not configured. "
            "Set it in your .env file to enable audit report generation."
        )
    if not PROCESS1_MODEL:
        raise ValueError(
            "PROCESS1_MODEL is not configured. "
            "Set it in your .env file (recommended: gemini-2.5-flash)."
        )
    return genai.Client(api_key=PROCESS1_API_KEY)


def _build_prompt(metrics: dict, dataset_meta: dict) -> str:
    return f"""You are a fairness auditing expert. Generate a structured audit report based on the \
following bias analysis results.

Dataset: {dataset_meta.get('name', 'Unknown')}
Protected attribute: {dataset_meta.get('protected_attr', 'Unknown')}
Outcome variable: {dataset_meta.get('outcome', 'Unknown')}

Metrics:
- Disparate Impact Ratio (DIR): {metrics.get('dir')}
- Statistical Parity Difference (SPD): {metrics.get('spd')}
- Equal Opportunity Difference (EOD): {metrics.get('eod')}
- Average Odds Difference (AOD): {metrics.get('aod')}
- Overall Bias Score (0-100): {metrics.get('bias_score')}
- Bias patterns detected: {metrics.get('patterns', [])}
- Proxy variables identified: {metrics.get('proxies', [])}

Write a report with sections: Executive Summary, Key Findings, Risk Assessment, \
and Recommended Remediation Steps. Use plain English suitable for a compliance officer."""


def generate_report(metrics: dict, dataset_meta: dict) -> str:
    """
    Makes a single, one-shot call and returns the full report text as a string.
    Raises ValueError if PROCESS1_API_KEY or PROCESS1_MODEL are not set.
    """
    client = _get_client()
    prompt = _build_prompt(metrics, dataset_meta)
    logger.info("[Process 1] Generating audit report for dataset: %s", dataset_meta.get("name"))
    response = client.models.generate_content(
        model=PROCESS1_MODEL,
        contents=prompt,
    )
    return response.text
