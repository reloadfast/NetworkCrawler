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
    import app.models.recommendation  # noqa: F401 — side-effect import registers ORM tables
    import app.models.risk  # noqa: F401 — side-effect import registers ORM tables
    import app.models.scan  # noqa: F401 — side-effect import registers ORM tables
    import app.models.scan_event  # noqa: F401 — side-effect import registers ORM tables
    import app.models.settings  # noqa: F401 — side-effect import registers ORM tables
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
    assert "risks_critical" in scan
    assert "risks_high" in scan
    assert "risks_medium" in scan
    assert "risks_low" in scan


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
    assert "ip_address" in risk
    assert "hostname" in risk
    assert "severity" in risk
    assert "check_id" in risk
    assert "title" in risk
    assert "description" in risk
    assert "detected_at" in risk


@pytest.mark.integration
def test_risk_includes_device_identity(client, seeded_db, seeded_risk):
    """Risk response must include ip_address and hostname from the linked device."""
    response = client.get("/api/risks")
    risk = next(r for r in response.json() if r["id"] == seeded_risk["risk_id"])
    # seeded_db device has ip_address="10.0.0.1"
    assert risk["ip_address"] == "10.0.0.1"
    # hostname is nullable; assert the key is present with the correct type
    assert risk["hostname"] is None or isinstance(risk["hostname"], str)


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


# ── #47 severity query param validation ───────────────────────────────────────


def test_invalid_severity_returns_422(client):
    """Invalid severity value must return 422, not silently return empty list."""
    response = client.get("/api/risks?severity=bogus")
    assert response.status_code == 422


def test_valid_severities_return_200(client):
    """Each valid severity value must be accepted."""
    for sev in ("critical", "high", "medium", "low"):
        response = client.get(f"/api/risks?severity={sev}")
        assert response.status_code == 200, f"severity={sev} returned {response.status_code}"


# ── #48 malformed steps JSON in recommendations ───────────────────────────────


def test_malformed_steps_json_returns_empty_list(client, seeded_db, seeded_risk, db_engine):
    """Recommendation with malformed steps JSON must return 200 with steps=[]."""
    import sqlalchemy
    from app.models.recommendation import Recommendation  # noqa: PLC0415 — deferred import
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention; uppercase matches class naming
    db = Session()
    rec = Recommendation(
        device_id=seeded_db["device_id"],
        risk_id=seeded_risk["risk_id"],
        check_id="test_check",
        severity="low",
        title="Test rec",
        description="desc",
        steps="NOT VALID JSON {{{",
        effort="low",
        impact="low",
    )
    db.add(rec)
    db.commit()
    rec_id = rec.id
    db.close()

    try:
        response = client.get(f"/api/recommendations?device_id={seeded_db['device_id']}")
        assert response.status_code == 200
        data = response.json()
        target = next((r for r in data if r["id"] == rec_id), None)
        assert target is not None
        assert target["steps"] == []
    finally:
        Session2 = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention; uppercase matches class naming
        db2 = Session2()
        db2.execute(sqlalchemy.delete(Recommendation).where(Recommendation.id == rec_id))
        db2.commit()
        db2.close()


def test_empty_steps_returns_empty_list(client, seeded_db, seeded_risk, db_engine):
    """Recommendation with empty-string steps must return 200 with steps=[]."""
    import sqlalchemy
    from app.models.recommendation import Recommendation  # noqa: PLC0415 — deferred import
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention; uppercase matches class naming
    db = Session()
    rec = Recommendation(
        device_id=seeded_db["device_id"],
        risk_id=seeded_risk["risk_id"],
        check_id="test_check_empty",
        severity="low",
        title="Test rec empty",
        description="desc",
        steps="",
        effort="low",
        impact="low",
    )
    db.add(rec)
    db.commit()
    rec_id = rec.id
    db.close()

    try:
        response = client.get(f"/api/recommendations?device_id={seeded_db['device_id']}")
        assert response.status_code == 200
        data = response.json()
        target = next((r for r in data if r["id"] == rec_id), None)
        assert target is not None
        assert target["steps"] == []
    finally:
        Session2 = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention; uppercase matches class naming
        db2 = Session2()
        db2.execute(sqlalchemy.delete(Recommendation).where(Recommendation.id == rec_id))
        db2.commit()
        db2.close()


def test_patch_device_trusted_toggles_flag(client, seeded_db):
    """PATCH /api/devices/{id}/trusted should toggle the trusted field."""
    device_id = seeded_db["device_id"]

    # Default is untrusted
    resp = client.get(f"/api/devices/{device_id}")
    assert resp.status_code == 200
    assert resp.json()["trusted"] is False

    # Set trusted=True
    resp = client.patch(
        f"/api/devices/{device_id}/trusted",
        json={"trusted": True},
    )
    assert resp.status_code == 200
    assert resp.json()["trusted"] is True

    # Set back to False
    resp = client.patch(
        f"/api/devices/{device_id}/trusted",
        json={"trusted": False},
    )
    assert resp.status_code == 200
    assert resp.json()["trusted"] is False


def test_patch_device_trusted_404_for_unknown(client):
    """PATCH /api/devices/{id}/trusted returns 404 for non-existent device."""
    resp = client.patch("/api/devices/999999/trusted", json={"trusted": True})
    assert resp.status_code == 404


def test_scan_response_includes_current_stage(client, seeded_db):
    """GET /api/scans response must include the current_stage field (may be null)."""
    resp = client.get("/api/scans")
    assert resp.status_code == 200
    data = resp.json()
    # The field must be present on every scan record (value may be null)
    for scan in data:
        assert "current_stage" in scan


# ── /api/settings/checklist ───────────────────────────────────────────────────


def test_get_checklist_returns_default_unknown(client):
    """GET /api/settings/checklist returns 8 items all answered 'unknown' by default."""
    resp = client.get("/api/settings/checklist")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 8
    assert all(it["answer"] == "unknown" for it in data["items"])
    assert data["yes_count"] == 0
    assert data["posture"] == "at_risk"


def test_post_checklist_saves_answer(client):
    """POST /api/settings/checklist persists a yes answer and updates posture."""
    resp = client.post(
        "/api/settings/checklist",
        json={"answers": {"checklist_upnp_disabled": "yes"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    upnp = next(it for it in data["items"] if it["key"] == "checklist_upnp_disabled")
    assert upnp["answer"] == "yes"
    assert data["yes_count"] == 1


def test_post_checklist_full_yes_returns_hardened(client):
    """Answering yes to all 8 questions should return posture='hardened'."""
    keys = [
        "checklist_upnp_disabled",
        "checklist_wps_disabled",
        "checklist_wifi_wpa2_or_better",
        "checklist_admin_wan_blocked",
        "checklist_iot_network_isolated",
        "checklist_firmware_updated",
        "checklist_unique_passwords",
        "checklist_remote_mgmt_disabled",
    ]
    resp = client.post(
        "/api/settings/checklist",
        json={"answers": dict.fromkeys(keys, "yes")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["yes_count"] == 8
    assert data["posture"] == "hardened"
    assert data["posture_label"] == "Hardened"


def test_post_checklist_ignores_invalid_keys(client):
    """POST /api/settings/checklist silently ignores unknown keys."""
    # Reset all answers first (state shared across module-scoped DB)
    client.post(
        "/api/settings/checklist",
        json={"answers": {"checklist_upnp_disabled": "unknown"}},
    )
    resp = client.post(
        "/api/settings/checklist",
        json={"answers": {"not_a_real_key": "yes"}},
    )
    assert resp.status_code == 200
    upnp = next(it for it in resp.json()["items"] if it["key"] == "checklist_upnp_disabled")
    assert upnp["answer"] == "unknown"


def test_post_checklist_ignores_invalid_values(client):
    """POST /api/settings/checklist silently ignores invalid answer values."""
    resp = client.post(
        "/api/settings/checklist",
        json={"answers": {"checklist_upnp_disabled": "maybe"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    upnp = next(it for it in data["items"] if it["key"] == "checklist_upnp_disabled")
    assert upnp["answer"] == "unknown"


# ── /api/settings — network_profile ──────────────────────────────────────────


def test_get_settings_includes_network_profile(client):
    """GET /api/settings returns network_profile field (defaults to standard_home)."""
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "network_profile" in data
    assert data["network_profile"] == "standard_home"


def test_patch_settings_updates_network_profile(client):
    """PATCH /api/settings with network_profile persists the value."""
    resp = client.patch("/api/settings", json={"network_profile": "home_lab"})
    assert resp.status_code == 200
    assert resp.json()["network_profile"] == "home_lab"

    # reset
    client.patch("/api/settings", json={"network_profile": "standard_home"})


def test_patch_settings_ignores_invalid_network_profile(client):
    """PATCH /api/settings silently ignores unknown profile values."""
    resp = client.patch("/api/settings", json={"network_profile": "not_a_profile"})
    assert resp.status_code == 200
    # profile should remain unchanged (standard_home default)
    assert resp.json()["network_profile"] == "standard_home"


def test_risk_display_severity_present(client, seeded_db):
    """GET /api/risks returns display_severity field on every risk."""
    resp = client.get("/api/risks")
    assert resp.status_code == 200
    for risk in resp.json():
        assert "display_severity" in risk


def test_risk_display_severity_overridden_by_home_lab(client, db_engine, seeded_db):
    """With home_lab profile, open_ssh risk has display_severity=low."""

    from app.models.risk import Risk

    S = sessionmaker(bind=db_engine)  # noqa: N806 -- uppercase matches SQLAlchemy Session convention
    db = S()
    device_id = seeded_db["device_id"]
    risk = Risk(
        device_id=device_id,
        severity="high",
        check_id="open_ssh",
        title="SSH open",
        description="SSH port is open",
    )
    db.add(risk)
    db.commit()

    client.patch("/api/settings", json={"network_profile": "home_lab"})
    resp = client.get("/api/risks")
    client.patch("/api/settings", json={"network_profile": "standard_home"})

    db.delete(risk)
    db.commit()
    db.close()

    ssh_risks = [r for r in resp.json() if r["check_id"] == "open_ssh"]
    assert len(ssh_risks) == 1
    assert ssh_risks[0]["severity"] == "high"
    assert ssh_risks[0]["display_severity"] == "low"


# ── /api/insights/segmentation ────────────────────────────────────────────────


def test_segmentation_no_devices_returns_not_flat(client):
    """GET /api/insights/segmentation returns flat_network=false when no devices."""
    resp = client.get("/api/insights/segmentation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["flat_network"] is False
    assert data["iot_count"] == 0
    assert data["server_count"] == 0
    assert data["mixed_risk_pairs"] == []
    assert data["recommendations"] == []


def test_segmentation_only_iot_not_flat(client, db_engine):
    """GET /api/insights/segmentation is not flat when only IoT devices, no servers."""
    from app.models.device import Device
    from sqlalchemy.orm import (
        sessionmaker as sm,  # noqa: N806 — uppercase Session is SQLAlchemy convention
    )

    Session = sm(bind=db_engine)  # noqa: N806 — uppercase Session is SQLAlchemy convention
    db = Session()
    d = Device(ip_address="192.168.1.50", device_type="iot")
    db.add(d)
    db.commit()

    resp = client.get("/api/insights/segmentation")
    data = resp.json()
    assert data["flat_network"] is False
    assert data["iot_count"] == 1

    db.delete(d)
    db.commit()
    db.close()


def test_segmentation_mixed_iot_server_is_flat(client, db_engine):
    """GET /api/insights/segmentation detects flat network with IoT + server."""
    from app.models.device import Device
    from sqlalchemy.orm import (
        sessionmaker as sm,  # noqa: N806 — uppercase Session is SQLAlchemy convention
    )

    Session = sm(bind=db_engine)  # noqa: N806 — uppercase Session is SQLAlchemy convention
    db = Session()
    iot = Device(ip_address="192.168.1.60", device_type="iot")
    srv = Device(ip_address="192.168.1.100", device_type="server")
    db.add_all([iot, srv])
    db.commit()

    resp = client.get("/api/insights/segmentation")
    data = resp.json()
    assert data["flat_network"] is True
    assert data["iot_count"] == 1
    assert data["server_count"] == 1
    assert len(data["recommendations"]) == 3

    db.delete(iot)
    db.delete(srv)
    db.commit()
    db.close()


def test_segmentation_mixed_risk_pair_detected(client, db_engine):
    """GET /api/insights/segmentation detects mixed_risk_pairs when IoT has open ports."""
    from app.models.device import Device, Port
    from sqlalchemy.orm import (
        sessionmaker as sm,  # noqa: N806 — uppercase Session is SQLAlchemy convention
    )

    Session = sm(bind=db_engine)  # noqa: N806 — uppercase Session is SQLAlchemy convention
    db = Session()
    iot = Device(ip_address="10.1.1.10", device_type="iot")
    db.add(iot)
    db.flush()
    p = Port(device_id=iot.id, port_number=8080, protocol="tcp")
    db.add(p)
    srv = Device(ip_address="10.1.1.20", device_type="server")
    db.add(srv)
    db.commit()

    resp = client.get("/api/insights/segmentation")
    data = resp.json()
    assert data["flat_network"] is True
    assert len(data["mixed_risk_pairs"]) == 1
    pair = data["mixed_risk_pairs"][0]
    assert pair["iot_ip"] == "10.1.1.10"
    assert pair["server_ip"] == "10.1.1.20"
    assert pair["shared_subnet"] == "10.1.1.0/24"

    db.delete(p)
    db.delete(iot)
    db.delete(srv)
    db.commit()
    db.close()


# ── /api/topology ──────────────────────────────────────────────────────────────


def test_topology_empty(client):
    """GET /api/topology returns empty list when no devices."""
    resp = client.get("/api/topology")
    assert resp.status_code == 200
    assert resp.json() == []


def test_topology_returns_nodes(client, seeded_db):
    """GET /api/topology returns one node per device with required fields."""
    resp = client.get("/api/topology")
    assert resp.status_code == 200
    nodes = resp.json()
    assert len(nodes) >= 1
    node = nodes[0]
    for field in ("id", "ip_address", "device_type", "port_count", "security_score", "is_gateway"):
        assert field in node, f"missing field: {field}"


def test_topology_gateway_detection_by_ip(client, db_engine):
    """GET /api/topology marks device ending in .1 as gateway."""
    from app.models.device import Device

    S = sessionmaker(bind=db_engine)  # noqa: N806 -- uppercase matches SQLAlchemy Session convention
    db = S()
    gw = Device(ip_address="192.168.1.1", device_type="unknown")
    other = Device(ip_address="192.168.1.50", device_type="workstation")
    db.add_all([gw, other])
    db.commit()

    resp = client.get("/api/topology")
    nodes = {n["ip_address"]: n for n in resp.json()}
    assert nodes["192.168.1.1"]["is_gateway"] is True
    assert nodes["192.168.1.50"]["is_gateway"] is False

    db.delete(gw)
    db.delete(other)
    db.commit()
    db.close()


def test_topology_gateway_detection_by_type(client, db_engine):
    """GET /api/topology marks device with device_type=router as gateway."""
    from app.models.device import Device

    S = sessionmaker(bind=db_engine)  # noqa: N806 -- uppercase matches SQLAlchemy Session convention
    db = S()
    router = Device(ip_address="10.0.0.254", device_type="router")
    db.add(router)
    db.commit()

    resp = client.get("/api/topology")
    nodes = {n["ip_address"]: n for n in resp.json()}
    assert nodes["10.0.0.254"]["is_gateway"] is True

    db.delete(router)
    db.commit()
    db.close()


# ── /api/network/wan ──────────────────────────────────────────────────────────


def test_wan_no_data(client):
    """GET /api/network/wan returns nulls when no WAN IP has been recorded."""
    resp = client.get("/api/network/wan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["wan_ip"] is None
    assert body["detected_at"] is None


def test_wan_returns_stored_ip(client, db_engine):
    """GET /api/network/wan returns the IP and timestamp stored in AppSettings."""
    from app.models.settings import AppSetting

    S = sessionmaker(bind=db_engine)  # noqa: N806 -- uppercase matches SQLAlchemy Session convention
    db = S()
    db.add(AppSetting(key="wan_ip", value="203.0.113.42"))
    db.add(AppSetting(key="wan_ip_detected_at", value="2026-03-02T12:00:00+00:00"))
    db.commit()

    resp = client.get("/api/network/wan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["wan_ip"] == "203.0.113.42"
    assert body["detected_at"] == "2026-03-02T12:00:00+00:00"

    db.query(AppSetting).filter(AppSetting.key.in_(["wan_ip", "wan_ip_detected_at"])).delete()
    db.commit()
    db.close()
