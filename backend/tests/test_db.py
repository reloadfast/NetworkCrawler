"""
Unit and integration tests for database initialisation, session management,
ORM models, and upsert helpers.

Markers: unit, integration
"""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def in_memory_engine():
    """Provide a fresh in-memory SQLite engine with tables created."""
    import app.models.device  # noqa: F401 — register ORM models
    from app.db import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def session(in_memory_engine):
    """Yield a transactional session that is rolled back after each test."""
    factory = sessionmaker(bind=in_memory_engine)
    with factory() as s:
        yield s


# ── Schema tests ──────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_init_db_creates_devices_table(in_memory_engine):
    inspector = inspect(in_memory_engine)
    assert "devices" in inspector.get_table_names()


@pytest.mark.unit
def test_init_db_creates_ports_table(in_memory_engine):
    inspector = inspect(in_memory_engine)
    assert "ports" in inspector.get_table_names()


@pytest.mark.unit
def test_devices_table_columns(in_memory_engine):
    inspector = inspect(in_memory_engine)
    cols = {c["name"] for c in inspector.get_columns("devices")}
    assert {
        "id",
        "ip_address",
        "mac_address",
        "vendor",
        "hostname",
        "os_guess",
        "first_seen",
        "last_seen",
    } <= cols


@pytest.mark.unit
def test_ports_table_columns(in_memory_engine):
    inspector = inspect(in_memory_engine)
    cols = {c["name"] for c in inspector.get_columns("ports")}
    assert {"id", "device_id", "port_number", "protocol", "service_name", "version_banner"} <= cols


@pytest.mark.unit
def test_devices_unique_constraint_exists(in_memory_engine):
    inspector = inspect(in_memory_engine)
    unique_names = {uc["name"] for uc in inspector.get_unique_constraints("devices")}
    assert "uq_devices_ip_address" in unique_names


@pytest.mark.unit
def test_ports_unique_constraint_exists(in_memory_engine):
    inspector = inspect(in_memory_engine)
    unique_names = {uc["name"] for uc in inspector.get_unique_constraints("ports")}
    assert "uq_ports_device_port_proto" in unique_names


# ── Session helper tests ──────────────────────────────────────────────────────


@pytest.mark.integration
def test_get_db_yields_and_closes(in_memory_engine, monkeypatch):
    """get_db dependency yields a session and closes it after iteration."""
    from app import db as db_module

    test_session_factory = sessionmaker(bind=in_memory_engine)
    monkeypatch.setattr(db_module, "SessionLocal", test_session_factory)

    gen = db_module.get_db()
    session = next(gen)
    assert session is not None
    try:
        next(gen)
    except StopIteration:
        pass


# ── Basic CRUD tests ──────────────────────────────────────────────────────────


@pytest.mark.integration
def test_device_crud(session):
    """Basic Device create/read round-trip."""
    from app.models.device import Device

    device = Device(ip_address="192.168.1.1", hostname="router")
    session.add(device)
    session.commit()
    session.refresh(device)

    fetched = session.get(Device, device.id)
    assert fetched.ip_address == "192.168.1.1"  # type: ignore[union-attr]
    assert fetched.hostname == "router"  # type: ignore[union-attr]


@pytest.mark.integration
def test_device_vendor_field(session):
    """vendor column is persisted and retrieved correctly."""
    from app.models.device import Device

    device = Device(
        ip_address="192.168.1.10", mac_address="aa:bb:cc:dd:ee:ff", vendor="Raspberry Pi"
    )
    session.add(device)
    session.commit()

    fetched = session.get(Device, device.id)
    assert fetched.vendor == "Raspberry Pi"  # type: ignore[union-attr]


@pytest.mark.integration
def test_port_crud_with_device(session):
    """Port linked to Device creates FK relationship correctly."""
    from app.models.device import Device, Port

    device = Device(ip_address="192.168.1.2")
    session.add(device)
    session.flush()

    port = Port(device_id=device.id, port_number=22, protocol="tcp", service_name="ssh")
    session.add(port)
    session.commit()

    fetched_port = session.get(Port, port.id)
    assert fetched_port.port_number == 22  # type: ignore[union-attr]
    assert fetched_port.device_id == device.id  # type: ignore[union-attr]


@pytest.mark.integration
def test_device_cascade_deletes_ports(session):
    """Deleting a Device cascades to its Ports."""
    from app.models.device import Device, Port

    device = Device(ip_address="192.168.1.3")
    session.add(device)
    session.flush()
    port = Port(device_id=device.id, port_number=80)
    session.add(port)
    session.commit()

    port_id = port.id
    session.delete(device)
    session.commit()

    assert session.get(Port, port_id) is None


# ── UniqueConstraint enforcement tests ───────────────────────────────────────


@pytest.mark.integration
def test_device_ip_unique_constraint_enforced(session):
    """Inserting two Devices with the same IP raises IntegrityError."""
    from app.models.device import Device

    session.add(Device(ip_address="10.0.0.1"))
    session.commit()
    session.add(Device(ip_address="10.0.0.1"))
    with pytest.raises(IntegrityError):
        session.commit()


@pytest.mark.integration
def test_port_unique_constraint_enforced(session):
    """Inserting two Ports with same (device_id, port_number, protocol) raises IntegrityError."""
    from app.models.device import Device, Port

    device = Device(ip_address="10.0.0.2")
    session.add(device)
    session.flush()
    session.add(Port(device_id=device.id, port_number=443, protocol="tcp"))
    session.commit()
    session.add(Port(device_id=device.id, port_number=443, protocol="tcp"))
    with pytest.raises(IntegrityError):
        session.commit()


# ── upsert_device tests ───────────────────────────────────────────────────────


@pytest.mark.integration
def test_upsert_device_creates_new(session):
    """upsert_device inserts a new row when ip_address is not present."""
    from app.db import upsert_device

    device = upsert_device(
        session,
        ip_address="172.16.0.1",
        mac_address="de:ad:be:ef:00:01",
        vendor="Cisco",
        hostname="gw",
    )
    session.commit()

    assert device.id is not None
    assert device.ip_address == "172.16.0.1"
    assert device.vendor == "Cisco"


@pytest.mark.integration
def test_upsert_device_updates_existing(session):
    """upsert_device updates non-None fields on an existing row."""
    from app.db import upsert_device
    from app.models.device import Device

    session.add(Device(ip_address="172.16.0.2", hostname="old-name"))
    session.commit()

    upsert_device(session, ip_address="172.16.0.2", hostname="new-name", vendor="Ubiquiti")
    session.commit()

    from sqlalchemy import select

    device = session.execute(select(Device).where(Device.ip_address == "172.16.0.2")).scalar_one()
    assert device.hostname == "new-name"
    assert device.vendor == "Ubiquiti"


@pytest.mark.integration
def test_upsert_device_none_does_not_overwrite(session):
    """upsert_device leaves existing values intact when update fields are None."""
    from app.db import upsert_device
    from app.models.device import Device

    session.add(Device(ip_address="172.16.0.3", hostname="keep-me", vendor="Intel"))
    session.commit()

    # Call with hostname=None — should NOT overwrite the stored "keep-me"
    upsert_device(session, ip_address="172.16.0.3", hostname=None, vendor=None)
    session.commit()

    from sqlalchemy import select

    device = session.execute(select(Device).where(Device.ip_address == "172.16.0.3")).scalar_one()
    assert device.hostname == "keep-me"
    assert device.vendor == "Intel"


@pytest.mark.integration
def test_upsert_device_idempotent(session):
    """Calling upsert_device twice with the same IP returns the same row."""
    from app.db import upsert_device

    d1 = upsert_device(session, ip_address="172.16.0.4")
    session.commit()
    d2 = upsert_device(session, ip_address="172.16.0.4")
    session.commit()

    assert d1.id == d2.id


# ── upsert_port tests ─────────────────────────────────────────────────────────


@pytest.mark.integration
def test_upsert_port_creates_new(session):
    """upsert_port inserts a new Port row."""
    from app.db import upsert_device, upsert_port

    device = upsert_device(session, ip_address="10.10.0.1")
    session.flush()

    port = upsert_port(session, device_id=device.id, port_number=22, service_name="ssh")
    session.commit()

    assert port.id is not None
    assert port.service_name == "ssh"


@pytest.mark.integration
def test_upsert_port_updates_existing(session):
    """upsert_port updates service_name / version_banner on an existing Port."""
    from app.db import upsert_device, upsert_port

    device = upsert_device(session, ip_address="10.10.0.2")
    session.flush()
    upsert_port(session, device_id=device.id, port_number=80, service_name="http")
    session.commit()

    upsert_port(
        session,
        device_id=device.id,
        port_number=80,
        service_name="http",
        version_banner="nginx/1.25",
    )
    session.commit()

    from app.models.device import Port
    from sqlalchemy import select

    port = session.execute(
        select(Port).where(Port.device_id == device.id, Port.port_number == 80)
    ).scalar_one()
    assert port.version_banner == "nginx/1.25"


@pytest.mark.integration
def test_upsert_port_idempotent(session):
    """Calling upsert_port twice with same key returns the same row."""
    from app.db import upsert_device, upsert_port

    device = upsert_device(session, ip_address="10.10.0.3")
    session.flush()

    p1 = upsert_port(session, device_id=device.id, port_number=443, protocol="tcp")
    session.commit()
    p2 = upsert_port(session, device_id=device.id, port_number=443, protocol="tcp")
    session.commit()

    assert p1.id == p2.id
