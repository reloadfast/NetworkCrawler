"""Hardening recommendation engine.

Public API:
    generate_recommendations(db, device_id) -> list[Recommendation]
        Create or update Recommendation rows for every Risk on a device.

    generate_all_recommendations(db) -> int
        Run generate_recommendations for every device in the DB.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.recommendation import Recommendation

logger = logging.getLogger(__name__)


# ── Advice catalogue ──────────────────────────────────────────────────────────
# One entry per check_id produced by app.analysis.checks.  Each entry provides
# the human-readable remediation advice attached to the generated Recommendation.


@dataclass(frozen=True)
class _Advice:
    title: str
    description: str
    steps: list[str]
    effort: str  # "low" | "medium" | "high"
    impact: str  # "low" | "medium" | "high"


_CATALOGUE: dict[str, _Advice] = {
    "telnet_open": _Advice(
        title="Disable Telnet and switch to SSH",
        description=(
            "Telnet transmits all data including credentials in plain text. "
            "An attacker with network access can intercept sessions trivially."
        ),
        steps=[
            "Log in to the device management interface.",
            "Locate the remote-access or services configuration section.",
            "Disable the Telnet (port 23) service entirely.",
            "Enable SSH if remote access is still required.",
            "Verify port 23 is no longer reachable from the network.",
        ],
        effort="low",
        impact="critical",
    ),
    "ftp_open": _Advice(
        title="Replace FTP with SFTP or FTPS",
        description=(
            "FTP sends usernames, passwords, and file contents in cleartext. "
            "Replace it with SFTP (SSH File Transfer Protocol) or FTPS (FTP over TLS)."
        ),
        steps=[
            "Identify what service is using port 21.",
            "Configure SFTP or FTPS as the replacement transfer method.",
            "Update all clients that connect to this device to use the new protocol.",
            "Disable the FTP service and close port 21.",
            "Test connectivity with the new secure protocol.",
        ],
        effort="medium",
        impact="high",
    ),
    "unencrypted_http": _Advice(
        title="Enable HTTPS on the management interface",
        description=(
            "The device exposes an unencrypted HTTP management interface. "
            "Credentials and configuration data transmitted over HTTP can be intercepted."
        ),
        steps=[
            "Access the device admin panel.",
            "Navigate to the HTTPS / SSL/TLS settings.",
            "Generate or upload a TLS certificate (self-signed is acceptable for LAN management).",
            "Enable HTTPS and set it as the default protocol.",
            "Disable HTTP or configure an automatic redirect from HTTP to HTTPS.",
        ],
        effort="low",
        impact="medium",
    ),
    "upnp_exposed": _Advice(
        title="Disable UPnP on non-router devices",
        description=(
            "Universal Plug and Play (UPnP) on a non-router device can be abused to "
            "automatically open ports or redirect traffic without authorisation."
        ),
        steps=[
            "Log in to the device management interface.",
            "Find the network or UPnP settings section.",
            "Disable the UPnP service.",
            "Verify that port 1900/UDP is no longer responding to SSDP discovery.",
        ],
        effort="low",
        impact="medium",
    ),
    "ssh_password_auth": _Advice(
        title="Disable SSH password authentication and use key-based auth",
        description=(
            "SSH servers that accept password authentication are vulnerable to brute-force "
            "and credential-stuffing attacks. Key-based authentication is significantly "
            "more secure."
        ),
        steps=[
            "Generate an SSH key pair on the client machine if you do not already have one.",
            "Copy the public key to the device's authorised_keys file.",
            "Edit /etc/ssh/sshd_config (or equivalent) and set: PasswordAuthentication no",
            "Reload the SSH service: sudo systemctl reload sshd",
            "Verify that password login is now rejected.",
        ],
        effort="medium",
        impact="medium",
    ),
    "smb_open": _Advice(
        title="Close or restrict SMB/NetBIOS ports",
        description=(
            "SMB (ports 445, 137-139) exposed on a non-NAS device broadens the attack surface "
            "and is a common ransomware entry point. Restrict or disable unless actively needed."
        ),
        steps=[
            "Determine whether SMB file sharing is actively used on this device.",
            "If not needed, disable SMB/Windows File Sharing in the OS or device settings.",
            "If needed, restrict access via firewall rules to specific trusted IP addresses only.",
            "Ensure the device's OS and SMB service are fully patched.",
            "Audit shared folders and remove any open or guest shares.",
        ],
        effort="medium",
        impact="high",
    ),
    "printer_iot_admin": _Advice(
        title="Restrict printer/IoT admin UI access",
        description=(
            "Printer and IoT device admin interfaces on common ports are frequently targeted "
            "by automated scanners. Restrict access and change default credentials."
        ),
        steps=[
            "Change the default administrator password on the device.",
            "Configure a firewall rule to allow admin UI access only from trusted "
            "management hosts.",
            "Disable remote admin access from the WAN/internet side if applicable.",
            "Check for and apply any available firmware updates.",
            "Disable unused services and protocols in the device's admin panel.",
        ],
        effort="low",
        impact="medium",
    ),
    "outdated_banner": _Advice(
        title="Update outdated service software",
        description=(
            "One or more services are advertising version banners that suggest outdated software "
            "with known CVEs. Update to current stable releases to patch known vulnerabilities."
        ),
        steps=[
            "Identify the exact software and version from the service banner.",
            "Check the vendor's security advisories for relevant CVEs.",
            "Apply available OS or package updates: e.g. sudo apt upgrade <package>",
            "If the OS is end-of-life, plan a migration to a supported version.",
            "After updating, re-scan to confirm the old version banner is no longer present.",
        ],
        effort="medium",
        impact="low",
    ),
}


# ── Public functions ──────────────────────────────────────────────────────────


def generate_recommendations(db: Session, device_id: int) -> list[Recommendation]:
    """Create or update Recommendation rows for every current Risk on *device_id*.

    Existing recommendations for the device are fully replaced so that resolved
    risks no longer have stale recommendations.  Caller must commit the session.
    """
    from app.models.recommendation import Recommendation
    from app.models.risk import Risk

    # Remove stale recommendations for this device
    existing = (
        db.execute(select(Recommendation).where(Recommendation.device_id == device_id))
        .scalars()
        .all()
    )
    for rec in existing:
        db.delete(rec)
    db.flush()

    # Fetch current risks for this device
    risks = db.execute(select(Risk).where(Risk.device_id == device_id)).scalars().all()

    written: list[Recommendation] = []
    now = datetime.now(tz=UTC)

    for risk in risks:
        advice = _CATALOGUE.get(risk.check_id)
        if advice is None:
            logger.warning(
                "No advice catalogue entry for check_id=%r (device %d, risk %d)",
                risk.check_id,
                device_id,
                risk.id,
            )
            continue

        rec = Recommendation(
            device_id=device_id,
            risk_id=risk.id,
            check_id=risk.check_id,
            severity=risk.severity,
            title=advice.title,
            description=advice.description,
            steps=json.dumps(advice.steps),
            effort=advice.effort,
            impact=advice.impact,
            created_at=now,
            updated_at=now,
        )
        db.add(rec)
        written.append(rec)

    logger.debug("Device %d: %d recommendation(s) written", device_id, len(written))
    return written


def generate_all_recommendations(db: Session) -> int:
    """Generate recommendations for every device.  Returns total count written."""
    from app.models.device import Device

    device_ids = db.execute(select(Device.id)).scalars().all()
    total = 0
    for device_id in device_ids:
        recs = generate_recommendations(db, device_id)
        total += len(recs)
    db.commit()
    logger.info(
        "generate_all_recommendations: %d recommendation(s) across %d device(s)",
        total,
        len(device_ids),
    )
    return total
