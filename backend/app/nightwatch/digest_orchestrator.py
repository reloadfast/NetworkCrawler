"""Digest orchestrator — main Nightwatch entry point.

Combines ntopng, CrowdSec, and NetworkCrawler data, calls LLM,
formats response, and sends to Telegram.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.nightwatch import llm_client
from app.nightwatch import ntopng_fetcher
from app.nightwatch import crowdsec_fetcher
from app.nightwatch import digest_builder
from app.nightwatch import telegram_sender

logger = logging.getLogger(__name__)


async def run_digest(db: Session, preview: bool = False) -> dict[str, Any]:
    """Run the full Nightwatch digest pipeline.
    
    Args:
        db: SQLAlchemy session.
        preview: If True, return digest text without sending to Telegram.
        
    Returns:
        Dict with 'success', 'text', 'error_key fields.
    """
    # Step 1: Load settings
    if not llm_client.is_configured(db):
        return {
            "success": False,
            "text": "Nightwatch is not fully configured. Please set up LLM endpoint, Telegram token, and enable the feature.",
            "error": "not_configured",
        }
    
    config = llm_client.get_config(db)
    ntopng_url = config.get("nightwatch_ntopng_url", "") or "http://192.168.1.110:3030"
    ntopng_username = config.get("nightwatch_ntopng_username")
    ntopng_password = config.get("nightwatch_ntopng_password")
    crowdsec_url = config.get("nightwatch_crowdsec_url", "") or "http://192.168.1.110:8082"
    crowdsec_api_key = config.get("nightwatch_crowdsec_api_key") or ""
    
    # Step 2: Fetch data concurrently
    ntopng_data: dict[str, Any] = {}
    crowdsec_data: dict[str, Any] = {}
    
    try:
        ntopng_data = await ntopng_fetcher.fetch_all_data(ntopng_url, ntopng_username, ntopng_password)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ntopng fetch failed: %s", exc)
    
    try:
        crowdsec_data = await crowdsec_fetcher.fetch_all_data(crowdsec_url, crowdsec_api_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("CrowdSec fetch failed: %s", exc)
    
    # Check if we have any useful data
    has_ntopng = bool(ntopng_data.get("top_talkers") or ntopng_data.get("protocols"))
    has_crowdsec = bool(crowdsec_data.get("active_ban_count", 0) > 0)
    has_networkcrawler = True  # Always try to include scan data
    
    if not has_ntopng and not has_crowdsec and not has_networkcrawler:
        return {
            "success": True,
            "text": "No Nightwatch: nothing to report from any data source.\n\nNo alerts or findings were detected.",
            "error": "no_data",
        }
    
    # Step 3: Build data text and call LLM
    try:
        parsed = digest_builder.call_llm(
            db=db,
            ntopng_data=ntopng_data,
            crowdsec_data=crowdsec_data,
        )
    except ValueError as exc:
        logger.error("LLM processing failed: %s", exc)
        return {
            "success": False,
            "text": f"LLM processing failed: {exc}",
            "error": "llm_error",
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error during LLM call: %s", exc)
        return {
            "success": False,
            "text": f"Unexpected error: {exc}",
            "error": "unexpected_error",
        }
    
    # Step 4: Format response
    findings = parsed.get("findings", [])
    actions = parsed.get("actions", [])
    
    if not findings and not actions:
        return {
            "success": False,
            "text": "LLM returned empty response. Check logs for details.",
            "error": "empty_llm_response",
        }
    
    digest_text = digest_builder.format_findings_as_text(findings, actions)
    
    # Step 5: Preview or send
    if preview:
        return {
            "success": True,
            "text": digest_text,
            "error": None,
            "findings_count": len(findings),
            "actions_count": len(actions),
        }
    
    # Send to Telegram
    bot_token = config.get("nightwatch_telegram_bot_token", "")
    chat_id = config.get("nightwatch_telegram_chat_id", "")
    
    try:
        success = telegram_sender.send_digest(bot_token, chat_id, digest_text)
        if success:
            return {
                "success": True,
                "text": digest_text,
                "error": None,
            }
        else:
            logger.error("Failed to send digest to Telegram")
            raise ValueError("Nightwatch: Failed to send digest to Telegram")
    except Exception as exc:  # noqa: BLE001
        logger.error("Telegram send failed: %s", exc)
        return {
            "success": False,
            "text": f"Digest generated successfully but failed to send to Telegram: {exc}",
            "error": "telegram_error",
        }
