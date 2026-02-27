"""Database connection, initialisation, and session helpers."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

if TYPE_CHECKING:
    from app.models.device import Device

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./networkcrawler.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables if they don't exist."""
    from app.models import device as _device  # noqa: F401 — side-effect import registers ORM tables

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency: yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def upsert_device(
    session: Session,
    *,
    ip_address: str,
    mac_address: str | None = None,
    vendor: str | None = None,
    hostname: str | None = None,
    os_guess: str | None = None,
) -> "Device":
    """Insert or update a Device row keyed on ip_address.

    If a Device with the given ip_address already exists, only non-None
    fields are written so that richer data from a previous scan is never
    overwritten with None.  The caller is responsible for committing.

    Returns the Device instance (either existing or newly created).
    """
    from app.models.device import Device
    from sqlalchemy import select

    stmt = select(Device).where(Device.ip_address == ip_address)
    device: Device | None = session.execute(stmt).scalar_one_or_none()

    if device is None:
        device = Device(
            ip_address=ip_address,
            mac_address=mac_address,
            vendor=vendor,
            hostname=hostname,
            os_guess=os_guess,
        )
        session.add(device)
    else:
        if mac_address is not None:
            device.mac_address = mac_address
        if vendor is not None:
            device.vendor = vendor
        if hostname is not None:
            device.hostname = hostname
        if os_guess is not None:
            device.os_guess = os_guess

    return device


def upsert_port(
    session: Session,
    *,
    device_id: int,
    port_number: int,
    protocol: str = "tcp",
    service_name: str | None = None,
    version_banner: str | None = None,
) -> "Device":
    """Insert or update a Port row keyed on (device_id, port_number, protocol).

    Non-None fields overwrite existing values.  Caller must commit.
    Returns the Port instance.
    """
    from app.models.device import Port
    from sqlalchemy import select

    stmt = select(Port).where(
        Port.device_id == device_id,
        Port.port_number == port_number,
        Port.protocol == protocol,
    )
    port = session.execute(stmt).scalar_one_or_none()

    if port is None:
        port = Port(
            device_id=device_id,
            port_number=port_number,
            protocol=protocol,
            service_name=service_name,
            version_banner=version_banner,
        )
        session.add(port)
    else:
        if service_name is not None:
            port.service_name = service_name
        if version_banner is not None:
            port.version_banner = version_banner

    return port
