"""
Unit tests for scan_runner.run_scan_and_persist().

orchestrate_scan is always mocked — no real network I/O.

Markers: unit, integration
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def in_memory_session_factory():
    """In-memory SQLite DB with all tables created; returns a SessionLocal factory.

    StaticPool is required so every session shares the same underlying connection
    and therefore sees the same in-memory database.
    """
    import app.models.device  # noqa: F401 — side-effect import registers ORM tables
    import app.models.recommendation  # noqa: F401 — side-effect import registers ORM tables
    import app.models.risk  # noqa: F401 — side-effect import registers ORM tables
    import app.models.scan  # noqa: F401 — side-effect import registers ORM tables
    from app.db import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)
    yield factory
    Base.metadata.drop_all(bind=engine)


def _make_scan_result(n_hosts: int = 1, n_arp: int = 0):
    """Return a minimal ScanResult with mocked NmapHost / ArpHost objects."""
    from app.scanner import ScanResult
    from app.scanner.arp_scan import ArpHost
    from app.scanner.nmap_scan import NmapHost, PortInfo

    hosts = []
    for i in range(n_hosts):
        nh = MagicMock(spec=NmapHost)
        nh.ip = f"192.168.1.{10 + i}"
        nh.mac = f"aa:bb:cc:dd:ee:{i:02x}"
        nh.hostname = f"host{i}"
        nh.os_guess = None
        port = MagicMock(spec=PortInfo)
        port.port_number = 22
        port.protocol = "tcp"
        port.service_name = "ssh"
        port.version_banner = None
        nh.ports = [port]
        hosts.append(nh)

    arp_only = []
    for j in range(n_arp):
        ah = MagicMock(spec=ArpHost)
        ah.ip = f"192.168.1.{50 + j}"
        ah.mac = f"11:22:33:44:55:{j:02x}"
        ah.vendor = "Acme"
        arp_only.append(ah)

    return ScanResult(hosts=hosts, arp_only=arp_only)


# ── run_scan_and_persist — happy path ─────────────────────────────────────────


@pytest.mark.integration
def test_run_scan_creates_scan_record(in_memory_session_factory, monkeypatch):
    """A completed scan inserts a Scan row with status='completed'."""
    from app.models.scan import Scan
    from app.scan_runner import run_scan_and_persist

    monkeypatch.setattr("app.scan_runner.SessionLocal", in_memory_session_factory)

    with patch("app.scan_runner.orchestrate_scan", return_value=_make_scan_result()):
        scan_id = run_scan_and_persist("manual")

    assert isinstance(scan_id, int)

    db = in_memory_session_factory()
    scan = db.get(Scan, scan_id)
    assert scan is not None
    assert scan.status == "completed"  # type: ignore[union-attr]
    assert scan.triggered_by == "manual"  # type: ignore[union-attr]
    assert scan.devices_found == 1  # type: ignore[union-attr]
    assert scan.finished_at is not None  # type: ignore[union-attr]
    assert scan.duration_seconds is not None  # type: ignore[union-attr]
    db.close()


@pytest.mark.integration
def test_run_scan_persists_device(in_memory_session_factory, monkeypatch):
    """Devices discovered by orchestrate_scan are upserted into the DB."""
    from app.models.device import Device
    from app.scan_runner import run_scan_and_persist

    monkeypatch.setattr("app.scan_runner.SessionLocal", in_memory_session_factory)

    with patch("app.scan_runner.orchestrate_scan", return_value=_make_scan_result(n_hosts=1)):
        run_scan_and_persist("scheduler")

    db = in_memory_session_factory()
    devices = db.execute(select(Device)).scalars().all()
    assert any(d.ip_address == "192.168.1.10" for d in devices)
    db.close()


@pytest.mark.integration
def test_run_scan_persists_port(in_memory_session_factory, monkeypatch):
    """Ports discovered are upserted linked to their device."""
    from app.models.device import Port
    from app.scan_runner import run_scan_and_persist

    monkeypatch.setattr("app.scan_runner.SessionLocal", in_memory_session_factory)

    with patch("app.scan_runner.orchestrate_scan", return_value=_make_scan_result(n_hosts=1)):
        run_scan_and_persist("scheduler")

    db = in_memory_session_factory()
    ports = db.execute(select(Port)).scalars().all()
    assert any(p.port_number == 22 for p in ports)
    db.close()


@pytest.mark.integration
def test_run_scan_arp_only_hosts(in_memory_session_factory, monkeypatch):
    """ARP-only hosts (no nmap data) are upserted with vendor."""
    from app.models.device import Device
    from app.scan_runner import run_scan_and_persist

    monkeypatch.setattr("app.scan_runner.SessionLocal", in_memory_session_factory)

    with patch(
        "app.scan_runner.orchestrate_scan",
        return_value=_make_scan_result(n_hosts=0, n_arp=2),
    ):
        run_scan_and_persist("scheduler")

    db = in_memory_session_factory()
    devices = db.execute(select(Device)).scalars().all()
    assert len(devices) >= 2
    db.close()


@pytest.mark.integration
def test_run_scan_multiple_hosts(in_memory_session_factory, monkeypatch):
    """devices_found reflects total nmap hosts + arp_only."""
    from app.models.scan import Scan
    from app.scan_runner import run_scan_and_persist

    monkeypatch.setattr("app.scan_runner.SessionLocal", in_memory_session_factory)

    with patch(
        "app.scan_runner.orchestrate_scan",
        return_value=_make_scan_result(n_hosts=2, n_arp=3),
    ):
        scan_id = run_scan_and_persist("manual")

    db = in_memory_session_factory()
    scan = db.get(Scan, scan_id)
    assert scan.devices_found == 5  # type: ignore[union-attr]
    db.close()


# ── run_scan_and_persist — failure path ───────────────────────────────────────


@pytest.mark.integration
def test_run_scan_marks_failed_on_exception(in_memory_session_factory, monkeypatch):
    """When orchestrate_scan raises, Scan status is 'failed' and error_message is set."""
    from app.models.scan import Scan
    from app.scan_runner import run_scan_and_persist

    monkeypatch.setattr("app.scan_runner.SessionLocal", in_memory_session_factory)

    with patch("app.scan_runner.orchestrate_scan", side_effect=RuntimeError("boom")):
        scan_id = run_scan_and_persist("manual")

    db = in_memory_session_factory()
    scan = db.get(Scan, scan_id)
    assert scan.status == "failed"  # type: ignore[union-attr]
    assert "boom" in scan.error_message  # type: ignore[union-attr]
    assert scan.finished_at is not None  # type: ignore[union-attr]
    db.close()


@pytest.mark.unit
def test_run_scan_returns_scan_id(in_memory_session_factory, monkeypatch):
    """run_scan_and_persist always returns an int scan ID even on failure."""
    from app.scan_runner import run_scan_and_persist

    monkeypatch.setattr("app.scan_runner.SessionLocal", in_memory_session_factory)

    with patch("app.scan_runner.orchestrate_scan", side_effect=Exception("err")):
        result = run_scan_and_persist("scheduler")

    assert isinstance(result, int)


@pytest.mark.integration
def test_run_scan_populates_risk_counts(in_memory_session_factory, monkeypatch):
    """Completed scan record includes per-severity risk counts (all zero when no risks)."""
    from app.models.scan import Scan
    from app.scan_runner import run_scan_and_persist

    monkeypatch.setattr("app.scan_runner.SessionLocal", in_memory_session_factory)

    with patch("app.scan_runner.orchestrate_scan", return_value=_make_scan_result(n_hosts=1)):
        scan_id = run_scan_and_persist("manual")

    db = in_memory_session_factory()
    scan = db.get(Scan, scan_id)
    assert scan.risks_critical is not None  # type: ignore[union-attr]
    assert scan.risks_high is not None  # type: ignore[union-attr]
    assert scan.risks_medium is not None  # type: ignore[union-attr]
    assert scan.risks_low is not None  # type: ignore[union-attr]
    # All counts must be non-negative integers
    assert scan.risks_critical >= 0  # type: ignore[union-attr]
    assert scan.risks_high >= 0  # type: ignore[union-attr]
    assert scan.risks_medium >= 0  # type: ignore[union-attr]
    assert scan.risks_low >= 0  # type: ignore[union-attr]
    db.close()


@pytest.mark.unit
def test_partial_scan_persists_arp_devices_when_nmap_fails(in_memory_session_factory, monkeypatch):
    """When nmap fails, ARP-discovered devices must still be persisted and
    the scan marked 'completed' with a warning_message."""
    from app.models.device import Device
    from app.models.scan import Scan
    from app.scan_runner import run_scan_and_persist
    from app.scanner import ScanResult
    from app.scanner.arp_scan import ArpHost

    monkeypatch.setattr("app.scan_runner.SessionLocal", in_memory_session_factory)

    partial_result = ScanResult(
        hosts=[],
        arp_only=[ArpHost(ip="192.168.1.50", mac="aa:bb:cc:dd:ee:ff", vendor="Acme")],
        warnings=["nmap unavailable — showing ARP-only results: nmap failed"],
    )

    with patch("app.scan_runner.orchestrate_scan", return_value=partial_result):
        scan_id = run_scan_and_persist("manual")

    db = in_memory_session_factory()
    scan = db.get(Scan, scan_id)
    assert scan.status == "completed"  # type: ignore[union-attr]
    assert scan.warning_message is not None  # type: ignore[union-attr]
    assert "nmap" in scan.warning_message.lower()  # type: ignore[union-attr]

    devices = db.query(Device).filter(Device.ip_address == "192.168.1.50").all()
    assert len(devices) == 1
    db.close()


@pytest.mark.unit
def test_stale_ports_removed_on_rescan(in_memory_session_factory, monkeypatch):
    """Ports from a previous scan that are absent in the current scan must be deleted."""
    from app.models.device import Port
    from app.scan_runner import run_scan_and_persist
    from app.scanner import ScanResult
    from app.scanner.nmap_scan import NmapHost, PortInfo

    monkeypatch.setattr("app.scan_runner.SessionLocal", in_memory_session_factory)

    # First scan: device has ports 22 and 80
    first_result = ScanResult(
        hosts=[
            NmapHost(
                ip="192.168.1.10",
                hostname="myhost",
                ports=[
                    PortInfo(port_number=22, protocol="tcp", state="open", service_name="ssh"),
                    PortInfo(port_number=80, protocol="tcp", state="open", service_name="http"),
                ],
            )
        ],
        arp_only=[],
    )
    with patch("app.scan_runner.orchestrate_scan", return_value=first_result):
        run_scan_and_persist("manual")

    db = in_memory_session_factory()
    ports_after_first = db.query(Port).filter(Port.port_number.in_([22, 80])).all()
    assert len(ports_after_first) == 2
    db.close()

    # Second scan: device now only has port 22 (80 closed)
    second_result = ScanResult(
        hosts=[
            NmapHost(
                ip="192.168.1.10",
                hostname="myhost",
                ports=[
                    PortInfo(port_number=22, protocol="tcp", state="open", service_name="ssh"),
                ],
            )
        ],
        arp_only=[],
    )
    with patch("app.scan_runner.orchestrate_scan", return_value=second_result):
        run_scan_and_persist("manual")

    db2 = in_memory_session_factory()
    remaining = db2.query(Port).all()
    port_numbers = [p.port_number for p in remaining]
    assert 22 in port_numbers
    assert 80 not in port_numbers, "Stale port 80 should have been removed"
    db2.close()
