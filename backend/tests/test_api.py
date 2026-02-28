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
    import app.models.device  # noqa: F401 — side-effect import registers ORM tables
    import app.models.risk  # noqa: F401 — side-effect import registers ORM tables
    import app.models.scan  # noqa: F401 — side-effect import registers ORM tables
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

    TestSession = sessionmaker(bind=db_engine)  # noqa: N806 — PEP-8 class name; sessionmaker convention

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

    Session = sessionmaker(bind=db_engine)  # noqa: N806 — PEP-8 class name; sessionmaker convention
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


# ── /api/risks ────────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_risk(db_engine, seeded_db):
    """Insert a Risk row tied to the seeded device and return its ID."""
    from datetime import UTC, datetime

    from app.models.risk import Risk

    Session = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention
    db = Session()
    risk = Risk(
        device_id=seeded_db["device_id"],
        severity="critical",
        check_id="telnet_open",
        title="Telnet port open",
        description="Test risk description",
        detected_at=datetime.now(tz=UTC),
    )
    db.add(risk)
    db.commit()
    risk_id = risk.id
    yield {"risk_id": risk_id}
    db.execute(__import__("sqlalchemy").delete(Risk).where(Risk.id == risk_id))
    db.commit()
    db.close()


@pytest.mark.integration
def test_list_risks_returns_list(client):
    response = client.get("/api/risks")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.integration
def test_list_risks_returns_seeded(client, seeded_risk):
    response = client.get("/api/risks")
    assert response.status_code == 200
    data = response.json()
    risk_ids = [r["id"] for r in data]
    assert seeded_risk["risk_id"] in risk_ids


@pytest.mark.integration
def test_risk_schema_fields(client, seeded_risk):
    response = client.get("/api/risks")
    risk = next(r for r in response.json() if r["id"] == seeded_risk["risk_id"])
    assert "id" in risk
    assert "device_id" in risk
    assert "severity" in risk
    assert "check_id" in risk
    assert "title" in risk
    assert "description" in risk
    assert "detected_at" in risk


@pytest.mark.integration
def test_get_risk_by_id(client, seeded_risk):
    risk_id = seeded_risk["risk_id"]
    response = client.get(f"/api/risks/{risk_id}")
    assert response.status_code == 200
    assert response.json()["check_id"] == "telnet_open"
    assert response.json()["severity"] == "critical"


@pytest.mark.integration
def test_get_risk_not_found(client):
    response = client.get("/api/risks/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Risk not found"


@pytest.mark.integration
def test_risks_summary_returns_counts(client, seeded_risk):
    response = client.get("/api/risks/summary")
    assert response.status_code == 200
    data = response.json()
    assert "critical" in data
    assert "high" in data
    assert "medium" in data
    assert "low" in data
    assert "total" in data
    assert data["critical"] >= 1
    assert data["total"] >= 1


@pytest.mark.integration
def test_device_risks_endpoint(client, seeded_db, seeded_risk):
    device_id = seeded_db["device_id"]
    response = client.get(f"/api/devices/{device_id}/risks")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    risk_ids = [r["id"] for r in data]
    assert seeded_risk["risk_id"] in risk_ids


@pytest.mark.integration
def test_device_risks_404_for_unknown_device(client):
    response = client.get("/api/devices/999999/risks")
    assert response.status_code == 404


@pytest.mark.integration
def test_list_risks_filter_by_severity(client, seeded_db, db_engine):
    """Risks can be filtered to a specific severity level."""
    from app.models.risk import Risk

    Session = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention; uppercase matches class naming
    db = Session()
    high_risk = Risk(
        device_id=seeded_db["device_id"],
        severity="high",
        check_id="ftp_open",
        title="FTP port open",
        description="FTP is open",
        detected_at=__import__("datetime").datetime.now(tz=__import__("datetime").timezone.utc),
    )
    db.add(high_risk)
    db.commit()
    high_id = high_risk.id
    db.close()

    try:
        response = client.get("/api/risks?severity=high")
        assert response.status_code == 200
        data = response.json()
        assert all(r["severity"] == "high" for r in data)
        assert any(r["id"] == high_id for r in data)

        response_critical = client.get("/api/risks?severity=critical")
        assert response_critical.status_code == 200
        assert all(r["severity"] == "critical" for r in response_critical.json())
    finally:
        Session2 = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention; uppercase matches class naming
        db2 = Session2()
        db2.execute(__import__("sqlalchemy").delete(Risk).where(Risk.id == high_id))
        db2.commit()
        db2.close()


@pytest.mark.integration
def test_list_risks_filter_by_device_id(client, seeded_db, db_engine):
    """Risks can be filtered to a specific device."""
    from app.models.device import Device
    from app.models.risk import Risk

    Session = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention; uppercase matches class naming
    db = Session()

    # Create a second device with its own risk
    other_device = Device(ip_address="10.0.0.99", mac_address=None, vendor="Other")
    db.add(other_device)
    db.flush()
    other_risk = Risk(
        device_id=other_device.id,
        severity="low",
        check_id="outdated_banner",
        title="Outdated banner",
        description="Old version",
        detected_at=__import__("datetime").datetime.now(tz=__import__("datetime").timezone.utc),
    )
    db.add(other_risk)
    db.commit()
    other_device_id = other_device.id
    other_risk_id = other_risk.id
    db.close()

    try:
        response = client.get(f"/api/risks?device_id={seeded_db['device_id']}")
        assert response.status_code == 200
        data = response.json()
        assert all(r["device_id"] == seeded_db["device_id"] for r in data)

        response_other = client.get(f"/api/risks?device_id={other_device_id}")
        assert response_other.status_code == 200
        other_data = response_other.json()
        assert any(r["id"] == other_risk_id for r in other_data)
        assert all(r["device_id"] == other_device_id for r in other_data)
    finally:
        Session2 = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention; uppercase matches class naming
        db2 = Session2()
        db2.execute(__import__("sqlalchemy").delete(Risk).where(Risk.id == other_risk_id))
        db2.execute(__import__("sqlalchemy").delete(Device).where(Device.id == other_device_id))
        db2.commit()
        db2.close()


@pytest.mark.integration
def test_list_risks_filter_by_severity_and_device_id(client, seeded_db, db_engine):
    """Both severity and device_id filters can be combined."""
    from app.models.risk import Risk

    Session = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention; uppercase matches class naming
    db = Session()
    risk = Risk(
        device_id=seeded_db["device_id"],
        severity="medium",
        check_id="upnp_exposed",
        title="UPnP exposed",
        description="UPnP open",
        detected_at=__import__("datetime").datetime.now(tz=__import__("datetime").timezone.utc),
    )
    db.add(risk)
    db.commit()
    risk_id = risk.id
    db.close()

    try:
        response = client.get(f"/api/risks?severity=medium&device_id={seeded_db['device_id']}")
        assert response.status_code == 200
        data = response.json()
        assert all(r["severity"] == "medium" for r in data)
        assert all(r["device_id"] == seeded_db["device_id"] for r in data)
        assert any(r["id"] == risk_id for r in data)
    finally:
        Session2 = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention; uppercase matches class naming
        db2 = Session2()
        db2.execute(__import__("sqlalchemy").delete(Risk).where(Risk.id == risk_id))
        db2.commit()
        db2.close()
