"""
checks.py — Misconfiguration check functions for Phase 3.

Each check is an independent, pure function that accepts a Device ORM instance
(with .ports pre-loaded) and returns a list of RiskData namedtuples describing
any findings.  No database I/O happens here; the caller (run_checks) persists
the results.

Check catalogue:
  check_telnet_open          — port 23 open                   critical
  check_ftp_open             — port 21 open                   high
  check_unencrypted_http     — port 80 open on mgmt ifaces    medium
  check_upnp_exposed         — port 1900 open on non-routers  medium
  check_ssh_password_auth    — SSH banner hints at pw-auth    medium
  check_smb_open             — ports 445/137-139 open         high
  check_printer_iot_admin    — IoT/printer admin on 80/8080   medium
  check_outdated_banner      — version_banner looks old       low
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from app.models.device import Device

# ── Result type ───────────────────────────────────────────────────────────────


class RiskData(NamedTuple):
    """Lightweight container returned by each check function."""

    check_id: str
    severity: str  # "critical" | "high" | "medium" | "low"
    title: str
    description: str


# ── Helpers ───────────────────────────────────────────────────────────────────

# Vendor strings that strongly suggest a home router / gateway
_ROUTER_VENDORS = frozenset(
    [
        "cisco",
        "ubiquiti",
        "mikrotik",
        "zyxel",
        "netgear",
        "linksys",
        "tp-link",
        "tplink",
        "asus",
        "dlink",
        "d-link",
        "belkin",
        "arris",
        "motorola",
        "actiontec",
        "technicolor",
        "sagemcom",
    ]
)

# OS strings that suggest a NAS device
_NAS_OS_HINTS = frozenset(["synology", "qnap", "freenas", "truenas", "openmediavault", "nas"])

# Service / banner fragments that suggest outdated or EOL software
_OUTDATED_PATTERNS = [
    re.compile(r"\bOpenSSH[_ ]([3-6]\.\d)", re.I),
    re.compile(r"\bvsftpd[_ ](1\.|2\.[0-2])", re.I),
    re.compile(r"\bApache[/ ](1\.|2\.[0-3])", re.I),
    re.compile(r"\bnginx[/ ]0\.", re.I),
    re.compile(r"\bProFTPD[_ ](1\.[0-3])", re.I),
    re.compile(r"\bOpenSSL[/ ](0\.|1\.0)", re.I),
]


def _has_port(device: Device, *port_numbers: int, protocol: str = "tcp") -> list:
    """Return Port objects matching any of the given port numbers and protocol."""
    return [p for p in device.ports if p.port_number in port_numbers and p.protocol == protocol]


def _is_likely_router(device: Device) -> bool:
    vendor = (device.vendor or "").lower()
    return any(r in vendor for r in _ROUTER_VENDORS)


def _is_likely_nas(device: Device) -> bool:
    os_hint = (device.os_guess or "").lower()
    hostname = (device.hostname or "").lower()
    combined = os_hint + " " + hostname
    return any(h in combined for h in _NAS_OS_HINTS)


# ── Check functions ───────────────────────────────────────────────────────────


def check_telnet_open(device: Device) -> list[RiskData]:
    """CRITICAL — Telnet (port 23) transmits all data in plaintext."""
    ports = _has_port(device, 23)
    if not ports:
        return []
    return [
        RiskData(
            check_id="telnet_open",
            severity="critical",
            title="Telnet port open",
            description=(
                f"Device {device.ip_address} has Telnet (port 23/tcp) open. "
                "Telnet transmits credentials and data in cleartext and should be "
                "replaced with SSH immediately."
            ),
        )
    ]


def check_ftp_open(device: Device) -> list[RiskData]:
    """HIGH — FTP (port 21) transmits credentials in plaintext."""
    ports = _has_port(device, 21)
    if not ports:
        return []
    return [
        RiskData(
            check_id="ftp_open",
            severity="high",
            title="FTP port open",
            description=(
                f"Device {device.ip_address} has FTP (port 21/tcp) open. "
                "FTP transmits usernames and passwords in cleartext. "
                "Replace with SFTP or FTPS."
            ),
        )
    ]


def check_unencrypted_http(device: Device) -> list[RiskData]:
    """MEDIUM — Unencrypted HTTP on management interfaces."""
    ports = _has_port(device, 80)
    if not ports:
        return []

    # Only flag when there is also a likely HTTPS equivalent open, or when the
    # service looks like a management UI (admin, web, http).
    port_obj = ports[0]
    service = (port_obj.service_name or "").lower()
    banner = (port_obj.version_banner or "").lower()
    mgmt_hints = ["http", "web", "admin", "lighttpd", "nginx", "apache", "mini_httpd"]
    is_mgmt = any(h in service or h in banner for h in mgmt_hints)

    if not is_mgmt:
        return []

    return [
        RiskData(
            check_id="unencrypted_http",
            severity="medium",
            title="Unencrypted HTTP management interface",
            description=(
                f"Device {device.ip_address} exposes an HTTP management interface "
                "on port 80/tcp without encryption. Credentials submitted via this "
                "interface can be intercepted. Enable HTTPS where possible."
            ),
        )
    ]


def check_upnp_exposed(device: Device) -> list[RiskData]:
    """MEDIUM — UPnP (1900/udp) exposed on a non-router device."""
    if _is_likely_router(device):
        return []
    ports = _has_port(device, 1900, protocol="udp")
    if not ports:
        return []
    return [
        RiskData(
            check_id="upnp_exposed",
            severity="medium",
            title="UPnP exposed on non-router device",
            description=(
                f"Device {device.ip_address} has UPnP (port 1900/udp) open. "
                "UPnP is rarely needed on non-gateway devices and can be exploited "
                "to redirect traffic or open external ports. Disable UPnP on this device."
            ),
        )
    ]


def check_ssh_password_auth(device: Device) -> list[RiskData]:
    """MEDIUM — SSH banner hints that password authentication is enabled."""
    ports = _has_port(device, 22)
    if not ports:
        return []

    port_obj = ports[0]
    banner = (port_obj.version_banner or "").lower()
    service = (port_obj.service_name or "").lower()

    # nmap -sV often includes "protocol 2.0" or similar; a password_auth hint
    # in the banner is rare but some configurations expose it.  We flag any
    # open SSH port as a *reminder* to verify key-only auth, using low confidence.
    if "ssh" not in service and "openssh" not in banner:
        return []

    return [
        RiskData(
            check_id="ssh_password_auth",
            severity="medium",
            title="SSH may allow password authentication",
            description=(
                f"Device {device.ip_address} has SSH (port 22/tcp) open. "
                "Verify that password authentication is disabled in favour of "
                "public-key authentication only (PasswordAuthentication no in sshd_config)."
            ),
        )
    ]


def check_smb_open(device: Device) -> list[RiskData]:
    """HIGH — SMB (445) or NetBIOS (137-139) open on a non-NAS device."""
    if _is_likely_nas(device):
        return []

    smb_ports = _has_port(device, 445)
    netbios_ports = _has_port(device, 137, 138, 139)
    found = smb_ports + netbios_ports
    if not found:
        return []

    port_list = ", ".join(str(p.port_number) for p in found)
    return [
        RiskData(
            check_id="smb_open",
            severity="high",
            title="SMB/NetBIOS ports open on non-NAS device",
            description=(
                f"Device {device.ip_address} has SMB or NetBIOS ports open "
                f"({port_list}/tcp). These protocols are frequently targeted by "
                "ransomware and lateral-movement attacks. Disable file sharing if "
                "not required, or restrict access with a firewall rule."
            ),
        )
    ]


def check_printer_iot_admin(device: Device) -> list[RiskData]:
    """MEDIUM — Printer/IoT admin UI on default ports (80, 8080, 8443)."""
    admin_ports = _has_port(device, 80, 8080, 8443)
    if not admin_ports:
        return []

    # Try to identify IoT/printer characteristics from vendor or OS
    vendor = (device.vendor or "").lower()
    os_hint = (device.os_guess or "").lower()
    iot_hints = [
        "printer",
        "canon",
        "epson",
        "hp",
        "brother",
        "lexmark",
        "xerox",
        "ricoh",
        "camera",
        "hikvision",
        "dahua",
        "foscam",
        "wyze",
        "iot",
        "embedded",
        "rtos",
    ]
    combined = vendor + " " + os_hint
    is_iot = any(h in combined for h in iot_hints)
    if not is_iot:
        return []

    port_list = ", ".join(str(p.port_number) for p in admin_ports)
    return [
        RiskData(
            check_id="printer_iot_admin",
            severity="medium",
            title="Printer/IoT admin UI on default port",
            description=(
                f"Device {device.ip_address} appears to be a printer or IoT device "
                f"with an admin web interface on port(s) {port_list}. "
                "Ensure the default password has been changed and restrict access "
                "to trusted hosts only."
            ),
        )
    ]


def check_outdated_banner(device: Device) -> list[RiskData]:
    """LOW — Service version banner suggests outdated/EOL software."""
    findings: list[RiskData] = []
    for port_obj in device.ports:
        banner = port_obj.version_banner or ""
        for pattern in _OUTDATED_PATTERNS:
            m = pattern.search(banner)
            if m:
                findings.append(
                    RiskData(
                        check_id="outdated_banner",
                        severity="low",
                        title="Potentially outdated service version",
                        description=(
                            f"Device {device.ip_address} port {port_obj.port_number}/tcp "
                            f"reports a service banner matching an outdated version: "
                            f'"{banner}". Update to a supported release to reduce '
                            "exposure to known vulnerabilities."
                        ),
                    )
                )
                break  # one finding per port is sufficient
    return findings


# ── Master list of all checks ─────────────────────────────────────────────────

ALL_CHECKS = [
    check_telnet_open,
    check_ftp_open,
    check_unencrypted_http,
    check_upnp_exposed,
    check_ssh_password_auth,
    check_smb_open,
    check_printer_iot_admin,
    check_outdated_banner,
]
