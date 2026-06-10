"""Tests for nightwatch analyzers (ntopng, CrowdSec, cross-reference)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_db import (  # noqa: F401 — required for pytest fixture setup
    in_memory_engine,  # noqa: F811
    session,  # noqa: F401
)

# ════════════════════════════════════════════════════════════════════════════════
# ntopng_analyzer tests
# ════════════════════════════════════════════════════════════════════════════════


class TestNtopngBandwidth:
    """Tests for bandwidth anomaly detection."""

    def test_high_bandwidth_detected(self):
        from app.nightwatch.analyzers.ntopng_analyzer import ntopng_analyze

        data = {
            "total_bytes": 5_000_000_000,
            "fetched_at": "2026-06-10T12:00:00",
            "top_talkers": [
                {
                    "device": "192.168.1.10",
                    "bytes_sent": 2_000_000_000,
                    "bytes_recv": 1_000_000_000,
                },
                {"device": "192.168.1.20", "bytes_sent": 50_000, "bytes_recv": 50_000},
            ],
            "protocols": {"TCP": 500_000_000, "UDP": 300_000_000},
            "host_stats": [],
            "flows": [],
            "alerts": [],
            "unusual_protocols": {},
        }

        result = ntopng_analyze(data)
        assert len(result.bandwidth_findings) >= 1
        assert any("High bandwidth" in f.summary for f in result.bandwidth_findings)

    def test_no_high_bandwidth(self):
        from app.nightwatch.analyzers.ntopng_analyzer import ntopng_analyze

        data = {
            "total_bytes": 1_000_000,
            "fetched_at": "2026-06-10T12:00:00",
            "top_talkers": [
                {"device": "192.168.1.10", "bytes_sent": 100_000, "bytes_recv": 100_000},
            ],
            "protocols": {},
            "host_stats": [],
            "flows": [],
            "alerts": [],
            "unusual_protocols": {},
        }

        result = ntopng_analyze(data)
        assert len(result.bandwidth_findings) == 0

    def test_disproportionate_talker_detected(self):
        from app.nightwatch.analyzers.ntopng_analyzer import ntopng_analyze

        data = {
            "total_bytes": 2_000_000_000,
            "fetched_at": "2026-06-10T12:00:00",
            "top_talkers": [
                {"device": "big-host", "bytes_sent": 1_800_000_000, "bytes_recv": 500_000_000},
                {"device": "small-host", "bytes_sent": 10_000, "bytes_recv": 10_000},
                {"device": "tiny-host", "bytes_sent": 5_000, "bytes_recv": 5_000},
            ],
            "protocols": {},
            "host_stats": [],
            "flows": [],
            "alerts": [],
            "unusual_protocols": {},
        }

        result = ntopng_analyze(data)
        assert any("Top talker" in f.summary for f in result.bandwidth_findings)


class TestNtopngProtocols:
    """Tests for protocol anomaly detection."""

    def test_suspicious_protocols_detected(self):
        from app.nightwatch.analyzers.ntopng_analyzer import ntopng_analyze

        data = {
            "total_bytes": 1_000_000,
            "fetched_at": "2026-06-10T12:00:00",
            "top_talkers": [],
            "protocols": {"MODBUS": 50_000, "OPC": 2_000, "TCP": 500_000},
            "host_stats": [],
            "flows": [],
            "alerts": [],
            "unusual_protocols": {},
        }

        result = ntopng_analyze(data)
        assert len(result.protocol_findings) >= 2  # MODBUS + OPC

    def test_unusual_protocol_detected(self):
        from app.nightwatch.analyzers.ntopng_analyzer import ntopng_analyze

        data = {
            "total_bytes": 1_000_000,
            "fetched_at": "2026-06-10T12:00:00",
            "top_talkers": [],
            "protocols": {"COAP": 5_000, "MQTT": 100_000},
            "host_stats": [],
            "flows": [],
            "alerts": [],
            "unusual_protocols": {},
        }

        result = ntopng_analyze(data)
        assert any("Unusual protocol" in f.summary for f in result.protocol_findings)
        assert any("COAP" in f.summary for f in result.protocol_findings)


class TestNtopngHosts:
    """Tests for host anomaly detection."""

    def test_suspicious_port_detected(self):
        from app.nightwatch.analyzers.ntopng_analyzer import ntopng_analyze

        data = {
            "total_bytes": 1_000,
            "fetched_at": "2026-06-10T12:00:00",
            "top_talkers": [],
            "protocols": {},
            "host_stats": [
                {
                    "host": "192.168.1.100",
                    "hostname": "iot-camera",
                    "open_ports": [80, 31337],
                    "packets_sent": 100,
                    "packets_recv": 50,
                },
            ],
            "flows": [],
            "alerts": [],
            "unusual_protocols": {},
        }

        result = ntopng_analyze(data)
        assert any(f.severity == "critical" for f in result.host_findings)
        assert any(int(f.details.get("port", 0)) == 31337 for f in result.host_findings)

    def test_high_packet_count_detected(self):
        from app.nightwatch.analyzers.ntopng_analyzer import ntopng_analyze

        data = {
            "total_bytes": 1_000_000_000,
            "fetched_at": "2026-06-10T12:00:00",
            "top_talkers": [],
            "protocols": {},
            "host_stats": [
                {
                    "host": "scanner-host",
                    "hostname": "suspect",
                    "open_ports": [443],
                    "packets_sent": 600_000,
                    "packets_recv": 500_000,
                },
            ],
            "flows": [],
            "alerts": [],
            "unusual_protocols": {},
        }

        result = ntopng_analyze(data)
        assert any("high packet count" in f.summary for f in result.host_findings)

    def test_flow_anomaly_detected(self):
        from app.nightwatch.analyzers.ntopng_analyzer import ntopng_analyze

        data = {
            "total_bytes": 500_000,
            "fetched_at": "2026-06-10T12:00:00",
            "top_talkers": [],
            "protocols": {},
            "host_stats": [],
            "flows": [
                {
                    "src_host": "192.168.1.100",
                    "dst_host": "45.33.32.156",
                    "dst_port": 6667,
                    "l4_proto": "TCP",
                    "bytes": 5000,
                    "duration": 300,
                },
            ],
            "alerts": [],
            "unusual_protocols": {},
        }

        result = ntopng_analyze(data)
        assert any(f.severity == "high" for f in result.flow_findings)
        assert any("6667" in str(f.summary) for f in result.flow_findings)


class TestNtopngAnalysisResult:
    """Tests for ntopngAnalysis.to_list() flattening."""

    def test_to_list_returns_correct_format(self):
        from app.nightwatch.analyzers.ntopng_analyzer import ntopng_analyze

        data = {
            "total_bytes": 1_000_000,
            "fetched_at": "2026-06-10T12:00:00",
            "top_talkers": [
                {"device": "test-host", "bytes_sent": 100 * 1024 * 1024 + 1, "bytes_recv": 0},
            ],
            "protocols": {"TCP": 1000, "MODBUS": 5_000},
            "host_stats": [
                {
                    "host": "test-host",
                    "hostname": "test",
                    "open_ports": [31337],
                    "packets_sent": 100,
                    "packets_recv": 50,
                },
            ],
            "flows": [],
            "alerts": [],
            "unusual_protocols": {},
        }

        result = ntopng_analyze(data)
        flat = result.to_list()
        assert len(flat) > 0
        for item in flat:
            assert "source" in item
            assert item["source"] == "ntopng"
            assert "severity" in item
            assert "summary" in item


# ════════════════════════════════════════════════════════════════════════════════
# CrowdSec analyzer tests
# ════════════════════════════════════════════════════════════════════════════════


class TestCrowdSecBans:
    """Tests for ban aggregation."""

    def test_repeat_bans_detected(self):
        from app.nightwatch.analyzers.crowdsec_analyzer import crowdsec_analyze

        data = {
            "alerts": [
                {
                    "ip": "45.33.32.156",
                    "reason": "ssh-bruteforce",
                    "score": 9,
                    "expire": "9999-12-31",
                },
                {
                    "ip": "45.33.32.156",
                    "reason": "ssh-bruteforce",
                    "score": 9,
                    "expire": "9999-12-31",
                },
                {
                    "ip": "45.33.32.156",
                    "reason": "ssh-bruteforce",
                    "score": 9,
                    "expire": "9999-12-31",
                },
                {"ip": "10.0.0.5", "reason": "scan", "score": 3, "expire": "9999-12-31"},
            ],
            "journal": [],
            "bans": {"45.33.32.156": 3, "10.0.0.5": 1},
            "reasons": {"ssh-bruteforce": 3, "scan": 1},
            "active_ban_count": 4,
        }

        result = crowdsec_analyze(data)
        assert len(result["ban_findings"]) >= 1
        assert any(f.severity == "critical" for f in result["ban_findings"])
        assert any("Persistent attacker" in f.summary for f in result["ban_findings"])

    def test_empty_alerts(self):
        from app.nightwatch.analyzers.crowdsec_analyzer import crowdsec_analyze

        data = {"alerts": [], "journal": [], "bans": {}, "reasons": {}, "active_ban_count": 0}
        result = crowdsec_analyze(data)
        assert result["total_alerts"] == 0
        assert len(result["ban_findings"]) == 0


class TestCrowdSecScenarios:
    """Tests for scenario clustering."""

    def test_scenario_counting(self):
        from app.nightwatch.analyzers.crowdsec_analyzer import crowdsec_analyze

        data = {
            "alerts": [
                {"ip": "1.1.1.1", "scenario": "sshd-breakout", "score": 5, "expire": "9999-12-31"},
                {"ip": "2.2.2.2", "scenario": "sshd-breakout", "score": 5, "expire": "9999-12-31"},
                {"ip": "3.3.3.3", "scenario": "wp-admin-brute", "score": 3, "expire": "9999-12-31"},
            ],
            "journal": [],
            "bans": {},
            "reasons": {},
            "active_ban_count": 3,
        }

        result = crowdsec_analyze(data)
        assert len(result["scenario_findings"]) >= 1
        assert any("sshd-breakout" in f.summary for f in result["scenario_findings"])


class TestCrowdSecTemporal:
    """Tests for temporal pattern detection."""

    def test_burst_detected(self):
        from datetime import datetime, timedelta

        from app.nightwatch.analyzers.crowdsec_analyzer import crowdsec_analyze

        base = datetime.now()
        alerts = [
            {
                "ip": f"{i}.{i}.{i}.{i}",
                "reason": "scan",
                "score": 3,
                "expire": (base + timedelta(hours=1)).isoformat(),
                "created": (base + timedelta(minutes=i)).isoformat(),
            }
            for i in range(20)
        ]

        data = {
            "alerts": alerts,
            "journal": [],
            "bans": {},
            "reasons": {},
            "active_ban_count": 10,
        }

        result = crowdsec_analyze(data)
        assert len(result["temporal_findings"]) >= 1
        assert any("burst" in f.summary for f in result["temporal_findings"])


# ════════════════════════════════════════════════════════════════════════════════
# Cross-reference tests
# ════════════════════════════════════════════════════════════════════════════════


class TestCrossReference:
    """Tests for cross-referencing between data sources."""

    def test_active_ban_on_network_detected(self):
        from app.nightwatch.analyzers.cross_reference import cross_reference

        ntopng = {
            "top_talkers": [{"device": "45.33.32.156", "bytes_sent": 1000, "bytes_recv": 500}],
            "host_stats": [{"host": "45.33.32.156", "hostname": "bad-host"}],
        }
        crowdsec = {
            "alerts": [
                {"ip": "45.33.32.156", "reason": "brute-force", "score": 9, "expire": "9999-12-31"}
            ],
            "bans": {},
            "reasons": {},
            "active_ban_count": 1,
        }

        result = cross_reference(crowdsec, ntopng)
        assert len(result) >= 1
        assert any("CrowdSec ban" in f.summary for f in result)

    def test_no_match_when_ip_not_on_network(self):
        from app.nightwatch.analyzers.cross_reference import cross_reference

        ntopng = {
            "top_talkers": [{"device": "192.168.1.10", "bytes_sent": 1000, "bytes_recv": 500}],
            "host_stats": [{"host": "192.168.1.10", "hostname": "good-host"}],
        }
        crowdsec = {
            "alerts": [{"ip": "99.99.99.99", "reason": "brute-force", "score": 9}],
            "bans": {},
            "reasons": {},
            "active_ban_count": 1,
        }

        result = cross_reference(crowdsec, ntopng)
        # Should not find active-ban-on-lan correlation
        assert not any("Active device" in f.summary for f in result)

    def test_empty_input_returns_empty(self):
        from app.nightwatch.analyzers.cross_reference import cross_reference

        result = cross_reference(
            {"alerts": [], "bans": {}, "reasons": {}, "active_ban_count": 0},
            {"top_talkers": [], "host_stats": []},
        )
        assert result == []
