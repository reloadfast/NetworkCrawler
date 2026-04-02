"""
service_probe.py — Lightweight HTTP banner probing for discovered web ports.

Fetches the HTTP Server response header from open web ports and populates
port.version_banner in-place.  Used instead of nmap -sV so the scan never
makes a TCP connection to port 22, avoiding the noisy sshd log entries and
srclimit_penalise penalties triggered by nmap's SSH banner grab.
"""

from __future__ import annotations

import logging
import ssl
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.scanner.nmap_scan import NmapHost, PortInfo

logger = logging.getLogger(__name__)

_HTTP_PORTS: frozenset[int] = frozenset({80, 8000, 8080, 8880})
_HTTPS_PORTS: frozenset[int] = frozenset({443, 8443, 9443})
_PROBE_TIMEOUT = 3  # seconds per request
_MAX_WORKERS = 10


def probe_http_banners(hosts: list[NmapHost]) -> None:
    """
    For each open web port on each host, attempt an HTTP HEAD request and
    populate port.version_banner with the Server response header (in-place).

    Ports that already have a version_banner are skipped.  All network
    failures are silently swallowed — a missing banner is not an error.
    """
    tasks: list[tuple[PortInfo, str, str, int]] = []
    for host in hosts:
        for port in host.ports:
            if port.version_banner:
                continue
            scheme = _pick_scheme(port)
            if scheme is None:
                continue
            tasks.append((port, scheme, host.ip, port.port_number))

    if not tasks:
        return

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {
            pool.submit(_fetch_server_header, scheme, ip, port_num): port_obj
            for port_obj, scheme, ip, port_num in tasks
        }
        for future in as_completed(futures):
            port_obj = futures[future]
            banner = future.result()
            if banner:
                port_obj.version_banner = banner
                logger.debug("HTTP banner for port %d: %s", port_obj.port_number, banner)


def _pick_scheme(port: PortInfo) -> str | None:
    """Return 'http' or 'https' if the port looks like a web port, else None."""
    if port.port_number in _HTTPS_PORTS or port.service_name in ("https", "ssl"):
        return "https"
    if port.port_number in _HTTP_PORTS or port.service_name in ("http", "http-alt"):
        return "http"
    return None


def _fetch_server_header(scheme: str, ip: str, port: int) -> str:
    """Return the Server response header value, or '' on any network error."""
    url = f"{scheme}://{ip}:{port}/"
    try:
        req = urllib.request.Request(url, method="HEAD")  # noqa: S310 — LAN IPs only; SSRF not a concern in a local network scanner
        ctx = _ssl_no_verify_context() if scheme == "https" else None
        with urllib.request.urlopen(req, timeout=_PROBE_TIMEOUT, context=ctx) as resp:  # noqa: S310 -- LAN IPs only; scheme is always http or https, never file or custom
            return resp.headers.get("Server", "")
    except Exception:  # noqa: BLE001 — connection refused, timeout, redirect loops, etc.
        return ""


def _ssl_no_verify_context() -> ssl.SSLContext:
    """Return an SSL context that skips cert verification for LAN self-signed certs."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
