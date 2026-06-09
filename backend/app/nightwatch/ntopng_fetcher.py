"""ntopng data fetcher for Nightwatch.

Queries ntopng v5 REST API for network data used in daily digest.
Uses basic auth from settings.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def _url(base: str) -> str:
    """Normalize base URL."""
    return base.rstrip("/")


async def fetch_top_talkers(
    base_url: str,
    username: str | None,
    password: str | None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch top talkers from ntopng.

    Args:
        base_url: ntopng base URL (e.g. 'http://192.168.1.110:3030').
        username: Basic auth username.
        password: Basic auth password.
        limit: Max number of results.

    Returns:
        List of top talker dicts with ip, name, bytes_sent, bytes_recv, etc.
    """
    url = f"{_url(base_url)}/rest/interface/topTalkers"
    auth = (username, password) if username and password else None

    try:
        r = httpx.get(url, auth=auth, headers={"Accept": "application/json"}, timeout=30)
        r.raise_for_status()
        data = r.json()
        # ntopng returns nested dicts keyed by device name/IP; extract values
        records = []
        for name, props in data.items()[:limit]:
            if isinstance(props, dict):
                records.append({"device": name, **props})
            elif isinstance(props, str):
                records.append({"device": props})
        return records
    except Exception as exc:  # noqa: BLE001 — best-effort notification, non-fatal
        logger.warning("Failed to fetch ntopng topTalkers: %s", exc)
        return []


async def fetch_alerts(
    base_url: str, username: str | None, password: str | None
) -> list[dict[str, Any]]:
    """Fetch ntopng alert definitions.

    Args:
        base_url: ntopng base URL.
        username: Basic auth username.
        password: Basic auth password.

    Returns:
        List of alert dicts.
    """
    url = f"{_url(base_url)}/rest/interface/alerts"
    auth = (username, password) if username and password else None

    try:
        r = httpx.get(url, auth=auth, headers={"Accept": "application/json"}, timeout=30)
        r.raise_for_status()
        data = r.json()
        records = []
        for name, props in data.items() if isinstance(data, dict) else data:
            if isinstance(props, dict):
                records.append({"alert": name, **props})
            elif isinstance(props, str):
                records.append({"alert": props})
        return records
    except Exception as exc:  # noqa: BLE001 — best-effort notification, non-fatal
        logger.warning("Failed to fetch ntopng alerts: %s", exc)
        return []


async def fetch_protocol_stats(
    base_url: str,
    username: str | None,
    password: str | None,
) -> dict[str, int]:
    """Fetch protocol statistics from ntopng.

    Args:
        base_url: ntopng base URL.
        username: Basic auth username.
        password: Basic auth password.

    Returns:
        Dict mapping protocol name to byte count.
    """
    url = f"{_url(base_url)}/rest/interface/protocolsStats"
    auth = (username, password) if username and password else None

    try:
        r = httpx.get(url, auth=auth, headers={"Accept": "application/json"}, timeout=30)
        r.raise_for_status()
        data = r.json()
        stats: dict[str, int] = {}
        for proto, props in data.items() if isinstance(data, dict) else data:
            if isinstance(props, dict):
                bytes_val = props.get("bytes_sent", 0) + props.get("bytes_recv", 0)
                stats[proto] = bytes_val
            elif isinstance(props, (int, float)):
                stats[proto] = int(props)
        return stats
    except Exception as exc:  # noqa: BLE001 — best-effort notification, non-fatal
        logger.warning("Failed to fetch protocol stats: %s", exc)
        return {}


async def fetch_host_stats(
    base_url: str,
    username: str | None,
    password: str | None,
) -> list[dict[str, Any]]:
    """Fetch host-level statistics from ntopng.

    Args:
        base_url: ntopng base URL.
        username: Basic auth username.
        password: Basic auth password.

    Returns:
        List of host stat dicts.
    """
    url = f"{_url(base_url)}/rest/interface/hosts"
    auth = (username, password) if username and password else None

    try:
        r = httpx.get(url, auth=auth, headers={"Accept": "application/json"}, timeout=30)
        r.raise_for_status()
        data = r.json()
        records = []
        for name, props in data.items() if isinstance(data, dict) else data:
            if isinstance(props, dict):
                props["host"] = name
                records.append(props)
        return records
    except Exception as exc:  # noqa: BLE001 — best-effort notification, non-fatal
        logger.warning("Failed to fetch host stats: %s", exc)
        return []


async def fetch_flows(
    base_url: str,
    username: str | None,
    password: str | None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Fetch flow data from ntopng (for anomaly detection).

    Args:
        base_url: ntopng base URL.
        username: Basic auth username.
        password: Basic auth password.
        limit: Max number of flows.

    Returns:
        List of flow dicts.
    """
    url = f"{_url(base_url)}/rest/interface/flows"
    auth = (username, password) if username and password else None

    params = {"limit": limit, "sort": "bytes", "order": "desc"}

    try:
        r = httpx.get(
            url, auth=auth, headers={"Accept": "application/json"}, params=params, timeout=30
        )
        r.raise_for_status()
        data = r.json()
        records = []
        for item in data.items() if isinstance(data, dict) else data:
            if isinstance(item, dict):
                records.append(item)
        return records[:limit]
    except Exception as exc:  # noqa: BLE001 — best-effort notification, non-fatal
        logger.warning("Failed to fetch flows: %s", exc)
        return []


async def fetch_all_data(
    ntopng_url: str,
    username: str | None,
    password: str | None,
) -> dict[str, Any]:
    """Fetch all ntopng data used for digest.

    Args:
        ntopng_url: ntopng base URL.
        username: Basic auth username.
        password: Basic auth password.

    Returns:
        Dict with all fetched data sections.
    """
    top_talkers = await fetch_top_talkers(ntopng_url, username, password)
    alerts = await fetch_alerts(ntopng_url, username, password)
    protocols = await fetch_protocol_stats(ntopng_url, username, password)
    hosts = await fetch_host_stats(ntopng_url, username, password)
    flows = await fetch_flows(ntopng_url, username, password)

    # Compute summary stats
    total_bytes = sum(protocols.values())
    unusual_protocols = {
        k: v
        for k, v in protocols.items()
        if k.upper() not in ("TCP", "UDP", "HTTP", "HTTPS", "DNS", "ICMP")
    }

    return {
        "top_talkers": top_talkers,
        "alerts": alerts,
        "protocols": protocols,
        "host_stats": hosts,
        "flows": flows,
        "total_bytes": total_bytes,
        "unusual_protocols": unusual_protocols,
        "fetched_at": datetime.now().isoformat(),
    }
