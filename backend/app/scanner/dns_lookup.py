"""
dns_lookup.py — Reverse DNS lookup fallback for hostname resolution.

resolve_hostnames() is the only public function; it operates on a list of
NmapHost objects in-place and fills in hostname where nmap returned none.

Resolution is attempted in two stages per host:
  1. Standard PTR lookup via socket.gethostbyaddr()
  2. mDNS fallback via avahi-resolve (if installed), catching .local names
     that PTR misses — common for IoT, NAS, Raspberry Pis, and Apple devices.
"""

from __future__ import annotations

import logging
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor

from app.scanner.nmap_scan import NmapHost

logger = logging.getLogger(__name__)

_LOOKUP_TIMEOUT_SECONDS = 2
_MAX_WORKERS = 20


def _rdns(ip: str) -> str:
    """
    Return the PTR hostname for *ip*, or empty string on any failure.

    Uses socket.setdefaulttimeout so each lookup is individually bounded.
    """
    try:
        socket.setdefaulttimeout(_LOOKUP_TIMEOUT_SECONDS)
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except OSError:
        return ""
    finally:
        socket.setdefaulttimeout(None)


def _avahi_resolve(ip: str) -> str:
    """
    Return the mDNS hostname for *ip* via avahi-resolve, or empty string.

    Gracefully degrades when avahi-utils is not installed (FileNotFoundError)
    or when the daemon is not running / has no record for the IP.
    """
    try:
        result = subprocess.run(  # noqa: S603 — fixed command list, no user input
            ["avahi-resolve", "--address", ip],  # noqa: S607 — well-known system utility; full path not portable
            capture_output=True,
            text=True,
            timeout=_LOOKUP_TIMEOUT_SECONDS,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Output format: "<ip>\t<hostname>"
            parts = result.stdout.strip().split()
            if len(parts) >= 2:
                return parts[-1].rstrip(".")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return ""


def _resolve(ip: str) -> str:
    """Try PTR first, fall back to avahi-resolve for mDNS/.local names."""
    name = _rdns(ip)
    if not name:
        name = _avahi_resolve(ip)
    return name


def resolve_hostnames(hosts: list[NmapHost]) -> None:
    """
    Fill in missing hostnames on *hosts* via reverse DNS (in-place).

    Only queries IPs where nmap returned no hostname.  All lookups run
    concurrently via a thread pool so a slow resolver doesn't serialise
    the scan cycle.
    """
    missing = [h for h in hosts if not h.hostname]
    if not missing:
        return

    logger.debug("Reverse DNS lookup for %d host(s) with no hostname", len(missing))

    futures = {}
    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(missing))) as pool:
        for host in missing:
            futures[pool.submit(_resolve, host.ip)] = host

    resolved = 0
    for future, host in futures.items():
        name = future.result()
        if name:
            host.hostname = name
            resolved += 1
            logger.debug("DNS %s → %s", host.ip, name)
        else:
            logger.debug("DNS %s → (no record)", host.ip)

    logger.info("Reverse DNS resolved %d/%d hostname(s)", resolved, len(missing))
