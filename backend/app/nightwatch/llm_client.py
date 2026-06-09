"""LLM service for Nightwatch — LLM interaction module.

Pattern replicates GlucoAssist meal_ai.py contract: single-row config (id=1),
encrypted API keys, OpenAI-compatible API calls with SSE fallback.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models.settings import AppSetting
from app.nightwatch.decrypt_utils import decrypt_api_key

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
_LLM_TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)


# ── Config helpers ──


def _get_setting(db: Session, key: str) -> str | None:
    """Get a single setting value from AppSetting table.

    Args:
        db: SQLAlchemy session.
        key: Setting key name.

    Returns:
        Setting value or None.
    """
    row = db.get(AppSetting, key)
    return row.value if row else None


def save_config(
    db: Session,
    llm_type: str | None = None,
    llm_endpoint: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
    telegram_bot_token: str | None = None,
    telegram_chat_id: str | None = None,
    ntopng_url: str | None = None,
    ntopng_username: str | None = None,
    ntopng_password: str | None = None,
    crowdsec_url: str | None = None,
    crowdsec_api_key: str | None = None,
    enabled: str | None = None,
) -> dict[str, str]:
    """Save Nightwatch config to AppSetting table.

    Only updates keys that are provided (non-None).

    Args:
        db: SQLAlchemy session.
        llm_type: 'ollama' or 'openai_compatible'.
        llm_endpoint: LLM base URL.
        llm_model: Model name (e.g. 'llama3.1:8b').
        llm_api_key: API key (encrypted if provided).
        telegram_bot_token: Telegram bot token.
        telegram_chat_id: Target chat/group ID.
        ntopng_url: ntopng base URL.
        ntopng_username: ntopng basic auth username.
        ntopng_password: ntopng basic auth password.
        crowdsec_url: CrowdSec API URL.
        crowdsec_api_key: bouncer bearer token.
        enabled: 'true' or 'false'.

    Returns:
        Dict of all current settings.
    """
    key_values = {
        "nightwatch_llm_type": llm_type,
        "nightwatch_llm_endpoint": llm_endpoint,
        "nightwatch_llm_model": llm_model,
        "nightwatch_telegram_bot_token": telegram_bot_token,
        "nightwatch_telegram_chat_id": telegram_chat_id,
        "nightwatch_ntopng_url": ntopng_url,
        "nightwatch_ntopng_username": ntopng_username,
        "nightwatch_ntopng_password": ntopng_password,
        "nightwatch_crowdsec_url": crowdsec_url,
        "nightwatch_crowdsec_api_key": crowdsec_api_key,
        "nightwatch_enabled": enabled,
    }

    # Handle encrypted API key
    if llm_api_key is not None:
        key_values["nightwatch_openai_api_key_enc"] = llm_api_key

    for key, value in key_values.items():
        if value is not None:
            row = db.get(AppSetting, key)
            if row is None:
                db.add(AppSetting(key=key, value=value))
            else:
                row.value = value

    db.commit()
    return get_config(db)


def get_config(db: Session) -> dict[str, str]:
    """Get all Nightwatch settings from AppSetting table.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict of all settings.
    """
    keys = [
        "nightwatch_enabled",
        "nightwatch_llm_type",
        "nightwatch_llm_endpoint",
        "nightwatch_llm_model",
        "nightwatch_telegram_bot_token",
        "nightwatch_telegram_chat_id",
        "nightwatch_ntopng_url",
        "nightwatch_ntopng_username",
        "nightwatch_ntopng_password",
        "nightwatch_crowdsec_url",
        "nightwatch_crowdsec_api_key",
        "nightwatch_openai_api_key_enc",
    ]

    result = {}
    rows = db.query(AppSetting).filter(AppSetting.key.in_(keys)).all()
    result = {row.key: row.value for row in rows}
    return result


def is_configured(db: Session) -> bool:
    """Check if Nightwatch is fully configured.

    Requires: enabled='true', LLM endpoint set, Telegram token set.

    Args:
        db: SQLAlchemy session.

    Returns:
        True if all required settings are configured.
    """
    config = get_config(db)
    if not config.get("nightwatch_enabled") == "true":
        return False
    if not (config.get("nightwatch_llm_endpoint") or "").strip():
        return False
    if not (config.get("nightwatch_telegram_bot_token") or "").strip():
        return False
    if not (config.get("nightwatch_telegram_chat_id") or "").strip():
        return False
    return True


# ── LLM helpers ──


def _build_headers(llm_type: str, api_key: str | None) -> dict[str, str]:
    """Build HTTP headers for LLM API call.

    Args:
        llm_type: 'ollama' or 'openai_compatible'.
        api_key: API key (unencrypted).

    Returns:
        Dict of headers.
    """
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if llm_type in ("openai_compatible", "ollama_bearer") and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _chat_url(endpoint: str) -> str:
    """Build chat completions URL from base endpoint.

    Args:
        endpoint: Base URL (e.g. 'http://192.168.1.110:11434').

    Returns:
        Full chat completions URL.
    """
    return endpoint.rstrip("/") + "/v1/chat/completions"


def _parse_sse_content(text: str) -> str:
    """Accumulate assistant content from an SSE-streamed chat completion body.

    Args:
        text: Raw text response from LLM API.

    Returns:
        Accumulated content string.
    """
    parts: list[str] = []
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload.strip() == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
            piece = chunk.get("choices", [{}])[0].get("delta", {}).get("content") or ""
            if piece:
                parts.append(piece)
        except (json.JSONDecodeError, IndexError, KeyError):
            continue
    return "".join(parts)


def _call_llm(
    llm_type: str,
    endpoint: str,
    model: str,
    api_key: str | None,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Call the LLM and return the raw assistant message content.

    Args:
        llm_type: 'ollama' or 'openai_compatible'.
        endpoint: LLM base URL.
        model: Model name.
        api_key: API key (unencrypted).
        system_prompt: System message content.
        user_prompt: User message content.

    Returns:
        Assistant message content string.

    Raises:
        httpx.HTTPStatusError: If API call fails.
    """
    url = _chat_url(endpoint)
    headers = _build_headers(llm_type, api_key)

    safe_model = model or ("gpt-4o" if llm_type == "openai_compatible" else "llama3.1:8b")

    payload: dict[str, Any] = {
        "model": safe_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "stream": False,
    }

    r = httpx.post(url, json=payload, headers=headers, timeout=_LLM_TIMEOUT)
    r.raise_for_status()

    try:
        # Normal non-streaming JSON response
        data = r.json()
        content = data["choices"][0]["message"]["content"]
    except Exception:  # noqa: BLE001 — intentional fallback
        # Proxy returned text/event-stream body — parse SSE
        content = _parse_sse_content(r.text)

    return content.strip()


def _extract_json(text: str) -> Any:
    """Parse JSON from LLM output, stripping markdown fences if present.

    Args:
        text: Raw LLM response text.

    Returns:
        Parsed JSON object.
    """
    import json

    cleaned = re.sub(r"```(?:json)?\s*([\s\S]*?)```", r"\1", text).strip()
    return json.loads(cleaned)


def list_models(db: Session) -> dict[str, Any]:
    """List available models from the configured LLM provider.

    Args:
        db: SQLAlchemy session.

    Returns:
        Dict with 'models' list and optional 'error'.
    """
    config = get_config(db)
    llm_type = config.get("nightwatch_llm_type") or "ollama"
    endpoint = (config.get("nightwatch_llm_endpoint") or "").rstrip("/")
    api_key_enc = config.get("nightwatch_openai_api_key_enc")

    if not endpoint:
        return {"models": [], "error": "LLM endpoint not configured"}

    api_key = decrypt_api_key(api_key_enc) if api_key_enc else None

    try:
        if llm_type in ("ollama", "ollama_bearer"):
            headers: dict[str, str] = {}
            if llm_type == "ollama_bearer" and api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            r = httpx.get(f"{endpoint}/api/tags", headers=headers, timeout=_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            models = [m["name"] for m in data.get("models", [])]
        else:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            r = httpx.get(f"{endpoint}/v1/models", headers=headers, timeout=_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            models = sorted(m["id"] for m in data.get("data", []))

        return {"models": models}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to list LLM models: %s", exc)
        return {"models": [], "error": str(exc)}
