"""
Unit and integration tests for database initialisation and session management.

Markers: unit, integration
"""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
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


@pytest.mark.unit()
def test_init_db_creates_devices_table(in_memory_engine):
    inspector = inspect(in_memory_engine)
    assert "devices" in inspector.get_table_names()


@pytest.mark.unit()
def test_init_db_creates_ports_table(in_memory_engine):
    inspector = inspect(in_memory_engine)
    assert "ports" in inspector.get_table_names()


@pytest.mark.unit()
def test_devices_table_columns(in_memory_engine):
    inspector = inspect(in_memory_engine)
    cols = {c["name"] for c in inspector.get_columns("devices")}
    assert {
        "id",
        "ip_address",
        "mac_address",
        "hostname",
        "os_guess",
        "first_seen",
        "last_seen",
    } <= cols


@pytest.mark.unit()
def test_ports_table_columns(in_memory_engine):
    inspector = inspect(in_memory_engine)
    cols = {c["name"] for c in inspector.get_columns("ports")}
    assert {"id", "device_id", "port_number", "protocol", "service_name", "version_banner"} <= cols


@pytest.mark.integration()
def test_get_db_yields_and_closes(in_memory_engine, monkeypatch):
    """get_db dependency yields a session and closes it after iteration."""
    from app import db as db_module

    test_session_factory = sessionmaker(bind=in_memory_engine)
    monkeypatch.setattr(db_module, "SessionLocal", test_session_factory)

    gen = db_module.get_db()
    session = next(gen)
    assert session is not None
    # Exhaust the generator to trigger the finally block (close)
    try:
        next(gen)
    except StopIteration:
        pass


@pytest.mark.integration()
def test_device_crud(in_memory_engine):
    """Basic Device create/read round-trip against in-memory DB."""
    from app.models.device import Device

    session_factory = sessionmaker(bind=in_memory_engine)
    with session_factory() as session:
        device = Device(ip_address="192.168.1.1", hostname="router")
        session.add(device)
        session.commit()
        session.refresh(device)

        fetched = session.get(Device, device.id)
        assert fetched.ip_address == "192.168.1.1"
        assert fetched.hostname == "router"


@pytest.mark.integration()
def test_port_crud_with_device(in_memory_engine):
    """Port linked to Device creates FK relationship correctly."""
    from app.models.device import Device, Port

    session_factory = sessionmaker(bind=in_memory_engine)
    with session_factory() as session:
        device = Device(ip_address="192.168.1.2")
        session.add(device)
        session.flush()

        port = Port(device_id=device.id, port_number=22, protocol="tcp", service_name="ssh")
        session.add(port)
        session.commit()

        fetched_port = session.get(Port, port.id)
        assert fetched_port.port_number == 22
        assert fetched_port.device_id == device.id


@pytest.mark.integration()
def test_device_cascade_deletes_ports(in_memory_engine):
    """Deleting a Device cascades to its Ports."""
    from app.models.device import Device, Port

    session_factory = sessionmaker(bind=in_memory_engine)
    with session_factory() as session:
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
