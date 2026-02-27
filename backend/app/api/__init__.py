"""REST API — /api/devices and /api/scans endpoints."""

from __future__ import annotations

from typing import Annotated

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
    first_seen: str | None  # ISO-8601 string
    last_seen: str | None
    ports: list[PortOut] = []

    model_config = {"from_attributes": True}


class ScanOut(BaseModel):
    id: int
    status: str
    triggered_by: str
    started_at: str | None
    finished_at: str | None
    duration_seconds: float | None
    devices_found: int | None
    error_message: str | None

    model_config = {"from_attributes": True}


class TriggerResponse(BaseModel):
    message: str
    scan_id: int | None = None


# ── /api/devices ──────────────────────────────────────────────────────────────


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Annotated[Session, Depends(get_db)]) -> list[DeviceOut]:
    """Return all known devices with their open ports."""
    from app.models.device import Device

    stmt = select(Device).options(selectinload(Device.ports)).order_by(Device.ip_address)
    devices = db.execute(stmt).scalars().all()
    return [_device_to_out(d) for d in devices]


@router.get("/devices/{device_id}", response_model=DeviceOut)
def get_device(device_id: int, db: Annotated[Session, Depends(get_db)]) -> DeviceOut:
    """Return a single device by ID, including its ports."""
    from app.models.device import Device

    stmt = select(Device).options(selectinload(Device.ports)).where(Device.id == device_id)
    device = db.execute(stmt).scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return _device_to_out(device)


def _device_to_out(d) -> DeviceOut:  # noqa: ANN001 — SQLAlchemy instance, validated via Pydantic
    return DeviceOut(
        id=d.id,
        ip_address=d.ip_address,
        mac_address=d.mac_address,
        vendor=d.vendor,
        hostname=d.hostname,
        os_guess=d.os_guess,
        first_seen=d.first_seen.isoformat() if d.first_seen else None,
        last_seen=d.last_seen.isoformat() if d.last_seen else None,
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
        error_message=s.error_message,
    )
