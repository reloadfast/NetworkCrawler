"""
Unit and integration tests for app/analysis/ — checks engine and run_checks orchestrator.

Markers:
  unit        — pure check function tests (no DB)
  integration — run_checks / run_all_checks with in-memory SQLite
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Helpers to build mock Device objects ─────────────────────────────────────


def _make_port(
    port_number: int, protocol: str = "tcp", service_name: str = "", version_banner: str = ""
):
    p = MagicMock()
    p.port_number = port_number
    p.protocol = protocol
    p.service_name = service_name
    p.version_banner = version_banner
    return p


def _make_device(
    ip: str = "192.168.1.10",
    vendor: str = "",
    hostname: str = "",
    os_guess: str = "",
    ports=None,
):
    d = MagicMock()
    d.ip_address = ip
    d.vendor = vendor
    d.hostname = hostname
    d.os_guess = os_guess
    d.ports = ports or []
    return d


# ── DB fixture (shared across integration tests) ──────────────────────────────


@pytest.fixture(scope="module")
def db_engine():
    import app.models.device  # noqa: F401 — registers ORM metadata
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


# ── check_telnet_open ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_telnet_open_fires_on_port_23():
    from app.analysis.checks import check_telnet_open

    device = _make_device(ports=[_make_port(23)])
    results = check_telnet_open(device)
    assert len(results) == 1
    assert results[0].check_id == "telnet_open"
    assert results[0].severity == "critical"


@pytest.mark.unit
def test_telnet_open_no_finding_without_port_23():
    from app.analysis.checks import check_telnet_open

    device = _make_device(ports=[_make_port(22), _make_port(80)])
    assert check_telnet_open(device) == []


@pytest.mark.unit
def test_telnet_open_no_finding_empty_ports():
    from app.analysis.checks import check_telnet_open

    assert check_telnet_open(_make_device()) == []


# ── check_ftp_open ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_ftp_open_fires_on_port_21():
    from app.analysis.checks import check_ftp_open

    device = _make_device(ports=[_make_port(21)])
    results = check_ftp_open(device)
    assert len(results) == 1
    assert results[0].check_id == "ftp_open"
    assert results[0].severity == "high"


@pytest.mark.unit
def test_ftp_open_no_finding_without_port_21():
    from app.analysis.checks import check_ftp_open

    assert check_ftp_open(_make_device(ports=[_make_port(22)])) == []


# ── check_unencrypted_http ────────────────────────────────────────────────────


@pytest.mark.unit
def test_http_check_fires_when_service_is_http():
    from app.analysis.checks import check_unencrypted_http

    device = _make_device(ports=[_make_port(80, service_name="http")])
    results = check_unencrypted_http(device)
    assert len(results) == 1
    assert results[0].check_id == "unencrypted_http"
    assert results[0].severity == "medium"


@pytest.mark.unit
def test_http_check_fires_when_banner_contains_nginx():
    from app.analysis.checks import check_unencrypted_http

    device = _make_device(ports=[_make_port(80, service_name="", version_banner="nginx 1.24.0")])
    results = check_unencrypted_http(device)
    assert len(results) == 1


@pytest.mark.unit
def test_http_check_no_finding_when_no_port_80():
    from app.analysis.checks import check_unencrypted_http

    assert check_unencrypted_http(_make_device(ports=[_make_port(443)])) == []


@pytest.mark.unit
def test_http_check_no_finding_when_service_not_mgmt():
    from app.analysis.checks import check_unencrypted_http

    # Port 80 open but service gives no management hint
    device = _make_device(ports=[_make_port(80, service_name="unknown", version_banner="")])
    assert check_unencrypted_http(device) == []


# ── check_upnp_exposed ────────────────────────────────────────────────────────


@pytest.mark.unit
def test_upnp_fires_on_non_router_device():
    from app.analysis.checks import check_upnp_exposed

    device = _make_device(vendor="SomeIoTCo", ports=[_make_port(1900, protocol="udp")])
    results = check_upnp_exposed(device)
    assert len(results) == 1
    assert results[0].check_id == "upnp_exposed"
    assert results[0].severity == "medium"


@pytest.mark.unit
def test_upnp_no_finding_for_router():
    from app.analysis.checks import check_upnp_exposed

    device = _make_device(vendor="Netgear Inc", ports=[_make_port(1900, protocol="udp")])
    assert check_upnp_exposed(device) == []


@pytest.mark.unit
def test_upnp_no_finding_when_port_missing():
    from app.analysis.checks import check_upnp_exposed

    assert check_upnp_exposed(_make_device(vendor="SomeIoTCo")) == []


# ── check_ssh_password_auth ───────────────────────────────────────────────────


@pytest.mark.unit
def test_ssh_check_fires_when_ssh_service_present():
    from app.analysis.checks import check_ssh_password_auth

    device = _make_device(ports=[_make_port(22, service_name="ssh", version_banner="OpenSSH 8.9")])
    results = check_ssh_password_auth(device)
    assert len(results) == 1
    assert results[0].check_id == "ssh_password_auth"
    assert results[0].severity == "medium"


@pytest.mark.unit
def test_ssh_check_no_finding_when_no_port_22():
    from app.analysis.checks import check_ssh_password_auth

    assert check_ssh_password_auth(_make_device(ports=[_make_port(80)])) == []


@pytest.mark.unit
def test_ssh_check_no_finding_when_non_ssh_service_on_22():
    from app.analysis.checks import check_ssh_password_auth

    # Port 22 but service_name is neither 'ssh' nor 'openssh'
    device = _make_device(ports=[_make_port(22, service_name="unknown", version_banner="")])
    assert check_ssh_password_auth(device) == []


# ── check_smb_open ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_smb_fires_on_port_445():
    from app.analysis.checks import check_smb_open

    device = _make_device(ports=[_make_port(445)])
    results = check_smb_open(device)
    assert len(results) == 1
    assert results[0].check_id == "smb_open"
    assert results[0].severity == "high"


@pytest.mark.unit
def test_smb_fires_on_netbios_ports():
    from app.analysis.checks import check_smb_open

    device = _make_device(ports=[_make_port(137), _make_port(138), _make_port(139)])
    results = check_smb_open(device)
    assert len(results) == 1


@pytest.mark.unit
def test_smb_no_finding_for_nas():
    from app.analysis.checks import check_smb_open

    device = _make_device(os_guess="Synology DiskStation", ports=[_make_port(445)])
    assert check_smb_open(device) == []


@pytest.mark.unit
def test_smb_no_finding_without_smb_ports():
    from app.analysis.checks import check_smb_open

    assert check_smb_open(_make_device(ports=[_make_port(22)])) == []


# ── check_printer_iot_admin ───────────────────────────────────────────────────


@pytest.mark.unit
def test_printer_iot_fires_for_hp_printer():
    from app.analysis.checks import check_printer_iot_admin

    device = _make_device(vendor="HP Inc", ports=[_make_port(80, service_name="http")])
    results = check_printer_iot_admin(device)
    assert len(results) == 1
    assert results[0].check_id == "printer_iot_admin"
    assert results[0].severity == "medium"


@pytest.mark.unit
def test_printer_iot_fires_for_hikvision_camera():
    from app.analysis.checks import check_printer_iot_admin

    device = _make_device(vendor="Hikvision", ports=[_make_port(8080)])
    results = check_printer_iot_admin(device)
    assert len(results) == 1


@pytest.mark.unit
def test_printer_iot_no_finding_for_unknown_vendor():
    from app.analysis.checks import check_printer_iot_admin

    device = _make_device(vendor="Unknown Corp", ports=[_make_port(80)])
    assert check_printer_iot_admin(device) == []


@pytest.mark.unit
def test_printer_iot_no_finding_without_admin_ports():
    from app.analysis.checks import check_printer_iot_admin

    device = _make_device(vendor="Canon", ports=[_make_port(9100)])  # printer data port, not admin
    assert check_printer_iot_admin(device) == []


# ── check_outdated_banner ─────────────────────────────────────────────────────


@pytest.mark.unit
def test_outdated_banner_fires_for_old_openssh():
    from app.analysis.checks import check_outdated_banner

    device = _make_device(ports=[_make_port(22, version_banner="OpenSSH 5.9 Ubuntu")])
    results = check_outdated_banner(device)
    assert len(results) == 1
    assert results[0].check_id == "outdated_banner"
    assert results[0].severity == "low"


@pytest.mark.unit
def test_outdated_banner_fires_for_old_apache():
    from app.analysis.checks import check_outdated_banner

    device = _make_device(ports=[_make_port(80, version_banner="Apache/2.2.31")])
    results = check_outdated_banner(device)
    assert len(results) == 1


@pytest.mark.unit
def test_outdated_banner_no_finding_for_modern_openssh():
    from app.analysis.checks import check_outdated_banner

    device = _make_device(ports=[_make_port(22, version_banner="OpenSSH 8.9 Ubuntu")])
    assert check_outdated_banner(device) == []


@pytest.mark.unit
def test_outdated_banner_no_finding_when_no_banner():
    from app.analysis.checks import check_outdated_banner

    device = _make_device(ports=[_make_port(22, version_banner="")])
    assert check_outdated_banner(device) == []


@pytest.mark.unit
def test_outdated_banner_multiple_ports_multiple_findings():
    from app.analysis.checks import check_outdated_banner

    device = _make_device(
        ports=[
            _make_port(22, version_banner="OpenSSH 5.3"),
            _make_port(21, version_banner="vsftpd 2.0.8"),
        ]
    )
    results = check_outdated_banner(device)
    assert len(results) == 2


# ── check_rdp_exposed ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_check_rdp_exposed_returns_risk():
    from app.analysis.checks import check_rdp_exposed

    device = _make_device(ports=[_make_port(3389)])
    results = check_rdp_exposed(device)
    assert len(results) == 1
    assert results[0].check_id == "rdp_exposed"
    assert results[0].severity == "high"


@pytest.mark.unit
def test_check_rdp_no_risk_when_port_closed():
    from app.analysis.checks import check_rdp_exposed

    assert check_rdp_exposed(_make_device(ports=[_make_port(22)])) == []


# ── check_vnc_exposed ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_check_vnc_exposed_returns_risk():
    from app.analysis.checks import check_vnc_exposed

    device = _make_device(ports=[_make_port(5900)])
    results = check_vnc_exposed(device)
    assert len(results) == 1
    assert results[0].check_id == "vnc_exposed"
    assert results[0].severity == "high"


# ── check_mqtt_open ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_check_mqtt_open_returns_risk():
    from app.analysis.checks import check_mqtt_open

    device = _make_device(ports=[_make_port(1883)])
    results = check_mqtt_open(device)
    assert len(results) == 1
    assert results[0].check_id == "mqtt_open"
    assert results[0].severity == "medium"


# ── check_open_dns_resolver ───────────────────────────────────────────────────


@pytest.mark.unit
def test_check_open_dns_resolver_returns_risk_tcp():
    from app.analysis.checks import check_open_dns_resolver

    device = _make_device(ports=[_make_port(53, protocol="tcp")])
    results = check_open_dns_resolver(device)
    assert len(results) == 1
    assert results[0].check_id == "open_dns_resolver"
    assert results[0].severity == "medium"


@pytest.mark.unit
def test_check_open_dns_resolver_returns_risk_udp():
    from app.analysis.checks import check_open_dns_resolver

    device = _make_device(ports=[_make_port(53, protocol="udp")])
    results = check_open_dns_resolver(device)
    assert len(results) == 1
    assert results[0].check_id == "open_dns_resolver"


# ── check_modbus_open ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_check_modbus_open_returns_risk():
    from app.analysis.checks import check_modbus_open

    device = _make_device(ports=[_make_port(502)])
    results = check_modbus_open(device)
    assert len(results) == 1
    assert results[0].check_id == "modbus_open"
    assert results[0].severity == "high"


# ── Integration: run_checks with real DB ─────────────────────────────────────


@pytest.mark.integration
def test_run_checks_persists_risks(db_session):
    """run_checks writes Risk rows to the DB for a device with findings."""
    from app.analysis import run_checks
    from app.db import upsert_device, upsert_port

    device = upsert_device(db_session, ip_address="10.0.0.50")
    db_session.flush()
    upsert_port(
        db_session, device_id=device.id, port_number=23, protocol="tcp", service_name="telnet"
    )
    upsert_port(db_session, device_id=device.id, port_number=21, protocol="tcp", service_name="ftp")
    db_session.flush()

    risks = run_checks(db_session, device.id)
    db_session.flush()

    assert len(risks) >= 2
    check_ids = {r.check_id for r in risks}
    assert "telnet_open" in check_ids
    assert "ftp_open" in check_ids


@pytest.mark.integration
def test_run_checks_replaces_stale_risks(db_session):
    """Re-running checks removes findings that no longer apply."""
    from app.analysis import run_checks
    from app.db import upsert_device, upsert_port

    device = upsert_device(db_session, ip_address="10.0.0.51")
    db_session.flush()
    port = upsert_port(
        db_session, device_id=device.id, port_number=23, protocol="tcp", service_name="telnet"
    )
    db_session.flush()

    # First pass — telnet risk written
    risks1 = run_checks(db_session, device.id)
    db_session.flush()
    assert any(r.check_id == "telnet_open" for r in risks1)

    # Remove port 23 and run again — telnet risk should be gone
    db_session.delete(port)
    db_session.flush()
    # Expire the session identity map so the next select re-fetches from the DB
    db_session.expire_all()

    risks2 = run_checks(db_session, device.id)
    db_session.flush()
    assert not any(r.check_id == "telnet_open" for r in risks2)


@pytest.mark.integration
def test_run_checks_returns_empty_for_unknown_device(db_session):
    from app.analysis import run_checks

    result = run_checks(db_session, device_id=999999)
    assert result == []


@pytest.mark.integration
def test_run_all_checks_runs_across_all_devices(db_session):
    from app.analysis import run_all_checks
    from app.db import upsert_device, upsert_port

    d1 = upsert_device(db_session, ip_address="10.0.1.1")
    d2 = upsert_device(db_session, ip_address="10.0.1.2")
    db_session.flush()
    upsert_port(db_session, device_id=d1.id, port_number=23, service_name="telnet")
    upsert_port(db_session, device_id=d2.id, port_number=21, service_name="ftp")
    db_session.flush()

    total = run_all_checks(db_session)
    assert total >= 2


@pytest.mark.integration
def test_trusted_device_generates_no_risks(db_session):
    """Devices marked trusted must have all risks cleared and no new ones written."""
    from app.analysis import run_checks
    from app.db import upsert_device, upsert_port

    device = upsert_device(db_session, ip_address="10.99.1.1")
    db_session.flush()
    upsert_port(db_session, device_id=device.id, port_number=23, service_name="telnet")
    db_session.flush()

    # First pass generates risks
    risks_before = run_checks(db_session, device.id)
    db_session.flush()
    assert any(r.check_id == "telnet_open" for r in risks_before)

    # Mark trusted and re-run
    device.trusted = True
    db_session.flush()
    db_session.expire_all()

    risks_after = run_checks(db_session, device.id)
    db_session.flush()
    assert risks_after == []

    # Verify the DB also has no risk rows for this device
    from app.models.risk import Risk
    from sqlalchemy import select as sa_select

    remaining = (
        db_session.execute(sa_select(Risk).where(Risk.device_id == device.id)).scalars().all()
    )
    assert remaining == []
