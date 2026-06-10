"""Digest orchestrator — main Nightwatch entry point.

Combines analyzed data from ntopng_analyzer, crowdsec_analyzer,
and cross_reference into pre-analyzed context, then calls LLM,
formats response, and sends to Telegram.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.nightwatch import digest_builder, llm_client
from app.nightwatch.analyzers import cross_reference, crowdsec_analyze, ntopng_analyze

logger = logging.getLogger(__name__)


async def run_digest(db: Session, preview: bool = False) -> dict[str, Any]:
    """Run the full Nightwatch digest pipeline.

    Uses structured analyzers (ntopng_analyze, crowdsec_analyze,
    cross_reference) instead of raw API dumps.

    Args:
        db: SQLAlchemy session.
        preview: If True, return digest text without sending to Telegram.

    Returns:
        Dict with 'success', 'text', 'error' keys.
    """
    # Step 1: Load settings
    if not llm_client.is_configured(db):
        return {
            "success": False,
            "text": (
                "Nightwatch is not fully configured. "
                "Please set up LLM endpoint, "
                "Telegram token, and enable the feature."
            ),
            "error": "not_configured",
        }

    config = llm_client.get_config(db)
    ntopng_url = config.get("nightwatch_ntopng_url", "") or "http://192.168.1.110:3030"
    ntopng_username = config.get("nightwatch_ntopng_username")
    ntopng_password = config.get("nightwatch_ntopng_password")
    crowdsec_url = config.get("nightwatch_crowdsec_url", "") or "http://192.168.1.110:8082"
    crowdsec_api_key = config.get("nightwatch_crowdsec_api_key") or ""

    # Step 2: Fetch raw data concurrently
    from app.nightwatch import crowdsec_fetcher, ntopng_fetcher

    try:
        raw_ntopng = await ntopng_fetcher.fetch_all_data(
            ntopng_url, ntopng_username, ntopng_password
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ntopng fetch failed: %s", exc)
        raw_ntopng = {}

    try:
        raw_crowdsec = await crowdsec_fetcher.fetch_all_data(crowdsec_url, crowdsec_api_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("CrowdSec fetch failed: %s", exc)
        raw_crowdsec = {}

    # Check we have data to analyze
    has_ntopng = bool(raw_ntopng and (raw_ntopng.get("top_talkers") or raw_ntopng.get("protocols")))
    has_crowdsec = bool(raw_crowdsec.get("active_ban_count", 0) > 0)
    has_networkcrawler = True

    if not has_ntopng and not has_crowdsec and not has_networkcrawler:
        return {
            "success": True,
            "text": "No Nightwatch: nothing to report from any data source.",
            "error": "no_data",
        }

    # Step 3: Analyze with dedicated analyzers
    analysis_ntopng = None
    analysis_crowdsec = None
    cross_findings: list[dict[str, Any]] = []

    try:
        analysis_ntopng = ntopng_analyze(raw_ntopng) if raw_ntopng else None
        logger.info(
            "ntopng analysis: %d bandwidth, %d protocol, %d host, %d flow findings",
            len(getattr(analysis_ntopng, "bandwidth_findings", [])),
            len(getattr(analysis_ntopng, "protocol_findings", [])),
            len(getattr(analysis_ntopng, "host_findings", [])),
            len(getattr(analysis_ntopng, "flow_findings", [])),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ntopng analysis failed: %s", exc)

    try:
        analysis_crowdsec = crowdsec_analyze(raw_crowdsec) if raw_crowdsec else {"findings": []}
        logger.info(
            "CrowdSec analysis: %d ban, %d scenario, %d temporal findings",
            len(analysis_crowdsec.get("ban_findings", [])),
            len(analysis_crowdsec.get("scenario_findings", [])),
            len(analysis_crowdsec.get("temporal_findings", [])),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("CrowdSec analysis failed: %s", exc)
        analysis_crowdsec = {"findings": []}

    # Cross-reference
    if raw_ntopng and raw_crowdsec:
        try:
            cross_findings = cross_reference(raw_ntopng, raw_crowdsec)
            logger.info("Cross-reference: %d findings", len(cross_findings))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cross-reference failed: %s", exc)

    # Step 4: Build prompt from ANALYZED data (not raw API responses)
    try:
        # Build ntopng context from ANALYSIS results, falling back to raw if analysis failed
        ntopng_context = {
            "top_talkers": getattr(analysis_ntopng, "findings", []),
            "protocols": {},
            "host_stats": getattr(analysis_ntopng, "findings", []),
            "flows": getattr(analysis_ntopng, "flow_findings", []),
            "total_bytes": getattr(analysis_ntopng, "total_bytes", 0),
            "alerts": [],
            "unusual_protocols": {},
        }
        # If analysis returned flat findings, include them
        if not ntopng_context["top_talkers"] and raw_ntopng:
            ntopng_context["top_talkers"] = raw_ntopng.get("top_talkers", [])
            ntopng_context["protocols"] = raw_ntopng.get("protocols", {})
            ntopng_context["host_stats"] = raw_ntopng.get("host_stats", [])
            ntopng_context["alerts"] = raw_ntopng.get("alerts", [])
            ntopng_context["unusual_protocols"] = raw_ntopng.get("unusual_protocols", {})

        crowdsec_context = {
            "findings": analysis_crowdsec.get("findings", []),
            "ban_findings": analysis_crowdsec.get("ban_findings", []),
            "scenario_findings": analysis_crowdsec.get("scenario_findings", []),
            "temporal_findings": analysis_crowdsec.get("temporal_findings", []),
            "bans": analysis_crowdsec.get("ban_by_ip", {}),
            "reasons": analysis_crowdsec.get("ban_by_reason", {}),
        }

        parsed = digest_builder.call_llm(db, ntopng_context, crowdsec_context)
    except ValueError as exc:
        logger.error("LLM processing failed: %s", exc)
        return {"success": False, "text": f"LLM processing failed: {exc}", "error": "llm_error"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error: %s", exc)
        return {"success": False, "text": f"Unexpected error: {exc}", "error": "unexpected_error"}

    findings = parsed.get("findings", [])
    actions = parsed.get("actions", [])

    if not findings and not actions:
        return {
            "success": False,
            "text": "LLM returned empty response. Check logs for details.",
            "error": "empty_llm_response",
        }

    # Step 5: Format and send
    digest_text = digest_builder.format_findings_as_text(findings, actions)

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

    if not bot_token or not chat_id:
        logger.warning("Telegram not configured — returning digest text")
        return {"success": True, "text": digest_text, "error": None}

    try:
        from app.nightwatch.telegram_sender import send_digest

        success = send_digest(bot_token, chat_id, digest_text)
        if success:
            return {"success": True, "text": digest_text, "error": None}
        else:
            logger.error("Failed to send digest to Telegram")
            raise ValueError("Nightwatch: Failed to send digest to Telegram")
    except Exception as exc:  # noqa: BLE001
        logger.error("Telegram send failed: %s", exc)
        return {
            "success": False,
            "text": f"Digest generated but failed to send: {exc}",
            "error": "telegram_error",
        }
