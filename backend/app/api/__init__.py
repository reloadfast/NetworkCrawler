"""REST API — devices, scans, risks, recommendations, settings, changes, and insights endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db

router = APIRouter(prefix="/api")

# ── Pydantic response schemas ─────────────────────────────────────────────────


class PortOut(BaseModel):
    id: int
    port_number: int
    protocol: str
    service_name: str | None
    version_banner: str | None

    model_config = {"from_attributes": True}


class DeviceOut(BaseModel):
    id: int
    ip_address: str
    mac_address: str | None
    vendor: str | None
    hostname: str | None
    os_guess: str | None
    label: str | None
    trusted: bool
    device_type: str | None  # iot | server | router | workstation | unknown
    first_seen: str | None  # ISO-8601 string
    last_seen: str | None
    ports: list[PortOut] = []
    security_score: int  # 0–100; 100 = no risks

    model_config = {"from_attributes": True}


class ScanOut(BaseModel):
    id: int
    status: str
    triggered_by: str
    started_at: str | None
    finished_at: str | None
    duration_seconds: float | None
    devices_found: int | None
    current_stage: str | None
    error_message: str | None
    warning_message: str | None
    risks_critical: int | None
    risks_high: int | None
    risks_medium: int | None
    risks_low: int | None

    model_config = {"from_attributes": True}


class TriggerResponse(BaseModel):
    message: str
    scan_id: int | None = None


# ── /api/devices ──────────────────────────────────────────────────────────────


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Annotated[Session, Depends(get_db)]) -> list[DeviceOut]:
    """Return all known devices with their open ports."""
    from app.models.device import Device

    stmt = (
        select(Device)
        .options(selectinload(Device.ports), selectinload(Device.risks))
        .order_by(Device.ip_address)
    )
    devices = db.execute(stmt).scalars().all()
    return [_device_to_out(d) for d in devices]


@router.get("/devices/{device_id}", response_model=DeviceOut)
def get_device(device_id: int, db: Annotated[Session, Depends(get_db)]) -> DeviceOut:
    """Return a single device by ID, including its ports."""
    from app.models.device import Device

    stmt = (
        select(Device)
        .options(selectinload(Device.ports), selectinload(Device.risks))
        .where(Device.id == device_id)
    )
    device = db.execute(stmt).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return _device_to_out(device)


class _TrustedUpdate(BaseModel):
    trusted: bool


@router.patch("/devices/{device_id}/trusted", response_model=DeviceOut)
def set_device_trusted(
    device_id: int,
    body: _TrustedUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> DeviceOut:
    """Toggle the trusted flag on a device."""
    from app.models.device import Device

    stmt = (
        select(Device)
        .options(selectinload(Device.ports), selectinload(Device.risks))
        .where(Device.id == device_id)
    )
    device = db.execute(stmt).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    device.trusted = body.trusted
    db.commit()
    db.refresh(device)
    return _device_to_out(device)


class _LabelUpdate(BaseModel):
    label: str | None


@router.patch("/devices/{device_id}/label", response_model=DeviceOut)
def set_device_label(
    device_id: int,
    body: _LabelUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> DeviceOut:
    """Set or clear the user-defined label on a device."""
    from app.models.device import Device

    stmt = (
        select(Device)
        .options(selectinload(Device.ports), selectinload(Device.risks))
        .where(Device.id == device_id)
    )
    device = db.execute(stmt).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    device.label = body.label.strip() if body.label else None
    db.commit()
    db.refresh(device)
    return _device_to_out(device)


def _device_security_score(d) -> int:  # noqa: ANN001 — SQLAlchemy instance
    """Compute 0-100 security score from active risks. 100 = clean."""
    if d.trusted:
        return 100
    weights = {"critical": 30, "high": 15, "medium": 7, "low": 3}
    penalty = sum(weights.get(r.severity, 0) for r in d.risks)
    return max(0, 100 - penalty)


def _device_to_out(d) -> DeviceOut:  # noqa: ANN001 — SQLAlchemy instance, validated via Pydantic
    return DeviceOut(
        id=d.id,
        ip_address=d.ip_address,
        mac_address=d.mac_address,
        vendor=d.vendor,
        hostname=d.hostname,
        os_guess=d.os_guess,
        label=d.label,
        trusted=bool(d.trusted),
        device_type=d.device_type,
        first_seen=d.first_seen.isoformat() if d.first_seen else None,
        last_seen=d.last_seen.isoformat() if d.last_seen else None,
        security_score=_device_security_score(d),
        ports=[
            PortOut(
                id=p.id,
                port_number=p.port_number,
                protocol=p.protocol,
                service_name=p.service_name,
                version_banner=p.version_banner,
            )
            for p in d.ports
        ],
    )


# ── /api/scans ────────────────────────────────────────────────────────────────


@router.get("/scans", response_model=list[ScanOut])
def list_scans(db: Annotated[Session, Depends(get_db)]) -> list[ScanOut]:
    """Return scan history, newest first."""
    from app.models.scan import Scan

    stmt = select(Scan).order_by(Scan.started_at.desc())
    scans = db.execute(stmt).scalars().all()
    return [_scan_to_out(s) for s in scans]


@router.post("/scans/trigger", response_model=TriggerResponse, status_code=202)
def trigger_scan(background_tasks: BackgroundTasks) -> TriggerResponse:
    """Enqueue a manual scan in the background and return immediately."""
    from app.scan_runner import run_scan_and_persist

    background_tasks.add_task(run_scan_and_persist, "manual")
    return TriggerResponse(message="Scan enqueued")


def _scan_to_out(s) -> ScanOut:  # noqa: ANN001 — SQLAlchemy instance
    return ScanOut(
        id=s.id,
        status=s.status,
        triggered_by=s.triggered_by,
        started_at=s.started_at.isoformat() if s.started_at else None,
        finished_at=s.finished_at.isoformat() if s.finished_at else None,
        duration_seconds=s.duration_seconds,
        devices_found=s.devices_found,
        current_stage=s.current_stage,
        error_message=s.error_message,
        warning_message=s.warning_message,
        risks_critical=s.risks_critical,
        risks_high=s.risks_high,
        risks_medium=s.risks_medium,
        risks_low=s.risks_low,
    )


# ── /api/risks ────────────────────────────────────────────────────────────────


class RiskOut(BaseModel):
    id: int
    device_id: int
    ip_address: str
    hostname: str | None
    severity: str
    display_severity: str  # may differ from severity based on active network profile
    check_id: str
    title: str
    description: str
    detected_at: str | None
    acknowledged_at: str | None
    acknowledged_note: str | None

    model_config = {"from_attributes": True}


class RiskSummary(BaseModel):
    critical: int
    high: int
    medium: int
    low: int
    total: int


_SeverityParam = Literal["critical", "high", "medium", "low"]


@router.get("/risks", response_model=list[RiskOut])
def list_risks(
    db: Annotated[Session, Depends(get_db)],
    severity: _SeverityParam | None = None,
    device_id: int | None = None,
    acknowledged: bool | None = None,
) -> list[RiskOut]:
    """Return risk findings, ordered by severity then detected_at.

    Optional query parameters:
    - ``severity``: filter to a single severity level (critical/high/medium/low)
    - ``device_id``: filter to risks belonging to a specific device
    - ``acknowledged``: ``true`` → acknowledged only; ``false`` → active only; omit → all
    """
    from app.models.risk import Risk

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    stmt = select(Risk).options(selectinload(Risk.device))
    if severity is not None:
        stmt = stmt.where(Risk.severity == severity)
    if device_id is not None:
        stmt = stmt.where(Risk.device_id == device_id)
    if acknowledged is True:
        stmt = stmt.where(Risk.acknowledged_at.isnot(None))
    elif acknowledged is False:
        stmt = stmt.where(Risk.acknowledged_at.is_(None))
    risks = db.execute(stmt).scalars().all()
    risks_sorted = sorted(
        risks, key=lambda r: (severity_order.get(r.severity, 99), r.detected_at or "")
    )
    profile = _get_active_profile(db)
    return [_risk_to_out(r, profile) for r in risks_sorted]


@router.get("/risks/summary", response_model=RiskSummary)
def risks_summary(db: Annotated[Session, Depends(get_db)]) -> RiskSummary:
    """Return a count of active (non-acknowledged) risks per severity level."""
    from app.models.risk import Risk

    all_risks = db.execute(select(Risk).where(Risk.acknowledged_at.is_(None))).scalars().all()
    counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for r in all_risks:
        if r.severity in counts:
            counts[r.severity] += 1
    return RiskSummary(
        critical=counts["critical"],
        high=counts["high"],
        medium=counts["medium"],
        low=counts["low"],
        total=sum(counts.values()),
    )


@router.get("/risks/{risk_id}", response_model=RiskOut)
def get_risk(risk_id: int, db: Annotated[Session, Depends(get_db)]) -> RiskOut:
    """Return a single risk by ID."""
    from app.models.risk import Risk

    stmt = select(Risk).options(selectinload(Risk.device)).where(Risk.id == risk_id)
    risk = db.execute(stmt).scalar_one_or_none()
    if risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    return _risk_to_out(risk, _get_active_profile(db))


class _AcknowledgeBody(BaseModel):
    note: str | None = None


@router.patch("/risks/{risk_id}/acknowledge", response_model=RiskOut)
def acknowledge_risk(
    risk_id: int,
    body: _AcknowledgeBody,
    db: Annotated[Session, Depends(get_db)],
) -> RiskOut:
    """Mark a risk as acknowledged (accepted). Survives future re-scans."""
    from datetime import UTC, datetime

    from app.models.risk import Risk

    stmt = select(Risk).options(selectinload(Risk.device)).where(Risk.id == risk_id)
    risk = db.execute(stmt).scalar_one_or_none()
    if risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    risk.acknowledged_at = datetime.now(tz=UTC)
    risk.acknowledged_note = body.note
    db.commit()
    db.refresh(risk)
    return _risk_to_out(risk, _get_active_profile(db))


@router.patch("/risks/{risk_id}/unacknowledge", response_model=RiskOut)
def unacknowledge_risk(
    risk_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> RiskOut:
    """Remove the acknowledgement from a risk, returning it to the active list."""
    from app.models.risk import Risk

    stmt = select(Risk).options(selectinload(Risk.device)).where(Risk.id == risk_id)
    risk = db.execute(stmt).scalar_one_or_none()
    if risk is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    risk.acknowledged_at = None
    risk.acknowledged_note = None
    db.commit()
    db.refresh(risk)
    return _risk_to_out(risk, _get_active_profile(db))


@router.get("/devices/{device_id}/risks", response_model=list[RiskOut])
def device_risks(device_id: int, db: Annotated[Session, Depends(get_db)]) -> list[RiskOut]:
    """Return all risks for a specific device."""
    from app.models.device import Device
    from app.models.risk import Risk

    device = db.execute(select(Device).where(Device.id == device_id)).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    stmt = select(Risk).options(selectinload(Risk.device)).where(Risk.device_id == device_id)
    risks = db.execute(stmt).scalars().all()
    profile = _get_active_profile(db)
    return [_risk_to_out(r, profile) for r in risks]


def _get_active_profile(db: Session) -> str:
    from app.analysis.profiles import DEFAULT_PROFILE, VALID_PROFILES
    from app.models.settings import AppSetting

    row = db.get(AppSetting, "network_profile")
    if row and row.value in VALID_PROFILES:
        return row.value
    return DEFAULT_PROFILE


def _risk_to_out(r, profile: str = "standard_home") -> RiskOut:  # noqa: ANN001 — SQLAlchemy instance
    from app.analysis.profiles import display_severity_for_check

    return RiskOut(
        id=r.id,
        device_id=r.device_id,
        ip_address=r.device.ip_address,
        hostname=r.device.hostname,
        severity=r.severity,
        display_severity=display_severity_for_check(r.check_id, r.severity, profile),
        check_id=r.check_id,
        title=r.title,
        description=r.description,
        detected_at=r.detected_at.isoformat() if r.detected_at else None,
        acknowledged_at=r.acknowledged_at.isoformat() if r.acknowledged_at else None,
        acknowledged_note=r.acknowledged_note,
    )


# ── /api/recommendations ──────────────────────────────────────────────────────

import json as _json  # noqa: E402 — after router definitions to keep imports grouped above
import logging as _logging  # noqa: E402 — after router definitions to keep imports grouped above

_api_logger = _logging.getLogger(__name__)


class RecommendationOut(BaseModel):
    id: int
    device_id: int
    risk_id: int
    check_id: str
    severity: str
    title: str
    description: str
    steps: list[str]
    effort: str
    impact: str
    attack_scenario: str | None
    likelihood: str | None
    created_at: str | None
    updated_at: str | None

    model_config = {"from_attributes": True}


@router.get("/recommendations", response_model=list[RecommendationOut])
def list_recommendations(
    db: Annotated[Session, Depends(get_db)],
    device_id: int | None = None,
    severity: str | None = None,
) -> list[RecommendationOut]:
    """Return all recommendations, optionally filtered by device_id and/or severity."""
    from app.models.recommendation import Recommendation

    stmt = select(Recommendation)
    if device_id is not None:
        stmt = stmt.where(Recommendation.device_id == device_id)
    if severity is not None:
        stmt = stmt.where(Recommendation.severity == severity)
    recs = db.execute(stmt).scalars().all()
    return [_rec_to_out(r) for r in recs]


@router.get("/recommendations/{rec_id}", response_model=RecommendationOut)
def get_recommendation(rec_id: int, db: Annotated[Session, Depends(get_db)]) -> RecommendationOut:
    """Return a single recommendation by ID."""
    from app.models.recommendation import Recommendation

    stmt = select(Recommendation).where(Recommendation.id == rec_id)
    rec = db.execute(stmt).scalar_one_or_none()
    if rec is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return _rec_to_out(rec)


@router.get("/devices/{device_id}/recommendations", response_model=list[RecommendationOut])
def device_recommendations(
    device_id: int, db: Annotated[Session, Depends(get_db)]
) -> list[RecommendationOut]:
    """Return all recommendations for a specific device."""
    from app.models.device import Device
    from app.models.recommendation import Recommendation

    device = db.execute(select(Device).where(Device.id == device_id)).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    stmt = select(Recommendation).where(Recommendation.device_id == device_id)
    recs = db.execute(stmt).scalars().all()
    return [_rec_to_out(r) for r in recs]


def _safe_load_steps(raw: str | None) -> list[str]:
    """Deserialise recommendation steps from JSON string; returns [] on failure."""
    if not raw:
        return []
    try:
        result = _json.loads(raw)
        return result if isinstance(result, list) else []
    except _json.JSONDecodeError:
        _api_logger.warning("Malformed steps JSON in recommendation: %r", raw[:120])
        return []


def _rec_to_out(r) -> RecommendationOut:  # noqa: ANN001 — SQLAlchemy instance
    return RecommendationOut(
        id=r.id,
        device_id=r.device_id,
        risk_id=r.risk_id,
        check_id=r.check_id,
        severity=r.severity,
        title=r.title,
        description=r.description,
        steps=_safe_load_steps(r.steps),
        effort=r.effort,
        impact=r.impact,
        attack_scenario=r.attack_scenario,
        likelihood=r.likelihood,
        created_at=r.created_at.isoformat() if r.created_at else None,
        updated_at=r.updated_at.isoformat() if r.updated_at else None,
    )


# ── /api/settings ─────────────────────────────────────────────────────────────


class SettingsOut(BaseModel):
    webhook_url: str | None
    network_profile: str


class _SettingsUpdate(BaseModel):
    webhook_url: str | None = None
    network_profile: str | None = None


@router.get("/settings", response_model=SettingsOut)
def get_settings(db: Annotated[Session, Depends(get_db)]) -> SettingsOut:
    """Return current application settings."""
    from app.notifications import get_webhook_url

    return SettingsOut(
        webhook_url=get_webhook_url(db),
        network_profile=_get_active_profile(db),
    )


@router.patch("/settings", response_model=SettingsOut)
def update_settings(
    body: _SettingsUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> SettingsOut:
    """Persist application settings."""
    from app.analysis.profiles import VALID_PROFILES
    from app.models.settings import AppSetting
    from app.notifications import get_webhook_url, set_webhook_url

    if body.webhook_url is not None:
        set_webhook_url(db, body.webhook_url.strip() or None)
    if body.network_profile is not None and body.network_profile in VALID_PROFILES:
        row = db.get(AppSetting, "network_profile")
        if row is None:
            db.add(AppSetting(key="network_profile", value=body.network_profile))
        else:
            row.value = body.network_profile
        db.commit()
    return SettingsOut(
        webhook_url=get_webhook_url(db),
        network_profile=_get_active_profile(db),
    )


class _TestWebhookResponse(BaseModel):
    success: bool
    message: str


@router.post("/settings/webhook/test", response_model=_TestWebhookResponse)
def test_webhook(db: Annotated[Session, Depends(get_db)]) -> _TestWebhookResponse:
    """Fire a test notification to the configured webhook URL."""
    from app.notifications import get_webhook_url, send_webhook

    url = get_webhook_url(db)
    if not url:
        raise HTTPException(status_code=422, detail="No webhook URL configured")
    send_webhook(
        url,
        {
            "event": "test",
            "title": "NetworkCrawler Test",
            "message": "Webhook is working correctly.",
            "summary": "Webhook is working correctly.",
        },
    )
    return _TestWebhookResponse(success=True, message=f"Test notification sent to {url}")


# ── /api/settings/checklist ───────────────────────────────────────────────────

_CHECKLIST_QUESTIONS: list[dict[str, str]] = [
    {
        "key": "checklist_upnp_disabled",
        "question": "Is UPnP disabled on your router?",
        "advice": (
            "UPnP lets devices automatically open ports to the internet. "
            "Attackers can abuse it to punch holes in your firewall without any credentials."
        ),
    },
    {
        "key": "checklist_wps_disabled",
        "question": "Is WPS disabled on your router?",
        "advice": (
            "WPS PIN mode can be brute-forced in hours with freely available tools. "
            "Disable it and rely on WPA2/WPA3 passphrase authentication."
        ),
    },
    {
        "key": "checklist_wifi_wpa2_or_better",
        "question": "Is your WiFi using WPA2 or WPA3?",
        "advice": (
            "WEP and WPA (TKIP) can be cracked in minutes. "
            "Upgrade to WPA2-AES minimum; WPA3 is preferred if all your devices support it."
        ),
    },
    {
        "key": "checklist_admin_wan_blocked",
        "question": "Is your router admin panel blocked from WAN access?",
        "advice": (
            "A WAN-accessible admin panel exposes router management to the entire internet. "
            "Disable remote management unless you specifically need it."
        ),
    },
    {
        "key": "checklist_iot_network_isolated",
        "question": "Do you use a guest or separate VLAN for IoT devices?",
        "advice": (
            "IoT devices on your main LAN can pivot to attack PCs, NAS, and other sensitive "
            "systems. Isolate them on a guest network with no inter-VLAN routing."
        ),
    },
    {
        "key": "checklist_firmware_updated",
        "question": "Is your router firmware up to date?",
        "advice": (
            "Outdated firmware contains known CVEs that are actively scanned and exploited. "
            "Check for updates quarterly and enable auto-update if available."
        ),
    },
    {
        "key": "checklist_unique_passwords",
        "question": "Do you use unique, strong passwords (e.g. via a password manager)?",
        "advice": (
            "Reused passwords enable credential-stuffing attacks: one leaked password "
            "compromises every account using it. Use a password manager for unique passwords."
        ),
    },
    {
        "key": "checklist_remote_mgmt_disabled",
        "question": "Is remote management (SSH/Telnet) disabled on your router?",
        "advice": (
            "SSH/Telnet on a router exposed to the internet is a constant brute-force target. "
            "Disable it unless you have key-only SSH strictly needed."
        ),
    },
]

_POSTURE_LEVELS = [
    (8, "hardened", "Hardened"),
    (6, "intermediate", "Intermediate"),
    (4, "basic", "Basic"),
    (0, "at_risk", "At Risk"),
]


def _compute_posture(yes_count: int) -> tuple[str, str]:
    for threshold, badge, label in _POSTURE_LEVELS:
        if yes_count >= threshold:
            return badge, label
    return "at_risk", "At Risk"


class ChecklistItemOut(BaseModel):
    key: str
    question: str
    advice: str
    answer: str  # "yes" | "no" | "unknown"


class ChecklistOut(BaseModel):
    items: list[ChecklistItemOut]
    posture: str
    posture_label: str
    yes_count: int


class _ChecklistUpdate(BaseModel):
    answers: dict[str, str]  # key → "yes"|"no"|"unknown"


def _get_checklist(db: Session) -> ChecklistOut:
    from sqlalchemy import select as sa_select

    from app.models.settings import AppSetting

    valid_answers = {"yes", "no", "unknown"}
    keys = [q["key"] for q in _CHECKLIST_QUESTIONS]
    rows = db.execute(sa_select(AppSetting).where(AppSetting.key.in_(keys))).scalars().all()
    stored = {r.key: r.value for r in rows}

    items: list[ChecklistItemOut] = []
    yes_count = 0
    for q in _CHECKLIST_QUESTIONS:
        raw = stored.get(q["key"], "unknown")
        answer = raw if raw in valid_answers else "unknown"
        if answer == "yes":
            yes_count += 1
        items.append(
            ChecklistItemOut(
                key=q["key"],
                question=q["question"],
                advice=q["advice"],
                answer=answer,
            )
        )

    posture, posture_label = _compute_posture(yes_count)
    return ChecklistOut(
        items=items,
        posture=posture,
        posture_label=posture_label,
        yes_count=yes_count,
    )


@router.get("/settings/checklist", response_model=ChecklistOut)
def get_checklist(db: Annotated[Session, Depends(get_db)]) -> ChecklistOut:
    """Return the network health checklist and current posture badge."""
    return _get_checklist(db)


@router.post("/settings/checklist", response_model=ChecklistOut)
def update_checklist(
    body: _ChecklistUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> ChecklistOut:
    """Persist checklist answers and return updated posture."""
    from app.models.settings import AppSetting

    valid_keys = {q["key"] for q in _CHECKLIST_QUESTIONS}
    valid_answers = {"yes", "no", "unknown"}

    for key, value in body.answers.items():
        if key not in valid_keys or value not in valid_answers:
            continue
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=value))
        else:
            row.value = value

    db.commit()
    return _get_checklist(db)


# ── /api/changes ──────────────────────────────────────────────────────────────


class ScanEventOut(BaseModel):
    id: int
    scan_id: int
    device_id: int | None
    event_type: str
    detail: str | None
    occurred_at: str | None
    reviewed: bool


class ChangesSummaryOut(BaseModel):
    unreviewed: int


@router.get("/changes", response_model=list[ScanEventOut])
def list_changes(
    db: Annotated[Session, Depends(get_db)],
    reviewed: bool | None = None,
    device_id: int | None = None,
    limit: int = 200,
) -> list[ScanEventOut]:
    """Return scan change events, newest first."""
    from app.models.scan_event import ScanEvent

    stmt = select(ScanEvent).order_by(ScanEvent.occurred_at.desc()).limit(limit)
    if reviewed is not None:
        stmt = stmt.where(ScanEvent.reviewed == reviewed)
    if device_id is not None:
        stmt = stmt.where(ScanEvent.device_id == device_id)
    events = db.execute(stmt).scalars().all()
    return [_event_to_out(e) for e in events]


@router.get("/changes/summary", response_model=ChangesSummaryOut)
def changes_summary(db: Annotated[Session, Depends(get_db)]) -> ChangesSummaryOut:
    """Return count of unreviewed change events."""
    from sqlalchemy import func as sqlfunc

    from app.models.scan_event import ScanEvent

    count = db.execute(
        select(sqlfunc.count()).select_from(ScanEvent).where(ScanEvent.reviewed == False)  # noqa: E712 — SQLAlchemy needs == False
    ).scalar_one()
    return ChangesSummaryOut(unreviewed=count or 0)


@router.patch("/changes/{event_id}/reviewed", response_model=ScanEventOut)
def mark_event_reviewed(
    event_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> ScanEventOut:
    """Mark a single change event as reviewed."""
    from app.models.scan_event import ScanEvent

    event = db.execute(select(ScanEvent).where(ScanEvent.id == event_id)).scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    event.reviewed = True
    db.commit()
    db.refresh(event)
    return _event_to_out(event)


@router.patch("/changes/reviewed/all", response_model=ChangesSummaryOut)
def mark_all_reviewed(db: Annotated[Session, Depends(get_db)]) -> ChangesSummaryOut:
    """Mark all unreviewed change events as reviewed."""
    from app.models.scan_event import ScanEvent

    db.execute(
        select(ScanEvent).where(ScanEvent.reviewed == False)  # noqa: E712 — SQLAlchemy needs == False
    )
    from sqlalchemy import update as sa_update

    db.execute(
        sa_update(ScanEvent).where(ScanEvent.reviewed == False).values(reviewed=True)  # noqa: E712 — SQLAlchemy needs == False
    )
    db.commit()
    return ChangesSummaryOut(unreviewed=0)


def _event_to_out(e) -> ScanEventOut:  # noqa: ANN001 — SQLAlchemy instance
    return ScanEventOut(
        id=e.id,
        scan_id=e.scan_id,
        device_id=e.device_id,
        event_type=e.event_type,
        detail=e.detail,
        occurred_at=e.occurred_at.isoformat() if e.occurred_at else None,
        reviewed=bool(e.reviewed),
    )


# ── /api/insights/segmentation ────────────────────────────────────────────────


class MixedRiskPairOut(BaseModel):
    iot_device_id: int
    iot_ip: str
    server_device_id: int
    server_ip: str
    shared_subnet: str


class SegmentationOut(BaseModel):
    flat_network: bool
    iot_count: int
    server_count: int
    mixed_risk_pairs: list[MixedRiskPairOut]
    recommendations: list[str]


@router.get("/insights/segmentation", response_model=SegmentationOut)
def get_segmentation(db: Annotated[Session, Depends(get_db)]) -> SegmentationOut:
    """Detect flat-network conditions and return VLAN segmentation advice."""
    from app.analysis.segmentation import analyse_segmentation

    result = analyse_segmentation(db)
    return SegmentationOut(
        flat_network=result.flat_network,
        iot_count=result.iot_count,
        server_count=result.server_count,
        mixed_risk_pairs=[
            MixedRiskPairOut(
                iot_device_id=p.iot_device_id,
                iot_ip=p.iot_ip,
                server_device_id=p.server_device_id,
                server_ip=p.server_ip,
                shared_subnet=p.shared_subnet,
            )
            for p in result.mixed_risk_pairs
        ],
        recommendations=result.recommendations,
    )
