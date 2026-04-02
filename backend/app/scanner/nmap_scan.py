"""
nmap_scan.py — Invoke nmap for service/version/OS detection and parse XML output.

run_nmap_scan() is the only function that touches subprocess; everything else
is pure XML parsing so it can be integration-tested with fixture files.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class PortInfo:
    port_number: int
    protocol: str
    state: str
    service_name: str = ""
    version_banner: str = ""


@dataclass
class NmapHost:
    ip: str
    mac: str = ""
    hostname: str = ""
    os_guess: str = ""
    ports: list[PortInfo] = field(default_factory=list)


# ── Public API ────────────────────────────────────────────────────────────────


def run_nmap_scan(
    hosts: list[str],
    interface: str | None = None,
) -> list[NmapHost]:
    """
    Run nmap --top-ports 1000 -oX against *hosts* and return parsed results.

    -sV (service version detection) is intentionally omitted: it makes active
    TCP connections to every open port — including SSH — to grab banners, which
    triggers sshd's srclimit_penalise on each scan cycle.  HTTP/HTTPS banners
    are fetched separately via service_probe.probe_http_banners() using urllib.

    -O (OS detection) is also omitted: nmap hard-codes geteuid()==0 for OS
    fingerprinting regardless of file capabilities, so it always quits when
    running as non-root uid 1000.

    Uses a temporary file for XML output so the subprocess and parser are
    independently testable.  Raises RuntimeError on non-zero exit.
    """
    if not hosts:
        return []

    iface = interface or os.environ.get("NETWORK_INTERFACE", "eth0")
    host_timeout = os.environ.get("NMAP_HOST_TIMEOUT", "30s")

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        xml_path = tmp.name

    try:
        cmd = [
            "nmap",
            "--host-timeout",
            host_timeout,
            "--top-ports",
            "1000",
            "-e",
            iface,
            "-oX",
            xml_path,
            *hosts,
        ]
        logger.debug("nmap command: %s", cmd)

        result = subprocess.run(  # noqa: S603 — argv list, no shell injection
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            raise RuntimeError(f"nmap failed (exit {result.returncode}): {result.stderr.strip()}")

        return parse_nmap_xml(Path(xml_path).read_text())
    finally:
        Path(xml_path).unlink(missing_ok=True)


def parse_nmap_xml(xml_text: str) -> list[NmapHost]:
    """
    Parse nmap XML output (``-oX``) into a list of NmapHost objects.

    Only 'up' hosts with at least one port entry are included; filtered
    ports (state != 'open') are silently skipped.

    Raises RuntimeError on malformed/truncated XML so the caller's partial-scan
    handler can continue with ARP-only results rather than crashing.
    """
    try:
        root = ET.fromstring(xml_text)  # noqa: S314 — input is local nmap output, not user data
    except ET.ParseError as exc:
        raise RuntimeError(f"nmap XML is malformed or truncated: {exc}") from exc
    results: list[NmapHost] = []

    for host_el in root.findall("host"):
        status = host_el.find("status")
        if status is None or status.get("state") != "up":
            continue

        host = _parse_host(host_el)
        results.append(host)

    return results


# ── Private helpers ───────────────────────────────────────────────────────────


def _parse_host(host_el: ET.Element) -> NmapHost:
    ip = ""
    mac = ""

    for addr in host_el.findall("address"):
        atype = addr.get("addrtype", "")
        if atype == "ipv4":
            ip = addr.get("addr", "")
        elif atype == "mac":
            mac = addr.get("addr", "")

    hostname = _parse_hostname(host_el)
    os_guess = _parse_os(host_el)
    ports = _parse_ports(host_el)

    return NmapHost(ip=ip, mac=mac, hostname=hostname, os_guess=os_guess, ports=ports)


def _parse_hostname(host_el: ET.Element) -> str:
    hostnames = host_el.find("hostnames")
    if hostnames is None:
        return ""
    for hn in hostnames.findall("hostname"):
        name = hn.get("name", "")
        if name:
            return name
    return ""


def _parse_os(host_el: ET.Element) -> str:
    os_el = host_el.find("os")
    if os_el is None:
        return ""
    # Prefer the match with the highest accuracy
    best: tuple[int, str] = (0, "")
    for match in os_el.findall("osmatch"):
        accuracy = int(match.get("accuracy", "0"))
        name = match.get("name", "")
        if accuracy > best[0]:
            best = (accuracy, name)
    return best[1]


def _parse_ports(host_el: ET.Element) -> list[PortInfo]:
    ports_el = host_el.find("ports")
    if ports_el is None:
        return []

    ports: list[PortInfo] = []
    for port_el in ports_el.findall("port"):
        state_el = port_el.find("state")
        if state_el is None or state_el.get("state") != "open":
            continue

        service_el = port_el.find("service")
        service_name = ""
        version_banner = ""
        if service_el is not None:
            service_name = service_el.get("name", "")
            product = service_el.get("product", "")
            version = service_el.get("version", "")
            extra = service_el.get("extrainfo", "")
            parts = filter(None, [product, version, extra])
            version_banner = " ".join(parts)

        ports.append(
            PortInfo(
                port_number=int(port_el.get("portid", "0")),
                protocol=port_el.get("protocol", "tcp"),
                state=state_el.get("state", ""),
                service_name=service_name,
                version_banner=version_banner,
            )
        )
    return ports
