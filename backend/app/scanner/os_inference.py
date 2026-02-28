"""
os_inference.py — Passive OS hints from nmap service/version banners.

infer_os() is the single public function.  It inspects a host's port
banners and service names to produce a best-effort OS label without
requiring elevated privileges or -O.

All logic is pure string matching so it is fully unit-testable.
"""

from __future__ import annotations

import re

from app.scanner.nmap_scan import NmapHost, PortInfo

# ── SSH banner patterns ───────────────────────────────────────────────────────
# OpenSSH embeds OS/distro hints in the version comment field, e.g.
#   "OpenSSH 8.9p1 Ubuntu-3ubuntu0.6"
#   "OpenSSH 8.4p1 Debian-2+deb11u2"
#   "OpenSSH 7.9 (protocol 2.0)"  ← FreeBSD default
#   "OpenSSH_for_Windows_8.1"

_SSH_OS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"Ubuntu", re.IGNORECASE), "Linux (Ubuntu)"),
    (re.compile(r"Debian", re.IGNORECASE), "Linux (Debian)"),
    (re.compile(r"Raspbian", re.IGNORECASE), "Linux (Raspbian)"),
    (re.compile(r"CentOS", re.IGNORECASE), "Linux (CentOS)"),
    (re.compile(r"Fedora", re.IGNORECASE), "Linux (Fedora)"),
    (re.compile(r"openSUSE|SUSE", re.IGNORECASE), "Linux (openSUSE)"),
    (re.compile(r"FreeBSD", re.IGNORECASE), "FreeBSD"),
    (re.compile(r"NetBSD", re.IGNORECASE), "NetBSD"),
    (re.compile(r"OpenBSD", re.IGNORECASE), "OpenBSD"),
    (re.compile(r"for_Windows|Windows", re.IGNORECASE), "Windows"),
    # Generic Linux when distro is absent but OpenSSH is present
    (re.compile(r"OpenSSH", re.IGNORECASE), "Linux"),
]

# ── HTTP Server header patterns ───────────────────────────────────────────────
_HTTP_OS_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"DD-WRT", re.IGNORECASE), "Linux (DD-WRT)"),
    (re.compile(r"OpenWrt", re.IGNORECASE), "Linux (OpenWrt)"),
    (re.compile(r"Tomato", re.IGNORECASE), "Linux (Tomato)"),
    (re.compile(r"Synology", re.IGNORECASE), "Linux (Synology DSM)"),
    (re.compile(r"QNAP", re.IGNORECASE), "Linux (QNAP QTS)"),
    (re.compile(r"Unraid", re.IGNORECASE), "Linux (Unraid)"),
    (re.compile(r"FreeNAS|TrueNAS", re.IGNORECASE), "FreeBSD (TrueNAS)"),
    (re.compile(r"lighttpd", re.IGNORECASE), "Linux"),
    (re.compile(r"mini_httpd", re.IGNORECASE), "Embedded Linux"),
    (re.compile(r"Cisco", re.IGNORECASE), "Cisco IOS"),
    (re.compile(r"MikroTik", re.IGNORECASE), "MikroTik RouterOS"),
    (re.compile(r"Windows", re.IGNORECASE), "Windows"),
]

# ── Service-name fallbacks ────────────────────────────────────────────────────
_SERVICE_OS_HINTS: dict[str, str] = {
    "msrpc": "Windows",
    "netbios-ssn": "Windows",
    "microsoft-ds": "Windows",
    "ms-wbt-server": "Windows",  # RDP
}


def _match_patterns(text: str, patterns: list[tuple[re.Pattern, str]]) -> str:
    for pattern, label in patterns:
        if pattern.search(text):
            return label
    return ""


def infer_os(host: NmapHost) -> str:
    """
    Return a best-effort OS label for *host* derived from its port banners.

    Returns empty string when nothing can be inferred.  Does not modify
    the host object — callers decide whether to apply the result.
    """
    for port in host.ports:
        # SSH banner is the most reliable source
        if port.service_name == "ssh" and port.version_banner:
            label = _match_patterns(port.version_banner, _SSH_OS_PATTERNS)
            if label:
                return label

    for port in host.ports:
        # HTTP Server header
        if port.service_name in ("http", "http-alt", "https") and port.version_banner:
            label = _match_patterns(port.version_banner, _HTTP_OS_PATTERNS)
            if label:
                return label

    for port in host.ports:
        # Service-name hints (Windows RPC/SMB/RDP)
        hint = _SERVICE_OS_HINTS.get(port.service_name, "")
        if hint:
            return hint

    return ""


def enrich_os_guesses(hosts: list[NmapHost]) -> None:
    """
    Fill in missing os_guess on *hosts* via passive banner inference (in-place).

    Only updates hosts where os_guess is currently empty.
    """
    for host in hosts:
        if not host.os_guess:
            host.os_guess = infer_os(host)
