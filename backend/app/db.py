"""Database connection, initialisation, and session helpers."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

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


def _migrate_schema(engine) -> None:
    """Add any missing columns introduced after initial schema creation."""
    migrations = [
        ("devices", "trusted", "BOOLEAN NOT NULL DEFAULT 0"),
        ("scans", "current_stage", "TEXT"),
        ("scans", "warning_message", "TEXT"),
        ("risks", "acknowledged_at", "DATETIME"),
        ("risks", "acknowledged_note", "TEXT"),
        ("devices", "label", "TEXT"),
        ("recommendations", "attack_scenario", "TEXT"),
        ("recommendations", "likelihood", "TEXT"),
        ("devices", "device_type", "TEXT DEFAULT 'unknown'"),
    ]
    with engine.connect() as conn:
        for table, column, col_def in migrations:
            result = conn.execute(text(f"PRAGMA table_info({table})"))  # noqa: S608 -- PRAGMA not user input
            existing_cols = {row[1] for row in result}
            if column not in existing_cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))  # noqa: S608 -- table/column/col_def are internal constants, not user input
                conn.commit()
        # Ensure the MAC address index exists (CREATE INDEX IF NOT EXISTS is idempotent).
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_devices_mac_address ON devices (mac_address)"  # noqa: S608 -- DDL constant
            )
        )
        conn.commit()


def init_db() -> None:
    """Create all tables if they don't exist."""
    # Ensure the data directory exists -- required when a volume is freshly mounted
    # and the directory hasn't been initialised yet (e.g. first run with a bind mount).
    _db_url = DATABASE_URL
    if _db_url.startswith("sqlite:///") and not _db_url.startswith("sqlite:///:"):
        # Strip the scheme prefix; four slashes = absolute path, three = relative
        db_path = Path(_db_url[len("sqlite:///") :])
        db_path.parent.mkdir(parents=True, exist_ok=True)

    from app.models import (
        device as _device,  # noqa: F401 -- side-effect import registers ORM tables
    )
    from app.models import (
        recommendation as _recommendation,  # noqa: F401 -- side-effect import registers ORM tables
    )
    from app.models import risk as _risk  # noqa: F401 -- side-effect import registers ORM tables
    from app.models import scan as _scan  # noqa: F401 -- side-effect import registers ORM tables
    from app.models import (
        scan_event as _scan_event,  # noqa: F401 -- side-effect import registers ORM tables
    )
    from app.models import (
        settings as _settings,  # noqa: F401 -- side-effect import registers ORM tables
    )

    Base.metadata.create_all(bind=engine)
    _migrate_schema(engine)


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
) -> Device:
    """Insert or update a Device row, using MAC address as the primary identity key.

    Lookup order:
    1. If mac_address is provided, find an existing device with that MAC.
       - Found at the same IP → normal update (non-None fields only).
       - Found at a different IP → update ip_address to the new one, preserving
         user-set fields (label, trusted, device_type).
    2. Fall back to ip_address lookup (covers devices that don't broadcast MAC,
       e.g. traffic routed through a switch without ARP visibility).
    3. If no existing device is found, create a new one.

    The caller is responsible for committing.  Returns the Device instance.
    """
    from sqlalchemy import select

    from app.models.device import Device

    device: Device | None = None

    # --- MAC-first lookup ---
    if mac_address is not None:
        device = session.execute(
            select(Device).where(Device.mac_address == mac_address)
        ).scalar_one_or_none()
        if device is not None and device.ip_address != ip_address:
            # Check if the new IP address already exists in the devices table
            existing_device_with_new_ip = session.execute(
                select(Device).where(Device.ip_address == ip_address)
            ).scalar_one_or_none()
            if existing_device_with_new_ip is not None:
                logger.error(
                    f"Attempted to update device with MAC {mac_address} to IP {ip_address}, "
                    f"but IP already exists for device with ID {existing_device_with_new_ip.id}. "
                    "Skipping update."
                )
            else:
                # Device moved to a new IP -- update the address in place so
                # user-assigned label/trusted/device_type are preserved.
                device.ip_address = ip_address

    # --- IP fallback ---
    if device is None:
        device = session.execute(
            select(Device).where(Device.ip_address == ip_address)
        ).scalar_one_or_none()
        if device is not None:
            logger.error(
                f"Attempted to create a new device with IP {ip_address}, "
                f"but IP already exists for device with ID {device.id}. Skipping update."
            )
            return device

    # --- Create ---
    if device is None:
        device = Device(
            ip_address=ip_address,
            mac_address=mac_address,
            vendor=vendor,
            hostname=hostname,
            os_guess=os_guess,
        )
        session.add(device)
        return device

    # --- Update non-None scan fields (never overwrite user-set fields) ---
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
) -> Device:
    """Insert or update a Port row keyed on (device_id, port_number, protocol).

    Non-None fields overwrite existing values.  Caller must commit.
    Returns the Port instance.
    """
    from sqlalchemy import select

    from app.models.device import Port

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
