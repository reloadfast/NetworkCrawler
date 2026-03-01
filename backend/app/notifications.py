"""Webhook notification helpers.

Sends a JSON POST to a configured URL when notable scan events occur:
  - One or more new devices appeared on the network
  - One or more unacknowledged critical risks were found

The webhook URL is read from the ``app_settings`` table (key ``webhook_url``),
falling back to the ``NOTIFY_WEBHOOK_URL`` environment variable.  If neither
is set, notifications are silently skipped.

The HTTP request uses only stdlib (``urllib.request``) — no extra runtime dep.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_SETTING_KEY = "webhook_url"


def get_webhook_url(db: Session) -> str | None:
    """Return the configured webhook URL, or None if not set."""
    from sqlalchemy import select

    from app.models.settings import AppSetting

    row = db.execute(select(AppSetting).where(AppSetting.key == _SETTING_KEY)).scalar_one_or_none()
    if row and row.value:
        return row.value.strip() or None
    return os.getenv("NOTIFY_WEBHOOK_URL") or None


def set_webhook_url(db: Session, url: str | None) -> None:
    """Persist the webhook URL in the settings table."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    from app.models.settings import AppSetting

    stmt = sqlite_insert(AppSetting).values(key=_SETTING_KEY, value=url or "")
    stmt = stmt.on_conflict_do_update(index_elements=["key"], set_={"value": url or ""})
    db.execute(stmt)
    db.commit()


def send_webhook(url: str, payload: dict) -> None:
    """POST ``payload`` as JSON to ``url``.  Logs but never raises on failure."""
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(  # noqa: S310 — URL is user-configured
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "NetworkCrawler"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 — URL is user-configured
            status = resp.status
        logger.info("Webhook delivered to %s (HTTP %s)", url, status)
    except urllib.error.URLError as exc:
        logger.warning("Webhook delivery failed: %s", exc)
    except Exception:  # noqa: BLE001 — never let notifications crash the scan runner
        logger.exception("Unexpected error delivering webhook")


def notify_scan_complete(
    db: Session,
    *,
    scan_id: int,
    new_device_ids: list[int],
    risk_counts: dict[str, int],
) -> None:
    """Build a scan-complete notification payload and fire it if a URL is configured.

    Only fires if there is something worth reporting: at least one new device
    or at least one unacknowledged critical risk.
    """
    url = get_webhook_url(db)
    if not url:
        return

    critical_count = risk_counts.get("critical", 0)
    if not new_device_ids and critical_count == 0:
        return  # nothing interesting to report

    # Resolve device details for the notification body
    from sqlalchemy import select

    from app.models.device import Device

    new_devices = []
    if new_device_ids:
        rows = db.execute(select(Device).where(Device.id.in_(new_device_ids))).scalars().all()
        new_devices = [
            {
                "ip": d.ip_address,
                "hostname": d.hostname,
                "mac": d.mac_address,
                "vendor": d.vendor,
            }
            for d in rows
        ]

    # Build a human-readable summary line (ntfy.sh / plain-text compatible)
    parts = []
    if new_devices:
        parts.append(f"{len(new_devices)} new device(s)")
    if critical_count:
        parts.append(f"{critical_count} critical risk(s)")
    summary = " and ".join(parts) + " detected"

    payload = {
        # Generic webhook fields
        "event": "scan_complete",
        "scan_id": scan_id,
        "summary": summary,
        "new_devices": new_devices,
        "risk_counts": risk_counts,
        # ntfy.sh-compatible fields (title + message)
        "title": "NetworkCrawler Alert",
        "message": summary,
    }
    send_webhook(url, payload)
