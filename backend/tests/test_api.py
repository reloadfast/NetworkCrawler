"""
Integration tests for the REST API endpoints.

Uses an in-memory SQLite DB via dependency override and mocks orchestrate_scan
so no real network I/O occurs.

Markers: integration
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def db_engine():
    import app.models.device  # noqa: F401
    import app.models.scan  # noqa: F401
    from app.db import Base

    # StaticPool keeps a single underlying connection so all sessions share
    # the same in-memory database (required for SQLite :memory:).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def client(db_engine):
    """TestClient wired to in-memory DB; scheduler disabled."""
    from app.db import get_db

    TestSession = sessionmaker(bind=db_engine)  # noqa: N806

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    # Patch scheduler so it never fires during tests
    with patch("apscheduler.schedulers.background.BackgroundScheduler.start"):
        with patch("apscheduler.schedulers.background.BackgroundScheduler.shutdown"):
            from app.main import app

            app.dependency_overrides[get_db] = override_get_db
            with TestClient(app) as c:
                yield c
            app.dependency_overrides.clear()


@pytest.fixture
def seeded_db(db_engine):
    """Insert a known device + port + scan and return their IDs."""
    from app.models.device import Device, Port
    from app.models.scan import Scan

    Session = sessionmaker(bind=db_engine)  # noqa: N806
    db = Session()

    device = Device(
        ip_address="10.0.0.1",
        mac_address="aa:bb:cc:dd:ee:ff",
        vendor="Acme",
        hostname="testhost",
    )
    db.add(device)
    db.flush()

    port = Port(device_id=device.id, port_number=22, protocol="tcp", service_name="ssh")
    db.add(port)

    now = datetime.now(tz=UTC)
    scan = Scan(
        status="completed",
        triggered_by="manual",
        started_at=now,
        finished_at=now,
        duration_seconds=1.5,
        devices_found=1,
    )
    db.add(scan)
    db.commit()

    ids = {"device_id": device.id, "port_id": port.id, "scan_id": scan.id}
    yield ids

    # cleanup
    db.delete(port)
    db.delete(device)
    db.delete(scan)
    db.commit()
    db.close()


# ── GET /api/devices ──────────────────────────────────────────────────────────


@pytest.mark.integration
def test_list_devices_empty(client):
    response = client.get("/api/devices")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.integration
def test_list_devices_returns_seeded(client, seeded_db):
    response = client.get("/api/devices")
    assert response.status_code == 200
    data = response.json()
    ips = [d["ip_address"] for d in data]
    assert "10.0.0.1" in ips


@pytest.mark.integration
def test_list_devices_includes_ports(client, seeded_db):
    response = client.get("/api/devices")
    assert response.status_code == 200
    devices = response.json()
    device = next(d for d in devices if d["ip_address"] == "10.0.0.1")
    assert len(device["ports"]) >= 1
    assert device["ports"][0]["port_number"] == 22


@pytest.mark.integration
def test_device_schema_fields(client, seeded_db):
    response = client.get("/api/devices")
    device = next(d for d in response.json() if d["ip_address"] == "10.0.0.1")
    assert "id" in device
    assert "mac_address" in device
    assert "vendor" in device
    assert "hostname" in device
    assert "first_seen" in device
    assert "last_seen" in device


# ── GET /api/devices/{id} ─────────────────────────────────────────────────────


@pytest.mark.integration
def test_get_device_by_id(client, seeded_db):
    device_id = seeded_db["device_id"]
    response = client.get(f"/api/devices/{device_id}")
    assert response.status_code == 200
    assert response.json()["ip_address"] == "10.0.0.1"


@pytest.mark.integration
def test_get_device_not_found(client):
    response = client.get("/api/devices/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Device not found"


@pytest.mark.integration
def test_get_device_includes_ports(client, seeded_db):
    device_id = seeded_db["device_id"]
    response = client.get(f"/api/devices/{device_id}")
    assert response.status_code == 200
    ports = response.json()["ports"]
    assert any(p["port_number"] == 22 for p in ports)


# ── GET /api/scans ────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_list_scans_returns_seeded(client, seeded_db):
    response = client.get("/api/scans")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(s["triggered_by"] == "manual" for s in data)


@pytest.mark.integration
def test_scan_schema_fields(client, seeded_db):
    response = client.get("/api/scans")
    scan = next(s for s in response.json() if s["triggered_by"] == "manual")
    assert "id" in scan
    assert "status" in scan
    assert "started_at" in scan
    assert "finished_at" in scan
    assert "duration_seconds" in scan
    assert "devices_found" in scan


# ── POST /api/scans/trigger ───────────────────────────────────────────────────


@pytest.mark.integration
def test_trigger_scan_returns_202(client):
    with patch("app.scan_runner.run_scan_and_persist") as mock_run:
        mock_run.return_value = 42
        response = client.post("/api/scans/trigger")
    assert response.status_code == 202


@pytest.mark.integration
def test_trigger_scan_response_body(client):
    with patch("app.scan_runner.run_scan_and_persist"):
        response = client.post("/api/scans/trigger")
    assert "message" in response.json()
    assert response.json()["message"] == "Scan enqueued"


# ── Security headers ──────────────────────────────────────────────────────────


@pytest.mark.integration
def test_security_header_x_content_type(client):
    response = client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"


@pytest.mark.integration
def test_security_header_x_frame_options(client):
    response = client.get("/health")
    assert response.headers.get("x-frame-options") == "DENY"


@pytest.mark.integration
def test_security_header_csp(client):
    response = client.get("/health")
    assert "default-src" in response.headers.get("content-security-policy", "")
