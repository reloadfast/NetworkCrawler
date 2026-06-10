"""HTTP handlers for Nightwatch module.

Endpoints:
- GET /api/nightwatch/preview — run digest without sending to Telegram
- GET /api/nightwatch/analyzer-results — inspect pre-analyzed findings
- GET /api/nightwatch/models — list available LLM models
- GET /api/nightwatch/is-configured — check Nightwatch config status
"""

from __future__ import annotations

import logging

from app.db import get_db
from app.nightwatch import digest_orchestrator, llm_client
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nightwatch", tags=["nightwatch"])


@router.get("/preview")
async def get_nightwatch_preview(db: Session = Depends(get_db)):  # noqa: B008
    """Run a preview of the Nightwatch digest without sending to Telegram."""
    result = await digest_orchestrator.run_digest(db, preview=True)
    return result


@router.get("/analyzer-results")
async def get_nightwatch_analyzer_results(db: Session = Depends(get_db)):  # noqa: B008
    """Inspect the pre-analyzed findings from ntopng and CrowdSec analyzers.

    Returns raw analyzer results for frontend debugging/inspection.
    Does NOT call the LLM or send Telegram messages.
    """
    config = llm_client.get_config(db)
    ntopng_url = config.get("nightwatch_ntopng_url", "") or "http://192.168.1.110:3030"
    ntopng_username = config.get("nightwatch_ntopng_username")
    ntopng_password = config.get("nightwatch_ntopng_password")
    crowdsec_url = config.get("nightwatch_crowdsec_url", "") or "http://192.168.1.110:8082"
    crowdsec_api_key = config.get("nightwatch_crowdsec_api_key") or ""

    try:
        raw_ntopng = await _fetch_ntopng(ntopng_url, ntopng_username, ntopng_password)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ntopng fetch failed during analyzer results: %s", exc)
        raw_ntopng = {}

    try:
        raw_crowdsec = await _fetch_crowdsec(crowdsec_url, crowdsec_api_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("CrowdSec fetch failed during analyzer results: %s", exc)
        raw_crowdsec = {}

    # Run analyzers
    ntopng_analysis = None
    crowdsec_analysis = None
    from app.nightwatch.analyzers import crowdsec_analyzer as cs_analyzer
    from app.nightwatch.analyzers import ntopng_analyzer

    if raw_ntopng:
        ntopng_analysis = ntopng_analyzer.ntopng_analyze(raw_ntopng)

    if raw_crowdsec:
        crowdsec_analysis = cs_analyzer.crowdsec_analyze(raw_crowdsec)

    # Cross-reference
    cross_result = []
    if raw_ntopng and raw_crowdsec:
        from app.nightwatch.analyzers.cross_reference import cross_reference

        cross_result = cross_reference(raw_ntopng, raw_crowdsec)

    # Convert to serializable dicts
    ntopng_result = {}
    if ntopng_analysis and hasattr(ntopng_analysis, "findings"):
        ntopng_result = {
            "bandwidth_findings_count": len(ntopng_analysis.bandwidth_findings),
            "protocol_findings_count": len(ntopng_analysis.protocol_findings),
            "host_findings_count": len(ntopng_analysis.host_findings),
            "flow_findings_count": len(ntopng_analysis.flow_findings),
            "total_bytes": getattr(ntopng_analysis, "total_bytes", 0),
            "findings": [
                {"severity": f.severity, "summary": f.summary} for f in ntopng_analysis.findings
            ],
        }

    crowdsec_result = {}
    if crowdsec_analysis:
        crowdsec_result = {
            "ban_findings_count": len(crowdsec_analysis.get("ban_findings", [])),
            "scenario_findings_count": len(crowdsec_analysis.get("scenario_findings", [])),
            "temporal_findings_count": len(crowdsec_analysis.get("temporal_findings", [])),
            "total_alerts": crowdsec_analysis.get("total_alerts", 0),
            "active_ban_count": crowdsec_analysis.get("active_ban_count", 0),
            "findings": [
                {"severity": f.severity, "summary": f.summary, "ip": f.ip}
                for f in crowdsec_analysis.get("ban_findings", [])
            ],
        }

    cross_serialized = [{"severity": f.severity, "summary": f.summary} for f in cross_result]

    return {
        "success": True,
        "ntopng": ntopng_result,
        "crowdsec": crowdsec_result,
        "cross_reference": cross_serialized,
    }


async def _fetch_ntopng(url: str, user: str | None, pw: str | None):
    from app.nightwatch.ntopng_fetcher import fetch_all_data

    return await fetch_all_data(url, user, pw)


async def _fetch_crowdsec(url: str, key: str):
    from app.nightwatch.crowdsec_fetcher import fetch_all_data

    return await fetch_all_data(url, key)


@router.get("/models")
async def get_lpm_models(db: Session = Depends(get_db)):  # noqa: B008
    """List available models from the configured LLM provider."""
    return llm_client.list_models(db)


@router.get("/is-configured")
async def check_if_configured(db: Session = Depends(get_db)):  # noqa: B008
    """Check if Nightwatch is fully configured."""
    return {"configured": llm_client.is_configured(db)}
