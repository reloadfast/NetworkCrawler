"""
arp_scan.py — Invoke arp-scan to enumerate live hosts on the LAN.

All subprocess calls go through run_arp_scan(); the rest of the module is
pure parsing so it can be unit-tested without a real network.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Matches a line like:  192.168.1.1\taa:bb:cc:dd:ee:ff\tVendor Name
# Vendor column is optional — arp-scan omits the tab when the vendor is unknown.
_ARP_LINE_RE = re.compile(
    r"^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\t(?P<mac>[0-9a-fA-F:]{17})(?:\t(?P<vendor>.*))?$"
)


@dataclass
class ArpHost:
    ip: str
    mac: str
    vendor: str = ""


def run_arp_scan(
    interface: str | None = None,
    subnet: str | None = None,
) -> list[ArpHost]:
    """
    Run arp-scan and return a list of discovered hosts.

    Falls back to env vars NETWORK_INTERFACE / SCAN_SUBNET when arguments
    are not provided.  Raises RuntimeError if arp-scan exits non-zero.
    """
    iface = interface or os.environ.get("NETWORK_INTERFACE", "eth0")
    target = subnet or os.environ.get("SCAN_SUBNET", "192.168.1.0/24")

    cmd = ["arp-scan", "--interface", iface, target]
    logger.debug("arp-scan command: %s", cmd)

    result = subprocess.run(  # noqa: S603 — argv list, no shell injection
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode not in (0, 1):  # arp-scan returns 1 when no hosts found
        raise RuntimeError(f"arp-scan failed (exit {result.returncode}): {result.stderr.strip()}")

    return parse_arp_output(result.stdout)


def parse_arp_output(output: str) -> list[ArpHost]:
    """Parse raw arp-scan stdout into ArpHost objects."""
    hosts: list[ArpHost] = []
    for line in output.splitlines():
        m = _ARP_LINE_RE.match(line.strip())
        if m:
            hosts.append(ArpHost(ip=m["ip"], mac=m["mac"], vendor=(m["vendor"] or "").strip()))
    return hosts
