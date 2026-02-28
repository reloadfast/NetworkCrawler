"""
dns_lookup.py — Reverse DNS lookup fallback for hostname resolution.

resolve_hostnames() is the only public function; it operates on a list of
NmapHost objects in-place and fills in hostname where nmap returned none.
Pure socket calls — no subprocess, no elevated privileges required.
"""

from __future__ import annotations

import logging
import signal
import socket
from contextlib import contextmanager

from app.scanner.nmap_scan import NmapHost

logger = logging.getLogger(__name__)

_LOOKUP_TIMEOUT_SECONDS = 1


@contextmanager
def _timeout(seconds: int):
    """SIGALRM-based timeout context for blocking socket calls."""

    def _handler(signum, frame):  # noqa: ANN001 — signal handler signature is fixed by the stdlib
        raise TimeoutError

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def _rdns(ip: str) -> str:
    """
    Return the PTR hostname for *ip*, or empty string on any failure.

    Uses a SIGALRM timeout so a single slow DNS server cannot stall
    the entire scan cycle.
    """
    try:
        with _timeout(_LOOKUP_TIMEOUT_SECONDS):
            hostname, _, _ = socket.gethostbyaddr(ip)
            return hostname
    except (OSError, TimeoutError):
        return ""


def resolve_hostnames(hosts: list[NmapHost]) -> None:
    """
    Fill in missing hostnames on *hosts* via reverse DNS (in-place).

    Only queries IPs where nmap returned no hostname.  Each lookup is
    individually timeout-guarded so a non-responsive resolver doesn't
    block the scan.
    """
    missing = [h for h in hosts if not h.hostname]
    if not missing:
        return

    logger.debug("Reverse DNS lookup for %d host(s) with no hostname", len(missing))
    resolved = 0
    for host in missing:
        name = _rdns(host.ip)
        if name:
            host.hostname = name
            resolved += 1
            logger.debug("rDNS %s → %s", host.ip, name)
        else:
            logger.debug("rDNS %s → (no PTR record)", host.ip)

    logger.info("Reverse DNS resolved %d/%d hostname(s)", resolved, len(missing))
