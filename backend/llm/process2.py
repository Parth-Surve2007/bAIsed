"""
backend/llm/process2.py

Process 2 — Conversational Explainer Chat.

Multi-turn streaming generator: receives the full conversation history plus
the current audit metrics, yields text chunks as the model responds.

This file reads PROCESS2_API_KEY and PROCESS2_MODEL exclusively.
It never touches PROCESS1_API_KEY or any Process 1 configuration.
"""

import logging

from google import genai
from google.genai import types

try:
    from backend.config import PROCESS2_API_KEY, PROCESS2_MODEL
except ImportError:
    from config import PROCESS2_API_KEY, PROCESS2_MODEL

logger = logging.getLogger(__name__)


def _get_client():
    """
    Returns a genai.Client configured with the Process 2 API key.
    Called once per request to ensure isolation from Process 1.
    """
    if not PROCESS2_API_KEY:
        raise ValueError(
            "PROCESS2_API_KEY is not configured. "
            "Set it in your .env file to enable the conversational explainer."
        )
    if not PROCESS2_MODEL:
        raise ValueError(
            "PROCESS2_MODEL is not configured. "
            "Set it in your .env file (recommended: gemma-4-26b-a4b-it)."
        )
    return genai.Client(api_key=PROCESS2_API_KEY)


def _build_system_instruction(metrics: dict, dataset_meta: dict) -> str:
    """
    Builds the system instruction prepended to every request so the model
    always has full awareness of the current audit results.
    """
    return f"""You are a bias auditing assistant embedded inside bAIsed, a fairness \
analysis tool. The user has just completed a bias audit on their dataset. Your job is to \
explain the results in plain English to a non-technical stakeholder.

You have full context of this specific audit:
- Dataset name: {dataset_meta.get('name', 'Unknown')}
- Protected attribute analysed: {dataset_meta.get('protected_attr', 'Unknown')}
- Outcome variable: {dataset_meta.get('outcome', 'Unknown')}
- Disparate Impact Ratio (DIR): {metrics.get('dir')} — values below 0.8 indicate adverse impact
- Statistical Parity Difference (SPD): {metrics.get('spd')} — values far from 0 indicate disparity
- Equal Opportunity Difference (EOD): {metrics.get('eod')}
- Average Odds Difference (AOD): {metrics.get('aod')}
- Overall Bias Score: {metrics.get('bias_score')}/100 — higher is more severe
- Detected patterns: {metrics.get('patterns', [])}
- Proxy variables: {metrics.get('proxies', [])}

Rules:
- Always refer to the actual numbers above, never speak in generalities.
- Explain what each metric means in context of THIS dataset.
- If asked about legal risk, mention relevant frameworks (EEOC, ECOA, EU AI Act) where relevant.
- Keep answers under 150 words unless the user asks for more detail.
- Do not fabricate metric values. Only use the numbers provided above."""


def stream_reply(messages: list, metrics: dict, dataset_meta: dict):
    """
    Generator that yields streamed text chunks.

    messages — full conversation history as list of {role, content} dicts,
               ordered oldest-first. Last entry must be a user message.

    The system instruction (metric values, dataset name, protected attributes)
    is passed on every request so the model always has full audit awareness.
    """
    client = _get_client()
    system_instruction = _build_system_instruction(metrics, dataset_meta)

    # Convert {role, content} history to google.genai Content objects
    history = []
    for msg in messages[:-1]:
        role = "user" if msg.get("role") == "user" else "model"
        history.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

    last_user_text = messages[-1]["content"] if messages else ""

    logger.info("[Process 2] Streaming explainer reply, history length: %d", len(history))

    response = client.models.generate_content_stream(
        model=PROCESS2_MODEL,
        contents=history + [types.Content(role="user", parts=[types.Part(text=last_user_text)])],
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=512,
        ),
    )

    for chunk in response:
        if chunk.text:
            yield chunk.text
