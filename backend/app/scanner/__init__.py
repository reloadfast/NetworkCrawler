"""
scanner/__init__.py — Public interface for the scanner package.

The orchestrate_scan() function is the single entry point called by the
scheduler and the manual-trigger API endpoint.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from app.scanner.arp_scan import ArpHost, run_arp_scan
from app.scanner.dns_lookup import resolve_hostnames
from app.scanner.nmap_scan import NmapHost, run_nmap_scan
from app.scanner.os_inference import enrich_os_guesses

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Merged result of one full LAN scan cycle."""

    hosts: list[NmapHost] = field(default_factory=list)
    """nmap-enriched hosts (ip, mac, hostname, os_guess, ports)."""

    arp_only: list[ArpHost] = field(default_factory=list)
    """Hosts found by arp-scan that nmap returned no data for."""

    warnings: list[str] = field(default_factory=list)
    """Non-fatal warnings accumulated during the scan (e.g. nmap failure)."""


def orchestrate_scan(
    interface: str | None = None,
    subnet: str | None = None,
) -> ScanResult:
    """
    Run a full scan cycle:
      1. arp-scan  → enumerate live IPs
      2. nmap      → service/version/OS detection on those IPs
      3. Merge     → attach MAC/vendor from arp to nmap results

    Returns a ScanResult.  Raises RuntimeError on tool failure.
    """
    iface = interface or os.environ.get("NETWORK_INTERFACE", "eth0")
    net = subnet or os.environ.get("SCAN_SUBNET", "192.168.1.0/24")

    logger.info("Starting ARP scan on %s / %s", iface, net)
    arp_hosts = run_arp_scan(interface=iface, subnet=net)
    logger.info("ARP scan found %d hosts", len(arp_hosts))

    if not arp_hosts:
        return ScanResult()

    ip_list = [h.ip for h in arp_hosts]
    arp_by_ip = {h.ip: h for h in arp_hosts}

    logger.info("Starting nmap scan on %d hosts", len(ip_list))
    nmap_hosts: list[NmapHost] = []
    warnings: list[str] = []
    try:
        nmap_hosts = run_nmap_scan(hosts=ip_list, interface=iface)
        logger.info("nmap scan returned %d hosts", len(nmap_hosts))
    except RuntimeError as exc:
        msg = f"nmap unavailable — showing ARP-only results: {exc}"
        logger.warning(msg)
        warnings.append(msg)

    # Enrich nmap results with MAC / vendor from arp-scan
    nmap_ips: set[str] = set()
    for nh in nmap_hosts:
        nmap_ips.add(nh.ip)
        if not nh.mac and nh.ip in arp_by_ip:
            nh.mac = arp_by_ip[nh.ip].mac

    # Hostname fallback: reverse DNS for hosts nmap couldn't name
    resolve_hostnames(nmap_hosts)

    # Passive OS inference from service/version banners
    enrich_os_guesses(nmap_hosts)

    # Hosts arp found but nmap returned nothing for (e.g. ICMP-filtered)
    arp_only = [h for h in arp_hosts if h.ip not in nmap_ips]

    return ScanResult(hosts=nmap_hosts, arp_only=arp_only, warnings=warnings)
