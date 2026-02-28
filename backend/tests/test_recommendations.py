"""
Unit and integration tests for the hardening recommendation engine and
/api/recommendations REST endpoints.

Markers:
  unit        — engine logic tests (no DB)
  integration — generate_recommendations / generate_all_recommendations with in-memory SQLite;
                REST endpoint tests via TestClient
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# ── Shared DB fixtures ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def db_engine():
    import app.models.device  # noqa: F401 — registers ORM metadata
    import app.models.recommendation  # noqa: F401 — registers ORM metadata
    import app.models.risk  # noqa: F401 — registers ORM metadata
    import app.models.scan  # noqa: F401 — registers ORM metadata
    from app.db import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention
    session = Session()
    yield session
    session.rollback()
    session.close()


def _seed_device_with_risk(session, *, ip: str, check_id: str, severity: str) -> tuple[int, int]:
    """Insert a Device + matching Risk; return (device_id, risk_id)."""
    from app.models.device import Device
    from app.models.risk import Risk

    device = Device(ip_address=ip)
    session.add(device)
    session.flush()

    risk = Risk(
        device_id=device.id,
        severity=severity,
        check_id=check_id,
        title="Test risk",
        description="Test description",
        detected_at=datetime.now(tz=UTC),
    )
    session.add(risk)
    session.flush()
    return device.id, risk.id


# ── Unit tests: catalogue coverage ───────────────────────────────────────────


@pytest.mark.unit
def test_catalogue_has_entry_for_every_check():
    """Every check_id produced by the analysis engine must have an advice entry."""
    from app.analysis.checks import ALL_CHECKS
    from app.recommendations import _CATALOGUE

    # Build the set of check_ids from the analysis module
    check_ids = set()
    for fn in ALL_CHECKS:
        # derive check_id from the function name: check_<id> → <id>
        name = fn.__name__
        assert name.startswith("check_"), f"Unexpected function name: {name}"
        check_ids.add(name[len("check_") :])

    missing = check_ids - set(_CATALOGUE.keys())
    assert not missing, f"No catalogue entry for check_ids: {missing}"


@pytest.mark.unit
def test_advice_entries_have_required_fields():
    """Each _Advice entry has non-empty steps, valid effort, and valid impact."""
    from app.recommendations import _CATALOGUE

    valid_levels = {"low", "medium", "high", "critical"}
    for check_id, advice in _CATALOGUE.items():
        assert advice.steps, f"{check_id}: steps must not be empty"
        assert advice.effort in valid_levels, f"{check_id}: invalid effort {advice.effort!r}"
        assert advice.impact in valid_levels, f"{check_id}: invalid impact {advice.impact!r}"
        assert advice.title, f"{check_id}: title must not be empty"
        assert advice.description, f"{check_id}: description must not be empty"


# ── Integration tests: generate_recommendations ───────────────────────────────


@pytest.mark.integration
def test_generate_recommendations_creates_recs_for_known_check(db_session):
    """generate_recommendations produces one Recommendation per Risk."""
    from app.recommendations import generate_recommendations

    device_id, _risk_id = _seed_device_with_risk(
        db_session, ip="10.1.0.1", check_id="telnet_open", severity="critical"
    )
    recs = generate_recommendations(db_session, device_id)
    db_session.commit()

    assert len(recs) == 1
    rec = recs[0]
    assert rec.device_id == device_id
    assert rec.check_id == "telnet_open"
    assert rec.severity == "critical"
    assert rec.effort in {"low", "medium", "high"}
    assert rec.impact in {"low", "medium", "high", "critical"}
    # steps must be valid JSON list
    steps = json.loads(rec.steps)
    assert isinstance(steps, list)
    assert len(steps) > 0


@pytest.mark.integration
def test_generate_recommendations_replaces_stale(db_session):
    """Re-running generate_recommendations replaces old rows rather than duplicating."""
    from app.recommendations import generate_recommendations

    device_id, _risk_id = _seed_device_with_risk(
        db_session, ip="10.1.0.2", check_id="ftp_open", severity="high"
    )

    # First run
    recs_first = generate_recommendations(db_session, device_id)
    db_session.commit()
    assert len(recs_first) == 1

    # Second run — should still produce exactly one recommendation
    recs_second = generate_recommendations(db_session, device_id)
    db_session.commit()
    assert len(recs_second) == 1


@pytest.mark.integration
def test_generate_recommendations_unknown_check_id_skipped(db_session, caplog):
    """An unknown check_id produces no recommendation and logs a warning."""
    import logging

    from app.recommendations import generate_recommendations

    device_id, _risk_id = _seed_device_with_risk(
        db_session, ip="10.1.0.3", check_id="nonexistent_check", severity="low"
    )

    with caplog.at_level(logging.WARNING, logger="app.recommendations"):
        recs = generate_recommendations(db_session, device_id)
    db_session.commit()

    assert recs == []
    assert any("nonexistent_check" in r.message for r in caplog.records)


@pytest.mark.integration
def test_generate_recommendations_device_not_found_returns_empty(db_session):
    """generate_recommendations for a non-existent device_id returns []."""
    from app.recommendations import generate_recommendations

    recs = generate_recommendations(db_session, 999999)
    assert recs == []


@pytest.mark.integration
def test_generate_all_recommendations(db_session):
    """generate_all_recommendations iterates all devices."""
    from app.recommendations import generate_all_recommendations

    device_id_a, _ = _seed_device_with_risk(
        db_session, ip="10.1.1.1", check_id="ssh_password_auth", severity="medium"
    )
    device_id_b, _ = _seed_device_with_risk(
        db_session, ip="10.1.1.2", check_id="smb_open", severity="high"
    )
    db_session.commit()

    total = generate_all_recommendations(db_session)
    # At least 2 (one per device seeded above; there may be more from earlier tests)
    assert total >= 2


@pytest.mark.integration
def test_generate_all_recommendations_multiple_risks_per_device(db_session):
    """A device with two risks gets two recommendations."""
    from app.models.device import Device
    from app.models.risk import Risk
    from app.recommendations import generate_recommendations

    device = Device(ip_address="10.1.2.1")
    db_session.add(device)
    db_session.flush()

    for check_id, severity in [("telnet_open", "critical"), ("ftp_open", "high")]:
        risk = Risk(
            device_id=device.id,
            severity=severity,
            check_id=check_id,
            title=f"{check_id} title",
            description=f"{check_id} description",
            detected_at=datetime.now(tz=UTC),
        )
        db_session.add(risk)
    db_session.flush()

    recs = generate_recommendations(db_session, device.id)
    db_session.commit()
    assert len(recs) == 2
    check_ids = {r.check_id for r in recs}
    assert check_ids == {"telnet_open", "ftp_open"}


# ── REST API integration tests ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def api_client(db_engine):
    """TestClient wired to the shared in-memory DB; scheduler disabled."""
    from app.db import get_db

    TestSession = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    with patch("apscheduler.schedulers.background.BackgroundScheduler.start"):
        with patch("apscheduler.schedulers.background.BackgroundScheduler.shutdown"):
            from app.main import app

            app.dependency_overrides[get_db] = override_get_db
            from fastapi.testclient import TestClient

            with TestClient(app) as c:
                yield c
            app.dependency_overrides.clear()


@pytest.fixture
def seeded_rec(db_engine):
    """Insert a Device + Risk + Recommendation; return their IDs."""
    from app.models.device import Device
    from app.models.recommendation import Recommendation
    from app.models.risk import Risk

    Session = sessionmaker(bind=db_engine)  # noqa: N806 — sessionmaker convention
    db = Session()

    device = Device(ip_address="10.2.0.1")
    db.add(device)
    db.flush()

    risk = Risk(
        device_id=device.id,
        severity="high",
        check_id="ftp_open",
        title="FTP port open",
        description="FTP is insecure.",
        detected_at=datetime.now(tz=UTC),
    )
    db.add(risk)
    db.flush()

    rec = Recommendation(
        device_id=device.id,
        risk_id=risk.id,
        check_id="ftp_open",
        severity="high",
        title="Replace FTP with SFTP or FTPS",
        description="FTP sends credentials in cleartext.",
        steps=json.dumps(["Disable FTP", "Enable SFTP"]),
        effort="medium",
        impact="high",
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    db.add(rec)
    db.commit()

    ids = {"device_id": device.id, "risk_id": risk.id, "rec_id": rec.id}
    yield ids

    db.delete(rec)
    db.delete(risk)
    db.delete(device)
    db.commit()
    db.close()


@pytest.mark.integration
def test_list_recommendations_empty(api_client):
    response = api_client.get("/api/recommendations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.integration
def test_list_recommendations_returns_seeded(api_client, seeded_rec):
    response = api_client.get("/api/recommendations")
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()]
    assert seeded_rec["rec_id"] in ids


@pytest.mark.integration
def test_list_recommendations_filter_by_device_id(api_client, seeded_rec):
    device_id = seeded_rec["device_id"]
    response = api_client.get(f"/api/recommendations?device_id={device_id}")
    assert response.status_code == 200
    data = response.json()
    assert all(r["device_id"] == device_id for r in data)


@pytest.mark.integration
def test_list_recommendations_filter_by_severity(api_client, seeded_rec):
    response = api_client.get("/api/recommendations?severity=high")
    assert response.status_code == 200
    data = response.json()
    assert all(r["severity"] == "high" for r in data)


@pytest.mark.integration
def test_list_recommendations_filter_no_match(api_client, seeded_rec):
    response = api_client.get("/api/recommendations?severity=critical")
    assert response.status_code == 200
    # The seeded rec is "high" so critical filter may return empty or other recs
    data = response.json()
    assert all(r["severity"] == "critical" for r in data)


@pytest.mark.integration
def test_get_recommendation_by_id(api_client, seeded_rec):
    rec_id = seeded_rec["rec_id"]
    response = api_client.get(f"/api/recommendations/{rec_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == rec_id
    assert data["check_id"] == "ftp_open"
    assert isinstance(data["steps"], list)
    assert len(data["steps"]) > 0
    assert "effort" in data
    assert "impact" in data


@pytest.mark.integration
def test_get_recommendation_not_found(api_client):
    response = api_client.get("/api/recommendations/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Recommendation not found"


@pytest.mark.integration
def test_device_recommendations_endpoint(api_client, seeded_rec):
    device_id = seeded_rec["device_id"]
    response = api_client.get(f"/api/devices/{device_id}/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert any(r["id"] == seeded_rec["rec_id"] for r in data)
    assert all(r["device_id"] == device_id for r in data)


@pytest.mark.integration
def test_device_recommendations_404_unknown_device(api_client):
    response = api_client.get("/api/devices/999999/recommendations")
    assert response.status_code == 404
    assert response.json()["detail"] == "Device not found"


@pytest.mark.integration
def test_recommendation_response_schema(api_client, seeded_rec):
    """Verify the full RecommendationOut schema fields are present and typed."""
    rec_id = seeded_rec["rec_id"]
    response = api_client.get(f"/api/recommendations/{rec_id}")
    assert response.status_code == 200
    data = response.json()
    required_fields = {
        "id",
        "device_id",
        "risk_id",
        "check_id",
        "severity",
        "title",
        "description",
        "steps",
        "effort",
        "impact",
        "created_at",
        "updated_at",
    }
    assert required_fields.issubset(data.keys())
    assert isinstance(data["steps"], list)
