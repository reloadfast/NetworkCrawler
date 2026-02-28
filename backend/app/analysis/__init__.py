"""Analysis package — risk detection and misconfiguration checks.

Public API:
    run_checks(db, device_id) -> list[Risk]
        Run all registered checks against a single device and upsert Risk rows.

    run_all_checks(db) -> int
        Run checks against every device in the database.  Returns total findings.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.analysis.checks import ALL_CHECKS, RiskData

if TYPE_CHECKING:
    from app.models.risk import Risk

logger = logging.getLogger(__name__)


# ── Public functions ──────────────────────────────────────────────────────────


def run_checks(db: Session, device_id: int) -> list[Risk]:
    """Run all checks for one device and persist findings.

    Existing Risk rows for the same (device_id, check_id) pair are replaced so
    that stale findings are updated rather than accumulated.  Returns the list
    of Risk ORM instances written to the session (caller must commit).
    """
    from app.models.device import Device
    from app.models.risk import Risk

    stmt = select(Device).options(selectinload(Device.ports)).where(Device.id == device_id)
    device = db.execute(stmt).scalar_one_or_none()
    if device is None:
        logger.warning("run_checks: device %d not found", device_id)
        return []

    # Trusted devices are acknowledged — clear any existing risks and skip checks
    existing_stmt = select(Risk).where(Risk.device_id == device_id)
    existing = db.execute(existing_stmt).scalars().all()
    if device.trusted:
        for risk in existing:
            db.delete(risk)
        logger.debug("Device %d is trusted — skipping checks and clearing risks", device_id)
        return []

    # Collect findings from all checks
    all_findings: list[RiskData] = []
    for check_fn in ALL_CHECKS:
        try:
            all_findings.extend(check_fn(device))
        except Exception:  # noqa: BLE001 — isolate individual check failures; log and continue
            logger.exception(
                "Check %s raised an exception for device %d", check_fn.__name__, device_id
            )

    # Build a set of check_ids that fired so we can delete stale entries
    # Delete existing Risk rows for this device (replace fired ones, remove resolved ones)
    for risk in existing:
        db.delete(risk)

    db.flush()

    # Insert fresh Risk rows
    written: list[Risk] = []
    for rd in all_findings:
        risk = Risk(
            device_id=device_id,
            severity=rd.severity,
            check_id=rd.check_id,
            title=rd.title,
            description=rd.description,
            detected_at=datetime.now(tz=UTC),
        )
        db.add(risk)
        written.append(risk)

    logger.debug("Device %d: %d risk(s) written", device_id, len(written))
    return written


def run_all_checks(db: Session) -> int:
    """Run checks for every device in the DB.  Returns total number of risks written."""
    from app.models.device import Device

    device_ids = db.execute(select(Device.id)).scalars().all()
    total = 0
    for device_id in device_ids:
        findings = run_checks(db, device_id)
        total += len(findings)
    db.commit()
    logger.info("run_all_checks: %d total risk(s) across %d device(s)", total, len(device_ids))
    return total
