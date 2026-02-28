"""
test_scanner.py — Tests for the scanner package.

Unit tests mock subprocess so no real network tools are required.
Integration tests use fixture XML files to exercise the XML parsers end-to-end.

Markers
-------
unit        — pure logic / mocked I/O, always run
integration — fixture-based, no live network
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from app.scanner import ScanResult, orchestrate_scan
from app.scanner.arp_scan import ArpHost, parse_arp_output, run_arp_scan
from app.scanner.nmap_scan import NmapHost, parse_nmap_xml, run_nmap_scan

# ── Fixture helpers ──────────────────────────────────────────────────────────

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


# ═══════════════════════════════════════════════════════════════════════════════
# arp_scan — unit tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseArpOutput:
    """parse_arp_output() is pure; no mocking needed."""

    @pytest.mark.unit
    def test_parses_single_host(self):
        output = "192.168.1.1\taa:bb:cc:dd:ee:ff\tCisco Systems\n"
        hosts = parse_arp_output(output)
        assert len(hosts) == 1
        assert hosts[0].ip == "192.168.1.1"
        assert hosts[0].mac == "aa:bb:cc:dd:ee:ff"
        assert hosts[0].vendor == "Cisco Systems"

    @pytest.mark.unit
    def test_parses_multiple_hosts(self):
        output = (
            "192.168.1.1\taa:bb:cc:dd:ee:01\tVendorA\n192.168.1.2\taa:bb:cc:dd:ee:02\tVendorB\n"
        )
        hosts = parse_arp_output(output)
        assert len(hosts) == 2
        assert hosts[1].ip == "192.168.1.2"

    @pytest.mark.unit
    def test_skips_header_and_summary_lines(self):
        output = (
            "Interface: eth0, datalink type: EN10MB (Ethernet)\n"
            "Starting arp-scan 1.10.0 with 256 hosts...\n"
            "192.168.1.1\taa:bb:cc:dd:ee:ff\tCisco Systems\n"
            "\n"
            "3 packets received by filter, 0 packets dropped by kernel\n"
        )
        hosts = parse_arp_output(output)
        assert len(hosts) == 1

    @pytest.mark.unit
    def test_empty_output_returns_empty_list(self):
        assert parse_arp_output("") == []

    @pytest.mark.unit
    def test_vendor_can_be_blank_with_empty_tab(self):
        """Trailing tab present but vendor field is empty."""
        output = "10.0.0.5\t00:11:22:33:44:55\t\n"
        hosts = parse_arp_output(output)
        assert len(hosts) == 1
        assert hosts[0].vendor == ""

    @pytest.mark.unit
    def test_vendor_can_be_blank_no_tab(self):
        """arp-scan omits the vendor tab entirely when vendor is unknown."""
        output = "10.0.0.5\t00:11:22:33:44:55\n"
        hosts = parse_arp_output(output)
        assert len(hosts) == 1
        assert hosts[0].vendor == ""

    @pytest.mark.unit
    def test_strips_whitespace_around_lines(self):
        output = "  192.168.1.1\tde:ad:be:ef:00:01\tSome Corp  \n"
        hosts = parse_arp_output(output)
        assert hosts[0].ip == "192.168.1.1"


class TestRunArpScan:
    """run_arp_scan() mocks subprocess.run."""

    @pytest.mark.unit
    def test_returns_parsed_hosts_on_success(self):
        stdout = "192.168.1.1\taa:bb:cc:dd:ee:ff\tCisco\n"
        mock_result = MagicMock(returncode=0, stdout=stdout, stderr="")

        with patch("app.scanner.arp_scan.subprocess.run", return_value=mock_result) as mock_run:
            hosts = run_arp_scan(interface="eth0", subnet="192.168.1.0/24")

        assert len(hosts) == 1
        assert hosts[0].ip == "192.168.1.1"
        # Verify correct command was built
        cmd = mock_run.call_args[0][0]
        assert "arp-scan" in cmd
        assert "--interface" in cmd
        assert "eth0" in cmd

    @pytest.mark.unit
    def test_returns_empty_list_when_no_hosts_found(self):
        """arp-scan exits 1 with empty stderr when no hosts found — must not raise."""
        mock_result = MagicMock(returncode=1, stdout="", stderr="")
        with patch("app.scanner.arp_scan.subprocess.run", return_value=mock_result):
            hosts = run_arp_scan(interface="eth0", subnet="192.168.1.0/24")
        assert hosts == []

    @pytest.mark.unit
    def test_raises_on_exit1_with_stderr(self):
        """Exit code 1 with stderr content is a real error (e.g. permission denied) — must raise."""
        mock_result = MagicMock(
            returncode=1,
            stdout="",
            stderr="ERROR: socket(PF_PACKET, SOCK_RAW, 8): Operation not permitted",
        )
        with patch("app.scanner.arp_scan.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="arp-scan failed"):
                run_arp_scan()

    @pytest.mark.unit
    def test_raises_on_nonzero_exit(self):
        mock_result = MagicMock(returncode=2, stdout="", stderr="permission denied")
        with patch("app.scanner.arp_scan.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="arp-scan failed"):
                run_arp_scan()

    @pytest.mark.unit
    def test_does_not_pass_localnet_flag(self):
        """--localnet conflicts with a subnet target; must never appear in the command."""
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.scanner.arp_scan.subprocess.run", return_value=mock_result) as mock_run:
            run_arp_scan(interface="eth0", subnet="192.168.1.0/24")
        cmd = mock_run.call_args[0][0]
        assert "--localnet" not in cmd
        assert "192.168.1.0/24" in cmd

    @pytest.mark.unit
    def test_uses_env_vars_as_defaults(self, monkeypatch):
        monkeypatch.setenv("NETWORK_INTERFACE", "ens3")
        monkeypatch.setenv("SCAN_SUBNET", "10.0.0.0/8")
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("app.scanner.arp_scan.subprocess.run", return_value=mock_result) as mock_run:
            run_arp_scan()
        cmd = mock_run.call_args[0][0]
        assert "ens3" in cmd
        assert "10.0.0.0/8" in cmd


# ═══════════════════════════════════════════════════════════════════════════════
# nmap_scan — integration tests (fixture XML)
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseNmapXml:
    """parse_nmap_xml() is pure; exercises fixture files."""

    @pytest.mark.integration
    def test_two_hosts_fixture(self):
        xml = _fixture("nmap_two_hosts.xml")
        hosts = parse_nmap_xml(xml)
        assert len(hosts) == 2

    @pytest.mark.integration
    def test_router_host_fields(self):
        xml = _fixture("nmap_two_hosts.xml")
        router = next(h for h in parse_nmap_xml(xml) if h.ip == "192.168.1.1")

        assert router.mac == "AA:BB:CC:DD:EE:01"
        assert router.hostname == "router.local"
        assert router.os_guess == "Linux 5.4"

    @pytest.mark.integration
    def test_router_open_ports_only(self):
        """Closed port 443 must not appear in results."""
        xml = _fixture("nmap_two_hosts.xml")
        router = next(h for h in parse_nmap_xml(xml) if h.ip == "192.168.1.1")

        port_nums = [p.port_number for p in router.ports]
        assert 22 in port_nums
        assert 80 in port_nums
        assert 443 not in port_nums  # closed — must be excluded

    @pytest.mark.integration
    def test_router_ssh_port_details(self):
        xml = _fixture("nmap_two_hosts.xml")
        router = next(h for h in parse_nmap_xml(xml) if h.ip == "192.168.1.1")
        ssh = next(p for p in router.ports if p.port_number == 22)

        assert ssh.protocol == "tcp"
        assert ssh.state == "open"
        assert ssh.service_name == "ssh"
        assert "OpenSSH" in ssh.version_banner
        assert "Ubuntu" in ssh.version_banner

    @pytest.mark.integration
    def test_workstation_no_mac_no_os(self):
        xml = _fixture("nmap_two_hosts.xml")
        ws = next(h for h in parse_nmap_xml(xml) if h.ip == "192.168.1.10")

        assert ws.mac == ""
        assert ws.os_guess == ""
        assert ws.hostname == ""

    @pytest.mark.integration
    def test_workstation_smb_port(self):
        xml = _fixture("nmap_two_hosts.xml")
        ws = next(h for h in parse_nmap_xml(xml) if h.ip == "192.168.1.10")

        assert len(ws.ports) == 1
        assert ws.ports[0].port_number == 445
        assert "WORKGROUP" in ws.ports[0].version_banner

    @pytest.mark.integration
    def test_minimal_host_fixture(self):
        """Host with no open ports, no hostname, no OS — still included (state=up)."""
        xml = _fixture("nmap_minimal_host.xml")
        hosts = parse_nmap_xml(xml)

        assert len(hosts) == 1
        assert hosts[0].ip == "192.168.1.50"
        assert hosts[0].mac == "DE:AD:BE:EF:00:01"
        assert hosts[0].ports == []  # only filtered port — not included

    @pytest.mark.integration
    def test_host_down_excluded(self):
        """Hosts with state=down must be excluded entirely."""
        xml = _fixture("nmap_host_down.xml")
        hosts = parse_nmap_xml(xml)
        assert hosts == []

    @pytest.mark.integration
    def test_no_ports_element_returns_empty_ports(self):
        """Host with no <ports> element at all must parse cleanly with empty ports list."""
        xml = _fixture("nmap_no_ports_element.xml")
        hosts = parse_nmap_xml(xml)
        assert len(hosts) == 1
        assert hosts[0].ip == "192.168.1.77"
        assert hosts[0].ports == []

    @pytest.mark.integration
    def test_os_highest_accuracy_wins(self):
        """When multiple osmatch entries exist, the highest accuracy must be chosen."""
        xml = _fixture("nmap_two_hosts.xml")
        router = next(h for h in parse_nmap_xml(xml) if h.ip == "192.168.1.1")
        # Fixture has accuracy 95 (Linux 5.4) and 80 (Linux 4.15)
        assert router.os_guess == "Linux 5.4"


# ═══════════════════════════════════════════════════════════════════════════════
# nmap_scan — unit tests (mocked subprocess)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunNmapScan:
    """run_nmap_scan() mocks subprocess.run; XML writing verified via fixture."""

    @pytest.mark.unit
    def test_does_not_use_os_detection_flag(self):
        """-O must not appear in the nmap command: it hard-codes geteuid()==0 and
        always quits when running as non-root uid 1000, regardless of file caps."""
        fixture_xml = _fixture("nmap_two_hosts.xml")

        def fake_run(cmd, **kwargs):
            idx = cmd.index("-oX")
            Path(cmd[idx + 1]).write_text(fixture_xml)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("app.scanner.nmap_scan.subprocess.run", side_effect=fake_run) as mock_run:
            run_nmap_scan(hosts=["192.168.1.1"], interface="eth0")

        cmd = mock_run.call_args[0][0]
        assert "-O" not in cmd
        assert "-sV" in cmd

    @pytest.mark.unit
    def test_returns_empty_list_for_empty_hosts(self):
        assert run_nmap_scan(hosts=[]) == []

    @pytest.mark.unit
    def test_parses_xml_written_by_nmap(self, tmp_path):
        """
        Simulate nmap writing XML to the temp file path captured by the mock.
        We intercept the call, copy a fixture to the temp file, then return rc=0.
        """
        fixture_xml = _fixture("nmap_two_hosts.xml")

        def fake_run(cmd, **kwargs):
            # Find the -oX argument and write fixture content to that path
            idx = cmd.index("-oX")
            xml_path = cmd[idx + 1]
            Path(xml_path).write_text(fixture_xml)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("app.scanner.nmap_scan.subprocess.run", side_effect=fake_run):
            hosts = run_nmap_scan(hosts=["192.168.1.1", "192.168.1.10"], interface="eth0")

        assert len(hosts) == 2
        assert hosts[0].ip == "192.168.1.1"

    @pytest.mark.unit
    def test_raises_on_nmap_failure(self):
        mock_result = MagicMock(returncode=1, stdout="", stderr="nmap: no interfaces")
        with patch("app.scanner.nmap_scan.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="nmap failed"):
                run_nmap_scan(hosts=["192.168.1.1"])

    @pytest.mark.unit
    def test_temp_file_cleaned_up_on_success(self):
        """Temporary XML file must be deleted even on success."""
        fixture_xml = _fixture("nmap_two_hosts.xml")
        captured_paths: list[str] = []

        def fake_run(cmd, **kwargs):
            idx = cmd.index("-oX")
            xml_path = cmd[idx + 1]
            captured_paths.append(xml_path)
            Path(xml_path).write_text(fixture_xml)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("app.scanner.nmap_scan.subprocess.run", side_effect=fake_run):
            run_nmap_scan(hosts=["192.168.1.1"])

        assert captured_paths, "No temp path was captured"
        assert not Path(captured_paths[0]).exists(), "Temp XML file was not cleaned up"

    @pytest.mark.unit
    def test_temp_file_cleaned_up_on_failure(self):
        """Temporary XML file must be deleted even when nmap exits non-zero."""
        captured_paths: list[str] = []

        def fake_run(cmd, **kwargs):
            idx = cmd.index("-oX")
            captured_paths.append(cmd[idx + 1])
            return MagicMock(returncode=1, stdout="", stderr="error")

        with patch("app.scanner.nmap_scan.subprocess.run", side_effect=fake_run):
            with pytest.raises(RuntimeError):
                run_nmap_scan(hosts=["192.168.1.1"])

        assert captured_paths
        assert not Path(captured_paths[0]).exists(), "Temp XML file leaked on failure"

    @pytest.mark.unit
    def test_uses_env_var_for_interface(self, monkeypatch):
        monkeypatch.setenv("NETWORK_INTERFACE", "wlan0")
        fixture_xml = _fixture("nmap_two_hosts.xml")

        def fake_run(cmd, **kwargs):
            idx = cmd.index("-oX")
            Path(cmd[idx + 1]).write_text(fixture_xml)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("app.scanner.nmap_scan.subprocess.run", side_effect=fake_run) as mock_run:
            run_nmap_scan(hosts=["192.168.1.1"])

        cmd = mock_run.call_args[0][0]
        assert "wlan0" in cmd


# ═══════════════════════════════════════════════════════════════════════════════
# orchestrate_scan — unit tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrchestrateScan:
    """orchestrate_scan() mocks both run_arp_scan and run_nmap_scan."""

    @pytest.mark.unit
    def test_returns_empty_scan_result_when_no_arp_hosts(self):
        with patch("app.scanner.run_arp_scan", return_value=[]):
            result = orchestrate_scan()
        assert isinstance(result, ScanResult)
        assert result.hosts == []
        assert result.arp_only == []

    @pytest.mark.unit
    def test_merges_mac_from_arp_into_nmap(self):
        arp_hosts = [ArpHost(ip="192.168.1.1", mac="aa:bb:cc:dd:ee:ff", vendor="Cisco")]
        nmap_hosts = [NmapHost(ip="192.168.1.1", mac="")]  # nmap didn't capture MAC

        with (
            patch("app.scanner.run_arp_scan", return_value=arp_hosts),
            patch("app.scanner.run_nmap_scan", return_value=nmap_hosts),
        ):
            result = orchestrate_scan()

        assert result.hosts[0].mac == "aa:bb:cc:dd:ee:ff"
        assert result.arp_only == []

    @pytest.mark.unit
    def test_keeps_existing_mac_from_nmap(self):
        """If nmap already has a MAC, the arp value should not overwrite it."""
        arp_hosts = [ArpHost(ip="192.168.1.1", mac="11:22:33:44:55:66", vendor="")]
        nmap_hosts = [NmapHost(ip="192.168.1.1", mac="aa:bb:cc:dd:ee:ff")]

        with (
            patch("app.scanner.run_arp_scan", return_value=arp_hosts),
            patch("app.scanner.run_nmap_scan", return_value=nmap_hosts),
        ):
            result = orchestrate_scan()

        assert result.hosts[0].mac == "aa:bb:cc:dd:ee:ff"

    @pytest.mark.unit
    def test_arp_only_hosts_excluded_from_nmap_results(self):
        arp_hosts = [
            ArpHost(ip="192.168.1.1", mac="aa:00:00:00:00:01", vendor=""),
            ArpHost(ip="192.168.1.2", mac="aa:00:00:00:00:02", vendor=""),
        ]
        # nmap only returned the first host
        nmap_hosts = [NmapHost(ip="192.168.1.1", mac="aa:00:00:00:00:01")]

        with (
            patch("app.scanner.run_arp_scan", return_value=arp_hosts),
            patch("app.scanner.run_nmap_scan", return_value=nmap_hosts),
        ):
            result = orchestrate_scan()

        assert len(result.hosts) == 1
        assert len(result.arp_only) == 1
        assert result.arp_only[0].ip == "192.168.1.2"

    @pytest.mark.unit
    def test_passes_interface_and_subnet_through(self):
        with (
            patch("app.scanner.run_arp_scan", return_value=[]) as mock_arp,
        ):
            orchestrate_scan(interface="eth1", subnet="10.10.0.0/16")

        mock_arp.assert_called_once_with(interface="eth1", subnet="10.10.0.0/16")

    @pytest.mark.unit
    def test_uses_env_vars_for_interface_and_subnet(self, monkeypatch):
        monkeypatch.setenv("NETWORK_INTERFACE", "bond0")
        monkeypatch.setenv("SCAN_SUBNET", "172.16.0.0/12")

        with patch("app.scanner.run_arp_scan", return_value=[]) as mock_arp:
            orchestrate_scan()

        mock_arp.assert_called_once_with(interface="bond0", subnet="172.16.0.0/12")

    @pytest.mark.unit
    def test_host_timeout_default_in_command(self):
        """--host-timeout 30s must appear in the nmap command by default."""
        fixture_xml = _fixture("nmap_two_hosts.xml")

        def fake_run(cmd, **kwargs):
            idx = cmd.index("-oX")
            Path(cmd[idx + 1]).write_text(fixture_xml)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("app.scanner.nmap_scan.subprocess.run", side_effect=fake_run) as mock_run:
            run_nmap_scan(hosts=["192.168.1.1"], interface="eth0")

        cmd = mock_run.call_args[0][0]
        assert "--host-timeout" in cmd
        assert cmd[cmd.index("--host-timeout") + 1] == "30s"

    @pytest.mark.unit
    def test_host_timeout_env_override(self, monkeypatch):
        """NMAP_HOST_TIMEOUT env var must override the default 30s value."""
        monkeypatch.setenv("NMAP_HOST_TIMEOUT", "60s")
        fixture_xml = _fixture("nmap_two_hosts.xml")

        def fake_run(cmd, **kwargs):
            idx = cmd.index("-oX")
            Path(cmd[idx + 1]).write_text(fixture_xml)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("app.scanner.nmap_scan.subprocess.run", side_effect=fake_run) as mock_run:
            run_nmap_scan(hosts=["192.168.1.1"], interface="eth0")

        cmd = mock_run.call_args[0][0]
        assert cmd[cmd.index("--host-timeout") + 1] == "60s"
