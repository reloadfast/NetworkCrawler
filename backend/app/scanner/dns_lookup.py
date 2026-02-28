"""
dns_lookup.py — Reverse DNS lookup fallback for hostname resolution.

resolve_hostnames() is the only public function; it operates on a list of
NmapHost objects in-place and fills in hostname where nmap returned none.
Pure socket calls — no subprocess, no elevated privileges required.
"""

from __future__ import annotations

import logging
import socket
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
            futures[pool.submit(_rdns, host.ip)] = host

    resolved = 0
    for future, host in futures.items():
        name = future.result()
        if name:
            host.hostname = name
            resolved += 1
            logger.debug("rDNS %s → %s", host.ip, name)
        else:
            logger.debug("rDNS %s → (no PTR record)", host.ip)

    logger.info("Reverse DNS resolved %d/%d hostname(s)", resolved, len(missing))
