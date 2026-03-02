"""
scan_runner.py — Persist a scan cycle into the database.

Called by both the APScheduler background job and the manual-trigger endpoint.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.analysis.device_classifier import classify_device_type
from app.db import SessionLocal, upsert_device, upsert_port
from app.scanner import ScanResult, orchestrate_scan

logger = logging.getLogger(__name__)


def _fetch_wan_ip() -> str | None:
    """Fetch public WAN IP from checkip.amazonaws.com with a 3-second timeout.

    Returns the IP string on success, or None if the network is unreachable / request fails.
    """
    import urllib.request

    try:
        with urllib.request.urlopen("https://checkip.amazonaws.com", timeout=3) as resp:
            return resp.read().decode().strip()
    except Exception:  # noqa: BLE001 -- best-effort; failures silently skipped
        return None


def _update_wan_ip(db: Session) -> None:
    """Detect public WAN IP and store it as AppSettings. Silently ignores failures."""
    wan_ip = _fetch_wan_ip()
    if wan_ip is None:
        return
    from app.models.settings import AppSetting

    now = datetime.now(tz=UTC).isoformat()
    for key, value in (("wan_ip", wan_ip), ("wan_ip_detected_at", now)):
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=value))
        else:
            row.value = value
    db.commit()
    logger.info("WAN IP updated: %s", wan_ip)


@dataclass
class _PersistSummary:
    """Summary of what changed during a single call to _persist_result."""

    new_device_ids: list[int] = field(default_factory=list)
    disappeared_ips: list[str] = field(default_factory=list)
    # keys: device_id, event_type, port_number, protocol, service_name
    port_events: list[dict] = field(default_factory=list)


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
        scan.current_stage = "scanning"
        db.commit()

        result: ScanResult = orchestrate_scan()
        summary = _persist_result(db, result)

        devices_found = len(result.hosts) + len(result.arp_only)

        scan.current_stage = "analysing"
        db.commit()

        # Run misconfiguration checks against all discovered devices
        from sqlalchemy import select as sa_select

        from app.analysis import (
            run_all_checks,  # noqa: PLC0415 — deferred to avoid circular import at module level
        )
        from app.models.risk import (
            Risk,  # noqa: PLC0415 — deferred to avoid circular import at module level
        )

        # Snapshot existing risks (before checks run) so we can detect changes
        pre_risks = {
            (r.device_id, r.check_id): (r.title, r.severity)
            for r in db.execute(sa_select(Risk)).scalars().all()
        }

        run_all_checks(db)

        post_risks = {
            (r.device_id, r.check_id): (r.title, r.severity)
            for r in db.execute(sa_select(Risk)).scalars().all()
        }

        # Record all change events for this scan
        _record_scan_events(db, scan_id, summary, pre_risks, post_risks)

        # Snapshot risk counts for trend tracking
        from sqlalchemy import func as sqlfunc

        risk_counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for sev in risk_counts:
            risk_counts[sev] = (
                db.execute(
                    sa_select(sqlfunc.count()).select_from(Risk).where(Risk.severity == sev)
                ).scalar_one()
                or 0
            )

        # Generate/update hardening recommendations for all devices
        from app.recommendations import (
            generate_all_recommendations,  # noqa: PLC0415 — deferred to avoid circular import at module level
        )

        generate_all_recommendations(db)

        # Best-effort WAN IP detection (3 s timeout, never fails the scan)
        _update_wan_ip(db)

        # Fire webhook notification (new devices or critical risks)
        from app.notifications import (
            notify_scan_complete,  # noqa: PLC0415 — deferred to avoid circular import at module level
        )

        notify_scan_complete(
            db,
            scan_id=scan_id,
            new_device_ids=summary.new_device_ids,
            risk_counts=risk_counts,
        )

        scan.status = "completed"
        scan.finished_at = datetime.now(tz=UTC)
        scan.duration_seconds = round(time.monotonic() - t0, 2)
        scan.devices_found = devices_found
        scan.risks_critical = risk_counts["critical"]
        scan.risks_high = risk_counts["high"]
        scan.risks_medium = risk_counts["medium"]
        scan.risks_low = risk_counts["low"]
        if result.warnings:
            scan.warning_message = "; ".join(result.warnings)
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


def _persist_result(db: Session, result: ScanResult) -> _PersistSummary:
    """Upsert all devices and ports from a ScanResult into the database.

    Returns a _PersistSummary with new device IDs, disappeared IPs, and port events.
    """
    from sqlalchemy import select

    from app.models.device import Device as DeviceModel
    from app.models.device import Port

    # Snapshot existing state before upserting
    existing_ips: set[str] = {row[0] for row in db.execute(select(DeviceModel.ip_address)).all()}

    # Snapshot existing ports per device for change detection
    pre_ports: dict[int, set[tuple[int, str]]] = {}
    for device_row in db.execute(select(DeviceModel)).scalars().all():
        pre_ports[device_row.id] = {(p.port_number, p.protocol) for p in device_row.ports}

    summary = _PersistSummary()
    scanned_ips: set[str] = set()

    # Full nmap results
    for nh in result.hosts:
        scanned_ips.add(nh.ip)
        device = upsert_device(
            db,
            ip_address=nh.ip,
            mac_address=nh.mac or None,
            hostname=nh.hostname or None,
            os_guess=nh.os_guess or None,
        )
        device.device_type = classify_device_type(
            vendor=device.vendor,
            hostname=nh.hostname or None,
            os_guess=nh.os_guess or None,
        )
        db.flush()
        if nh.ip not in existing_ips:
            summary.new_device_ids.append(device.id)

        current_ports = {(p.port_number, p.protocol) for p in nh.ports}
        old_ports = pre_ports.get(device.id, set())

        for port in nh.ports:
            upsert_port(
                db,
                device_id=device.id,
                port_number=port.port_number,
                protocol=port.protocol,
                service_name=port.service_name or None,
                version_banner=port.version_banner or None,
            )

        # Detect newly opened ports (only for existing devices)
        if nh.ip in existing_ips:
            for port_key in current_ports - old_ports:
                port_obj = next(
                    (p for p in nh.ports if (p.port_number, p.protocol) == port_key), None
                )
                summary.port_events.append(
                    {
                        "device_id": device.id,
                        "event_type": "port_opened",
                        "port_number": port_key[0],
                        "protocol": port_key[1],
                        "service_name": port_obj.service_name if port_obj else None,
                    }
                )
            for port_key in old_ports - current_ports:
                summary.port_events.append(
                    {
                        "device_id": device.id,
                        "event_type": "port_closed",
                        "port_number": port_key[0],
                        "protocol": port_key[1],
                        "service_name": None,
                    }
                )

        # Remove ports no longer seen in this scan
        existing_ports = db.execute(select(Port).where(Port.device_id == device.id)).scalars().all()
        for existing in existing_ports:
            if (existing.port_number, existing.protocol) not in current_ports:
                db.delete(existing)

    # ARP-only hosts (no nmap data)
    for ah in result.arp_only:
        scanned_ips.add(ah.ip)
        device = upsert_device(
            db,
            ip_address=ah.ip,
            mac_address=ah.mac or None,
            vendor=ah.vendor or None,
        )
        device.device_type = classify_device_type(
            vendor=ah.vendor or None,
            hostname=device.hostname,
            os_guess=device.os_guess,
        )
        db.flush()
        if ah.ip not in existing_ips:
            summary.new_device_ids.append(device.id)

    # Detect disappeared devices (were in DB, not found in this scan)
    summary.disappeared_ips = list(existing_ips - scanned_ips)

    db.commit()
    return summary


def _record_scan_events(
    db: Session,
    scan_id: int,
    summary: _PersistSummary,
    pre_risks: dict[tuple[int, str], tuple[str, str]],
    post_risks: dict[tuple[int, str], tuple[str, str]],
) -> None:
    """Insert ScanEvent rows for all detected changes."""
    from sqlalchemy import select

    from app.models.device import Device as DeviceModel
    from app.models.scan_event import ScanEvent

    now = datetime.now(tz=UTC)
    events: list[ScanEvent] = []

    # device_appeared
    if summary.new_device_ids:
        devices = (
            db.execute(select(DeviceModel).where(DeviceModel.id.in_(summary.new_device_ids)))
            .scalars()
            .all()
        )
        for d in devices:
            events.append(
                ScanEvent(
                    scan_id=scan_id,
                    device_id=d.id,
                    event_type="device_appeared",
                    detail=json.dumps(
                        {
                            "ip": d.ip_address,
                            "hostname": d.hostname,
                            "label": d.label,
                            "mac": d.mac_address,
                            "vendor": d.vendor,
                        }
                    ),
                    occurred_at=now,
                )
            )

    # device_disappeared
    if summary.disappeared_ips:
        devices = (
            db.execute(
                select(DeviceModel).where(DeviceModel.ip_address.in_(summary.disappeared_ips))
            )
            .scalars()
            .all()
        )
        for d in devices:
            events.append(
                ScanEvent(
                    scan_id=scan_id,
                    device_id=d.id,
                    event_type="device_disappeared",
                    detail=json.dumps(
                        {
                            "ip": d.ip_address,
                            "hostname": d.hostname,
                            "label": d.label,
                            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
                        }
                    ),
                    occurred_at=now,
                )
            )

    # port_opened / port_closed
    for pe in summary.port_events:
        events.append(
            ScanEvent(
                scan_id=scan_id,
                device_id=pe["device_id"],
                event_type=pe["event_type"],
                detail=json.dumps(
                    {
                        "port": pe["port_number"],
                        "protocol": pe["protocol"],
                        "service": pe["service_name"],
                    }
                ),
                occurred_at=now,
            )
        )

    # risk_appeared / risk_resolved
    appeared_keys = set(post_risks) - set(pre_risks)
    resolved_keys = set(pre_risks) - set(post_risks)

    for key in appeared_keys:
        device_id, check_id = key
        title, severity = post_risks[key]
        events.append(
            ScanEvent(
                scan_id=scan_id,
                device_id=device_id,
                event_type="risk_appeared",
                detail=json.dumps({"check_id": check_id, "title": title, "severity": severity}),
                occurred_at=now,
            )
        )

    for key in resolved_keys:
        device_id, check_id = key
        title, severity = pre_risks[key]
        events.append(
            ScanEvent(
                scan_id=scan_id,
                device_id=device_id,
                event_type="risk_resolved",
                detail=json.dumps({"check_id": check_id, "title": title, "severity": severity}),
                occurred_at=now,
            )
        )

    if events:
        db.add_all(events)
        db.commit()
        logger.info("Scan %d: recorded %d change events", scan_id, len(events))
