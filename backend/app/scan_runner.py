"""
scan_runner.py — Persist a scan cycle into the database.

Called by both the APScheduler background job and the manual-trigger endpoint.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db import SessionLocal, upsert_device, upsert_port
from app.scanner import ScanResult, orchestrate_scan

logger = logging.getLogger(__name__)


def run_scan_and_persist(triggered_by: str = "scheduler") -> int:
    """Run a full scan cycle and persist results.

    Creates a Scan history record, calls orchestrate_scan(), upserts all
    discovered devices and ports, then marks the Scan as completed or failed.

    Returns the Scan.id of the created record.
    """
    from app.models.scan import Scan

    db: Session = SessionLocal()
    scan = Scan(triggered_by=triggered_by, started_at=datetime.now(tz=UTC))
    db.add(scan)
    db.commit()
    db.refresh(scan)
    scan_id: int = scan.id

    t0 = time.monotonic()
    try:
        result: ScanResult = orchestrate_scan()
        _persist_result(db, result)
        devices_found = len(result.hosts) + len(result.arp_only)

        # Run misconfiguration checks against all discovered devices
        from app.analysis import (
            run_all_checks,  # noqa: PLC0415 — deferred to avoid circular import at module level
        )

        run_all_checks(db)

        scan.status = "completed"
        scan.finished_at = datetime.now(tz=UTC)
        scan.duration_seconds = round(time.monotonic() - t0, 2)
        scan.devices_found = devices_found
        db.commit()
        logger.info("Scan %d completed: %d devices", scan_id, devices_found)

    except Exception as exc:  # noqa: BLE001 — intentional broad catch; log and mark failed
        logger.exception("Scan %d failed: %s", scan_id, exc)
        scan.status = "failed"
        scan.finished_at = datetime.now(tz=UTC)
        scan.duration_seconds = round(time.monotonic() - t0, 2)
        scan.error_message = str(exc)
        db.commit()

    finally:
        db.close()

    return scan_id


def _persist_result(db: Session, result: ScanResult) -> None:
    """Upsert all devices and ports from a ScanResult into the database."""
    # Full nmap results
    for nh in result.hosts:
        device = upsert_device(
            db,
            ip_address=nh.ip,
            mac_address=nh.mac or None,
            hostname=nh.hostname or None,
            os_guess=nh.os_guess or None,
        )
        db.flush()
        for port in nh.ports:
            upsert_port(
                db,
                device_id=device.id,
                port_number=port.port_number,
                protocol=port.protocol,
                service_name=port.service_name or None,
                version_banner=port.version_banner or None,
            )

    # ARP-only hosts (no nmap data)
    for ah in result.arp_only:
        upsert_device(
            db,
            ip_address=ah.ip,
            mac_address=ah.mac or None,
            vendor=ah.vendor or None,
        )

    db.commit()
