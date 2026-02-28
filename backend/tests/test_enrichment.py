"""
test_enrichment.py — Unit tests for dns_lookup and os_inference modules.

Markers: unit
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from app.scanner.dns_lookup import resolve_hostnames
from app.scanner.nmap_scan import NmapHost, PortInfo
from app.scanner.os_inference import enrich_os_guesses, infer_os

# ═══════════════════════════════════════════════════════════════════════════════
# os_inference — infer_os()
# ═══════════════════════════════════════════════════════════════════════════════


def _host_with_ssh(banner: str) -> NmapHost:
    return NmapHost(
        ip="192.168.1.1",
        ports=[
            PortInfo(
                port_number=22,
                protocol="tcp",
                state="open",
                service_name="ssh",
                version_banner=banner,
            )
        ],
    )


def _host_with_http(banner: str) -> NmapHost:
    return NmapHost(
        ip="192.168.1.1",
        ports=[
            PortInfo(
                port_number=80,
                protocol="tcp",
                state="open",
                service_name="http",
                version_banner=banner,
            )
        ],
    )


class TestInferOs:
    @pytest.mark.unit
    def test_ubuntu_ssh_banner(self):
        assert infer_os(_host_with_ssh("OpenSSH 8.9p1 Ubuntu-3ubuntu0.6")) == "Linux (Ubuntu)"

    @pytest.mark.unit
    def test_debian_ssh_banner(self):
        assert infer_os(_host_with_ssh("OpenSSH 8.4p1 Debian-2+deb11u2")) == "Linux (Debian)"

    @pytest.mark.unit
    def test_raspbian_ssh_banner(self):
        assert infer_os(_host_with_ssh("OpenSSH 8.4p1 Raspbian-5+rpi1")) == "Linux (Raspbian)"

    @pytest.mark.unit
    def test_freebsd_ssh_banner(self):
        assert infer_os(_host_with_ssh("OpenSSH 7.9 FreeBSD-20200214")) == "FreeBSD"

    @pytest.mark.unit
    def test_windows_ssh_banner(self):
        assert infer_os(_host_with_ssh("OpenSSH_for_Windows_8.1")) == "Windows"

    @pytest.mark.unit
    def test_generic_openssh_fallback(self):
        assert infer_os(_host_with_ssh("OpenSSH 9.0 (protocol 2.0)")) == "Linux"

    @pytest.mark.unit
    def test_openwrt_http_banner(self):
        assert infer_os(_host_with_http("OpenWrt/uhttpd")) == "Linux (OpenWrt)"

    @pytest.mark.unit
    def test_synology_http_banner(self):
        assert infer_os(_host_with_http("nginx/Synology")) == "Linux (Synology DSM)"

    @pytest.mark.unit
    def test_windows_smb_service(self):
        host = NmapHost(
            ip="192.168.1.1",
            ports=[
                PortInfo(
                    port_number=445,
                    protocol="tcp",
                    state="open",
                    service_name="microsoft-ds",
                    version_banner="",
                )
            ],
        )
        assert infer_os(host) == "Windows"

    @pytest.mark.unit
    def test_no_ports_returns_empty(self):
        assert infer_os(NmapHost(ip="192.168.1.1")) == ""

    @pytest.mark.unit
    def test_unrecognised_banner_returns_empty(self):
        assert infer_os(_host_with_ssh("some-unknown-server 1.0")) == ""

    @pytest.mark.unit
    def test_ssh_takes_priority_over_http(self):
        """SSH banner should be used before HTTP when both are present."""
        host = NmapHost(
            ip="192.168.1.1",
            ports=[
                PortInfo(
                    port_number=22,
                    protocol="tcp",
                    state="open",
                    service_name="ssh",
                    version_banner="OpenSSH 8.9p1 Ubuntu-3",
                ),
                PortInfo(
                    port_number=80,
                    protocol="tcp",
                    state="open",
                    service_name="http",
                    version_banner="OpenWrt/uhttpd",
                ),
            ],
        )
        assert infer_os(host) == "Linux (Ubuntu)"


class TestEnrichOsGuesses:
    @pytest.mark.unit
    def test_fills_empty_os_guess(self):
        host = _host_with_ssh("OpenSSH 8.9p1 Ubuntu-3")
        host.os_guess = ""
        enrich_os_guesses([host])
        assert host.os_guess == "Linux (Ubuntu)"

    @pytest.mark.unit
    def test_does_not_overwrite_existing_os_guess(self):
        host = _host_with_ssh("OpenSSH 8.9p1 Ubuntu-3")
        host.os_guess = "Linux 5.4"  # already set (e.g. from nmap -O in future)
        enrich_os_guesses([host])
        assert host.os_guess == "Linux 5.4"

    @pytest.mark.unit
    def test_mixed_list(self):
        h1 = _host_with_ssh("OpenSSH 8.4p1 Debian-2")
        h1.os_guess = ""
        h2 = NmapHost(ip="192.168.1.2")  # no ports, no inference possible
        h2.os_guess = ""
        enrich_os_guesses([h1, h2])
        assert h1.os_guess == "Linux (Debian)"
        assert h2.os_guess == ""


# ═══════════════════════════════════════════════════════════════════════════════
# dns_lookup — resolve_hostnames()
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveHostnames:
    @pytest.mark.unit
    def test_fills_missing_hostname_via_rdns(self):
        host = NmapHost(ip="192.168.1.1", hostname="")
        with patch(
            "app.scanner.dns_lookup.socket.gethostbyaddr",
            return_value=("router.local", [], ["192.168.1.1"]),
        ):
            resolve_hostnames([host])
        assert host.hostname == "router.local"

    @pytest.mark.unit
    def test_does_not_overwrite_existing_hostname(self):
        host = NmapHost(ip="192.168.1.1", hostname="already-named.local")
        with patch("app.scanner.dns_lookup.socket.gethostbyaddr") as mock_dns:
            resolve_hostnames([host])
        mock_dns.assert_not_called()
        assert host.hostname == "already-named.local"

    @pytest.mark.unit
    def test_gracefully_handles_no_ptr_record(self):
        host = NmapHost(ip="192.168.1.1", hostname="")
        with patch("app.scanner.dns_lookup.socket.gethostbyaddr", side_effect=OSError("no PTR")):
            resolve_hostnames([host])
        assert host.hostname == ""

    @pytest.mark.unit
    def test_gracefully_handles_timeout(self):
        host = NmapHost(ip="192.168.1.1", hostname="")
        with patch("app.scanner.dns_lookup.socket.gethostbyaddr", side_effect=TimeoutError):
            resolve_hostnames([host])
        assert host.hostname == ""

    @pytest.mark.unit
    def test_only_queries_hosts_without_hostname(self):
        h1 = NmapHost(ip="192.168.1.1", hostname="existing.local")
        h2 = NmapHost(ip="192.168.1.2", hostname="")
        with patch(
            "app.scanner.dns_lookup.socket.gethostbyaddr",
            return_value=("resolved.local", [], []),
        ) as mock_dns:
            resolve_hostnames([h1, h2])
        mock_dns.assert_called_once_with("192.168.1.2")
        assert h2.hostname == "resolved.local"

    @pytest.mark.unit
    def test_empty_list_is_noop(self):
        with patch("app.scanner.dns_lookup.socket.gethostbyaddr") as mock_dns:
            resolve_hostnames([])
        mock_dns.assert_not_called()

    @pytest.mark.unit
    def test_resolves_multiple_hosts_concurrently(self):
        """All hosts in the list should be resolved regardless of concurrency."""
        hosts = [NmapHost(ip=f"192.168.1.{i}", hostname="") for i in range(1, 6)]

        def fake_rdns(ip):
            return (f"host-{ip.split('.')[-1]}.local", [], [ip])

        with patch("app.scanner.dns_lookup.socket.gethostbyaddr", side_effect=fake_rdns):
            resolve_hostnames(hosts)

        for i, host in enumerate(hosts, 1):
            assert host.hostname == f"host-{i}.local"
