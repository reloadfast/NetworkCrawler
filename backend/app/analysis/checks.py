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
  check_rdp_exposed          — port 3389 open                 high
  check_vnc_exposed          — port 5900 open                 high
  check_mqtt_open            — port 1883 open (no TLS)        medium
  check_open_dns_resolver    — port 53 open                   medium
  check_modbus_open          — port 502 open                  high
  check_snmp_exposed         — port 161/udp open              high
  check_redis_exposed        — port 6379 open                 critical
  check_docker_daemon_tcp    — port 2375 open (no TLS)        critical
  check_docker_daemon_tls    — port 2376 open (TLS)           high
  check_elasticsearch_open   — port 9200 open                 high
  check_portainer_exposed    — ports 9000/9443 open           medium
  check_home_assistant_exposed — port 8123 open               medium
  check_tftp_open            — port 69/udp open               medium
  check_wireguard_vpn        — port 51820/udp open            low
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


def check_rdp_exposed(device: Device) -> list[RiskData]:
    """HIGH — RDP (port 3389) exposed on the network."""
    ports = _has_port(device, 3389)
    if not ports:
        return []
    return [
        RiskData(
            check_id="rdp_exposed",
            severity="high",
            title="RDP port exposed",
            description=(
                f"Device {device.ip_address} has RDP (port 3389/tcp) open. "
                "RDP is a common target for brute-force and ransomware attacks. "
                "Restrict access to trusted hosts only, or use a VPN."
            ),
        )
    ]


def check_vnc_exposed(device: Device) -> list[RiskData]:
    """HIGH — VNC (port 5900) exposed on the network."""
    ports = _has_port(device, 5900)
    if not ports:
        return []
    return [
        RiskData(
            check_id="vnc_exposed",
            severity="high",
            title="VNC port exposed",
            description=(
                f"Device {device.ip_address} has VNC (port 5900/tcp) open. "
                "VNC connections are often unencrypted and rely on weak passwords. "
                "Tunnel VNC through SSH or a VPN, or disable it if not in use."
            ),
        )
    ]


def check_mqtt_open(device: Device) -> list[RiskData]:
    """MEDIUM — MQTT broker (port 1883) open without TLS."""
    ports = _has_port(device, 1883)
    if not ports:
        return []
    return [
        RiskData(
            check_id="mqtt_open",
            severity="medium",
            title="Unencrypted MQTT broker open",
            description=(
                f"Device {device.ip_address} has an MQTT broker (port 1883/tcp) open. "
                "Port 1883 is the plaintext MQTT port. Use port 8883 (MQTT over TLS) "
                "and configure broker authentication to prevent unauthorised access."
            ),
        )
    ]


def check_open_dns_resolver(device: Device) -> list[RiskData]:
    """MEDIUM — DNS service (port 53) open; potential open resolver."""
    tcp_ports = _has_port(device, 53, protocol="tcp")
    udp_ports = _has_port(device, 53, protocol="udp")
    if not tcp_ports and not udp_ports:
        return []
    return [
        RiskData(
            check_id="open_dns_resolver",
            severity="medium",
            title="DNS service open — verify it is not an open resolver",
            description=(
                f"Device {device.ip_address} has DNS (port 53) open. "
                "If this device is not intended to be a DNS server, disable the service. "
                "If it is a DNS server, ensure it only answers queries for authorised "
                "clients to prevent use as an open resolver in amplification attacks."
            ),
        )
    ]


def check_modbus_open(device: Device) -> list[RiskData]:
    """HIGH — Modbus (port 502) open; ICS/SCADA protocol on a home LAN."""
    ports = _has_port(device, 502)
    if not ports:
        return []
    return [
        RiskData(
            check_id="modbus_open",
            severity="high",
            title="Modbus/ICS port open",
            description=(
                f"Device {device.ip_address} has Modbus (port 502/tcp) open. "
                "Modbus is an industrial control system protocol with no built-in "
                "authentication. Its presence on a home LAN is unusual and potentially "
                "dangerous. Verify the device and disable the service if not required."
            ),
        )
    ]


def check_snmp_exposed(device: Device) -> list[RiskData]:
    """HIGH — SNMP (port 161/udp) open; default community string leaks device info."""
    ports = _has_port(device, 161, protocol="udp")
    if not ports:
        return []
    return [
        RiskData(
            check_id="snmp_exposed",
            severity="high",
            title="SNMP port open",
            description=(
                f"Device {device.ip_address} has SNMP (port 161/udp) open. "
                "Devices using the default 'public' community string expose full device "
                "information to anyone on the network. Change the community string or "
                "switch to SNMPv3 with authentication and encryption."
            ),
        )
    ]


def check_redis_exposed(device: Device) -> list[RiskData]:
    """CRITICAL — Redis (port 6379) open; no authentication by default."""
    ports = _has_port(device, 6379)
    if not ports:
        return []
    return [
        RiskData(
            check_id="redis_exposed",
            severity="critical",
            title="Redis database port open",
            description=(
                f"Device {device.ip_address} has Redis (port 6379/tcp) open. "
                "Redis has no authentication enabled by default, and the CONFIG SET "
                "command can be used to write arbitrary files and gain remote code "
                "execution. Bind Redis to 127.0.0.1 and require a strong password."
            ),
        )
    ]


def check_docker_daemon_tcp(device: Device) -> list[RiskData]:
    """CRITICAL — Docker TCP daemon (port 2375) open; unauthenticated API."""
    ports = _has_port(device, 2375)
    if not ports:
        return []
    return [
        RiskData(
            check_id="docker_daemon_tcp",
            severity="critical",
            title="Docker daemon exposed without TLS",
            description=(
                f"Device {device.ip_address} has the Docker daemon API (port 2375/tcp) "
                "open without TLS. This allows anyone on the network to run containers, "
                "mount the host filesystem, and gain full root access to the host. "
                "Disable the TCP listener or enable TLS client authentication immediately."
            ),
        )
    ]


def check_docker_daemon_tls(device: Device) -> list[RiskData]:
    """HIGH — Docker TLS daemon (port 2376) open; verify TLS is properly configured."""
    ports = _has_port(device, 2376)
    if not ports:
        return []
    return [
        RiskData(
            check_id="docker_daemon_tls",
            severity="high",
            title="Docker daemon TLS port open",
            description=(
                f"Device {device.ip_address} has the Docker daemon TLS port (2376/tcp) "
                "open. While TLS is required on this port, it still exposes the Docker "
                "API remotely. Verify that client certificate authentication is enforced "
                "and restrict access to trusted hosts only."
            ),
        )
    ]


def check_elasticsearch_open(device: Device) -> list[RiskData]:
    """HIGH — Elasticsearch HTTP (port 9200) open; historically unauthenticated."""
    ports = _has_port(device, 9200)
    if not ports:
        return []
    return [
        RiskData(
            check_id="elasticsearch_open",
            severity="high",
            title="Elasticsearch HTTP port open",
            description=(
                f"Device {device.ip_address} has Elasticsearch (port 9200/tcp) open. "
                "Older versions of Elasticsearch had no authentication, leading to "
                "widespread data breaches. Ensure X-Pack security is enabled, require "
                "authentication, and restrict network access to trusted hosts."
            ),
        )
    ]


def check_portainer_exposed(device: Device) -> list[RiskData]:
    """MEDIUM — Portainer admin UI (ports 9000/9443) open."""
    ports = _has_port(device, 9000) + _has_port(device, 9443)
    if not ports:
        return []
    port_list = ", ".join(str(p.port_number) for p in ports)
    return [
        RiskData(
            check_id="portainer_exposed",
            severity="medium",
            title="Portainer Docker management UI exposed",
            description=(
                f"Device {device.ip_address} has Portainer (port(s) {port_list}) open. "
                "Portainer provides a web UI for managing the entire Docker stack. "
                "Ensure a strong admin password is set, enable HTTPS only, and restrict "
                "access to trusted hosts with a firewall rule."
            ),
        )
    ]


def check_home_assistant_exposed(device: Device) -> list[RiskData]:
    """MEDIUM — Home Assistant (port 8123) open on the LAN."""
    ports = _has_port(device, 8123)
    if not ports:
        return []
    return [
        RiskData(
            check_id="home_assistant_exposed",
            severity="medium",
            title="Home Assistant web interface exposed",
            description=(
                f"Device {device.ip_address} has Home Assistant (port 8123/tcp) open. "
                "Home Assistant controls smart home devices and may have access to "
                "locks, cameras, and alarms. Ensure a strong password is set, enable "
                "two-factor authentication, and avoid exposing this port to the internet."
            ),
        )
    ]


def check_tftp_open(device: Device) -> list[RiskData]:
    """MEDIUM — TFTP (port 69/udp) open; no authentication protocol."""
    ports = _has_port(device, 69, protocol="udp")
    if not ports:
        return []
    return [
        RiskData(
            check_id="tftp_open",
            severity="medium",
            title="TFTP port open",
            description=(
                f"Device {device.ip_address} has TFTP (port 69/udp) open. "
                "TFTP (Trivial File Transfer Protocol) has no authentication mechanism "
                "and transfers files in plaintext. It is commonly used for network "
                "booting and router firmware — disable it if not actively needed."
            ),
        )
    ]


def check_wireguard_vpn(device: Device) -> list[RiskData]:
    """LOW — WireGuard VPN (port 51820/udp) detected; informational."""
    ports = _has_port(device, 51820, protocol="udp")
    if not ports:
        return []
    return [
        RiskData(
            check_id="wireguard_vpn",
            severity="low",
            title="WireGuard VPN port open",
            description=(
                f"Device {device.ip_address} has WireGuard VPN (port 51820/udp) open. "
                "This is informational — WireGuard is a modern, secure VPN protocol. "
                "Ensure only authorised peers are configured and keep WireGuard updated."
            ),
        )
    ]


# ── Compound / pattern-based checks ──────────────────────────────────────────


def check_multiple_admin_panels(device: Device) -> list[RiskData]:
    """MEDIUM — 3+ management ports open; unusually large admin surface."""
    admin_ports = _has_port(device, 80, 8080, 8443, 9000, 9443, 9200, 5900, 3389, 22)
    if len(admin_ports) < 3:  # noqa: PLR2004 — 3 is the meaningful threshold
        return []
    port_list = ", ".join(str(p.port_number) for p in admin_ports)
    return [
        RiskData(
            check_id="multiple_admin_panels",
            severity="medium",
            title="Multiple admin/management ports open",
            description=(
                f"Device {device.ip_address} has {len(admin_ports)} management or "
                f"admin ports open simultaneously ({port_list}). "
                "Each extra management interface is an additional attack surface. "
                "Disable any admin panels or remote-access services that are not "
                "actively required."
            ),
        )
    ]


def check_database_and_web_exposed(device: Device) -> list[RiskData]:
    """HIGH — database port open alongside a public-facing web port."""
    db_ports = _has_port(device, 3306, 5432, 6379, 27017, 1433, 5984)
    web_ports = _has_port(device, 80, 8080)
    if not db_ports or not web_ports:
        return []
    db_list = ", ".join(str(p.port_number) for p in db_ports)
    web_list = ", ".join(str(p.port_number) for p in web_ports)
    return [
        RiskData(
            check_id="database_and_web_exposed",
            severity="high",
            title="Database and unencrypted web port open together",
            description=(
                f"Device {device.ip_address} has database port(s) ({db_list}) open "
                f"alongside unencrypted web port(s) ({web_list}). "
                "An attacker who exploits the web layer may pivot directly to the "
                "database. The database port should not be network-accessible, and "
                "all web traffic should be served over HTTPS."
            ),
        )
    ]


def check_cleartext_credential_surface(device: Device) -> list[RiskData]:
    """HIGH — Telnet, FTP, and HTTP all open; maximum cleartext exposure."""
    telnet = _has_port(device, 23)
    ftp = _has_port(device, 21)
    http = _has_port(device, 80)
    if not (telnet and ftp and http):
        return []
    return [
        RiskData(
            check_id="cleartext_credential_surface",
            severity="high",
            title="Cleartext credential surface (Telnet + FTP + HTTP all open)",
            description=(
                f"Device {device.ip_address} has Telnet (23), FTP (21), and HTTP (80) "
                "all open simultaneously. Every one of these protocols transmits "
                "credentials and data in plaintext. An attacker on the same network "
                "can capture login credentials with a passive packet capture. "
                "Disable all three and replace with SSH, SFTP/SCP, and HTTPS."
            ),
        )
    ]


def check_remote_access_no_encryption(device: Device) -> list[RiskData]:
    """HIGH — RDP or VNC open with no TLS service detected on the device."""
    rdp = _has_port(device, 3389)
    vnc = _has_port(device, 5900)
    if not (rdp or vnc):
        return []
    # If any TLS-capable port is open, the device at least has *some* encrypted path
    tls_ports = _has_port(device, 443, 8443, 22)
    if tls_ports:
        return []
    remote_list = ", ".join(str(p.port_number) for p in (rdp + vnc))
    return [
        RiskData(
            check_id="remote_access_no_encryption",
            severity="high",
            title="Remote desktop open with no encrypted alternative",
            description=(
                f"Device {device.ip_address} has remote access port(s) ({remote_list}) "
                "open and no TLS-encrypted service (443/8443/22) detected. "
                "RDP and VNC can leak screen content and credentials if not tunnelled "
                "through an encrypted channel such as SSH or a VPN. "
                "Disable direct RDP/VNC exposure and access the device via a VPN or "
                "SSH tunnel instead."
            ),
        )
    ]


def check_ssh_and_telnet_both_open(device: Device) -> list[RiskData]:
    """MEDIUM — SSH and Telnet both open; Telnet likely a forgotten legacy service."""
    ssh = _has_port(device, 22)
    telnet = _has_port(device, 23)
    if not (ssh and telnet):
        return []
    return [
        RiskData(
            check_id="ssh_and_telnet_both_open",
            severity="medium",
            title="SSH and Telnet both open",
            description=(
                f"Device {device.ip_address} has both SSH (22) and Telnet (23) open. "
                "SSH is the secure replacement for Telnet — having both suggests "
                "Telnet was never disabled after SSH was enabled. "
                "Disable Telnet immediately; any legitimate remote access should use "
                "SSH with key-based authentication only."
            ),
        )
    ]


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
    check_rdp_exposed,
    check_vnc_exposed,
    check_mqtt_open,
    check_open_dns_resolver,
    check_modbus_open,
    check_snmp_exposed,
    check_redis_exposed,
    check_docker_daemon_tcp,
    check_docker_daemon_tls,
    check_elasticsearch_open,
    check_portainer_exposed,
    check_home_assistant_exposed,
    check_tftp_open,
    check_wireguard_vpn,
    # Compound / pattern checks
    check_multiple_admin_panels,
    check_database_and_web_exposed,
    check_cleartext_credential_surface,
    check_remote_access_no_encryption,
    check_ssh_and_telnet_both_open,
]
