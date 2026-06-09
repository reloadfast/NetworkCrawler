"""CrowdSec data fetcher for Nightwatch.

Queries CrowdSec API (via bouncer endpoint) for threat data used in daily digest.
Uses bearer token authentication from settings.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def fetch_alerts(
    base_url: str,
    api_key: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Fetch active alerts from CrowdSec API.

    Args:
        base_url: CrowdSec API base URL (e.g. 'http://192.168.1.110:8082').
        api_key: Bearer token from bouncer API key.
        limit: Maximum number of alerts to fetch.

    Returns:
        List of alert dicts with source IP, reason, duration, etc.
    """
    url = f"{base_url.rstrip('/')}/v1/alerts"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    params = {"limit": limit}

    try:
        r = httpx.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        # CrowdSec may return a list or dict with alert keys
        if isinstance(data, dict):
            alerts = data.get("results", data.get("alerts", []))
        elif isinstance(data, list):
            alerts = data
        else:
            alerts = [data]

        # Normalize to consistent format
        records = []
        for alert in alerts:
            if isinstance(alert, dict):
                records.append(
                    {
                        "instance": alert.get("instance", ""),
                        "scheme": alert.get("scheme", "unknown"),
                        "leisure": alert.get("leisure", 0),
                        "ip": alert.get("ip", alert.get("source", {}).get("address", "")),
                        "reason": alert.get("reason", alert.get("scenario", "")),
                        "expire": alert.get("expire", ""),
                        "score": alert.get("score", 0),
                        "events": alert.get("events", 0),
                    }
                )
        return records
    except Exception as exc:  # noqa: BLE001 — best-effort for notification
        logger.warning("Failed to fetch CrowdSec alerts: %s", exc)
        return []


async def fetch_journal(
    base_url: str,
    api_key: str,
    days: int = 1,
) -> list[dict[str, Any]]:
    """Fetch recent events from CrowdSec journal.

    Args:
        base_url: CrowdSec API base URL.
        api_key: Bearer token from bouncer API key.
        days: Number of recent days to fetch (defaults to 1).

    Returns:
        list of event dicts with timestamp, source, action, etc.
    """
    url = f"{base_url.rstrip('/')}/v1/journal/all"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    try:
        r = httpx.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()

        events = []
        if isinstance(data, dict):
            raw_events = data.get("records", data.get("events", data))
        elif isinstance(data, list):
            raw_events = data
        else:
            raw_events = [data]

        for event in raw_events:
            if isinstance(event, dict):
                events.append(
                    {
                        "scenario": event.get("scenario", event.get("id", "")),
                        "timestamp": event.get("timestamp", event.get("created", "")),
                        "processes": event.get("processes", []),
                        "rules": event.get("rules", []),
                    }
                )

        # Filter to last N days
        from datetime import datetime, timedelta

        cutoff = datetime.now() - timedelta(days=days)
        recent = []
        for event in events:
            ts = event.get("timestamp", "")
            if ts:
                try:
                    ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if ts_dt >= cutoff:
                        recent.append(event)
                except ValueError:
                    recent.append(event)  # include if timestamp parse fails
            else:
                recent.append(event)

        return recent
    except Exception as exc:  # noqa: BLE001 — best-effort for notification
        logger.warning("Failed to fetch CrowdSec journal: %s", exc)
        return []


async def fetch_all_data(
    crowdsec_url: str,
    api_key: str,
) -> dict[str, Any]:
    """Fetch all CrowdSec data used for digest.

    Args:
        crowdsec_url: CrowdSec API base URL.
        api_key: Bearer token from bouncer API key.

    Returns:
        dict with alerts, journal, and summary stats.
    """
    import asyncio

    alerts, journal = await asyncio.gather(
        fetch_alerts(crowdsec_url, api_key),
        fetch_journal(crowdsec_url, api_key),
    )

    # Compute summary
    ban_by_ip: dict[str, int] = {}
    ban_by_reason: dict[str, int] = {}
    for alert in alerts:
        ip = alert.get("ip", "")
        reason = alert.get("reason", "unknown")
        if ip:
            ban_by_ip[ip] = ban_by_ip.get("ip", 0) + 1
        if reason:
            ban_by_reason[reason] = ban_by_reason.get("reason", 0) + 1

    return {
        "alerts": alerts,
        "journal": journal,
        "bans": ban_by_ip,
        "reasons": ban_by_reason,
        "active_ban_count": len(alerts),
        "fetched_at": __import__("datetime").datetime.now().isoformat(),
    }
