"""Hardening recommendation engine.

Public API:
    generate_recommendations(db, device_id) -> list[Recommendation]
        Create or update Recommendation rows for every Risk on a device.

    generate_all_recommendations(db) -> int
        Run generate_recommendations for every device in the DB.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.recommendation import Recommendation

logger = logging.getLogger(__name__)


# ── Advice catalogue ──────────────────────────────────────────────────────────
# One entry per check_id produced by app.analysis.checks.  Each entry provides
# the human-readable remediation advice attached to the generated Recommendation.


@dataclass(frozen=True)
class _Advice:
    title: str
    description: str
    steps: list[str]
    effort: str  # "low" | "medium" | "high"
    impact: str  # "low" | "medium" | "high"
    attack_scenario: str = ""  # plain-language exploitation narrative
    likelihood: str = ""  # realistic likelihood on a home network


_CATALOGUE: dict[str, _Advice] = {
    "telnet_open": _Advice(
        title="Disable Telnet and switch to SSH",
        description=(
            "Telnet transmits all data including credentials in plain text. "
            "An attacker with network access can intercept sessions trivially."
        ),
        steps=[
            "Log in to the device management interface.",
            "Locate the remote-access or services configuration section.",
            "Disable the Telnet (port 23) service entirely.",
            "Enable SSH if remote access is still required.",
            "Verify port 23 is no longer reachable from the network.",
        ],
        effort="low",
        impact="critical",
        attack_scenario=(
            "An attacker on your Wi-Fi passively records all Telnet traffic with "
            "a tool like Wireshark or tcpdump. In seconds they see your username and "
            "password in plain text — no hacking required."
        ),
        likelihood=(
            "High — automated scanners probe port 23 continuously. On a home network, "
            "any device with Wi-Fi access can capture Telnet sessions."
        ),
    ),
    "ftp_open": _Advice(
        title="Replace FTP with SFTP or FTPS",
        description=(
            "FTP sends usernames, passwords, and file contents in cleartext. "
            "Replace it with SFTP (SSH File Transfer Protocol) or FTPS (FTP over TLS)."
        ),
        steps=[
            "Identify what service is using port 21.",
            "Configure SFTP or FTPS as the replacement transfer method.",
            "Update all clients that connect to this device to use the new protocol.",
            "Disable the FTP service and close port 21.",
            "Test connectivity with the new secure protocol.",
        ],
        effort="medium",
        impact="high",
        attack_scenario=(
            "Anyone connected to your network can run a packet capture and read every "
            "file transferred and every password typed into FTP. They can also attempt "
            "brute-force logins with common credential lists."
        ),
        likelihood=(
            "Medium — FTP is less common on home networks but frequently left enabled "
            "on NAS devices and routers."
        ),
    ),
    "unencrypted_http": _Advice(
        title="Enable HTTPS on the management interface",
        description=(
            "The device exposes an unencrypted HTTP management interface. "
            "Credentials and configuration data transmitted over HTTP can be intercepted."
        ),
        steps=[
            "Access the device admin panel.",
            "Navigate to the HTTPS / SSL/TLS settings.",
            "Generate or upload a TLS certificate (self-signed is acceptable for LAN management).",
            "Enable HTTPS and set it as the default protocol.",
            "Disable HTTP or configure an automatic redirect from HTTP to HTTPS.",
        ],
        effort="low",
        impact="medium",
        attack_scenario=(
            "A device on your network performs a man-in-the-middle attack, intercepting "
            "your browser's connection to the admin panel. They can read or modify the page, "
            "steal your session cookie, or capture your login credentials."
        ),
        likelihood=(
            "Medium — requires the attacker to already be on your LAN, but ARP spoofing "
            "makes this trivial on a flat Wi-Fi network."
        ),
    ),
    "upnp_exposed": _Advice(
        title="Disable UPnP on non-router devices",
        description=(
            "Universal Plug and Play (UPnP) on a non-router device can be abused to "
            "automatically open ports or redirect traffic without authorisation."
        ),
        steps=[
            "Log in to the device management interface.",
            "Find the network or UPnP settings section.",
            "Disable the UPnP service.",
            "Verify that port 1900/UDP is no longer responding to SSDP discovery.",
        ],
        effort="low",
        impact="medium",
        attack_scenario=(
            "A malicious website or script instructs your router via UPnP to open ports "
            "to the internet — without any confirmation from you. This has been used to "
            "expose SSH, RDP, and camera streams publicly."
        ),
        likelihood=(
            "Medium — UPnP attacks have been exploited in the wild. Any device on your "
            "network (including a compromised IoT device) can silently add port forwarding rules."
        ),
    ),
    "ssh_password_auth": _Advice(
        title="Disable SSH password authentication and use key-based auth",
        description=(
            "SSH servers that accept password authentication are vulnerable to brute-force "
            "and credential-stuffing attacks. Key-based authentication is significantly "
            "more secure."
        ),
        steps=[
            "Generate an SSH key pair on the client machine if you do not already have one.",
            "Copy the public key to the device's authorised_keys file.",
            "Edit /etc/ssh/sshd_config (or equivalent) and set: PasswordAuthentication no",
            "Reload the SSH service: sudo systemctl reload sshd",
            "Verify that password login is now rejected.",
        ],
        effort="medium",
        impact="medium",
        attack_scenario=(
            "Automated bots continuously probe port 22 on the internet and LAN, trying "
            "millions of username/password combinations. A weak or reused password can "
            "be cracked in minutes."
        ),
        likelihood=(
            "High — SSH brute-force is one of the most common attack types. "
            "Tools like Hydra and Medusa make this trivial."
        ),
    ),
    "smb_open": _Advice(
        title="Close or restrict SMB/NetBIOS ports",
        description=(
            "SMB (ports 445, 137-139) exposed on a non-NAS device broadens the attack surface "
            "and is a common ransomware entry point. Restrict or disable unless actively needed."
        ),
        steps=[
            "Determine whether SMB file sharing is actively used on this device.",
            "If not needed, disable SMB/Windows File Sharing in the OS or device settings.",
            "If needed, restrict access via firewall rules to specific trusted IP addresses only.",
            "Ensure the device's OS and SMB service are fully patched.",
            "Audit shared folders and remove any open or guest shares.",
        ],
        effort="medium",
        impact="high",
        attack_scenario=(
            "The EternalBlue exploit (used by WannaCry ransomware) targeted SMB directly. "
            "Even on a LAN, an attacker can use SMB vulnerabilities to move laterally between "
            "devices or access shared files without credentials."
        ),
        likelihood=(
            "Medium — SMB exploits are well-known. Unpatched SMB is high-risk; patched SMB "
            "on a home LAN is lower but not negligible."
        ),
    ),
    "printer_iot_admin": _Advice(
        title="Restrict printer/IoT admin UI access",
        description=(
            "Printer and IoT device admin interfaces on common ports are frequently targeted "
            "by automated scanners. Restrict access and change default credentials."
        ),
        steps=[
            "Change the default administrator password on the device.",
            "Configure a firewall rule to allow admin UI access only from trusted "
            "management hosts.",
            "Disable remote admin access from the WAN/internet side if applicable.",
            "Check for and apply any available firmware updates.",
            "Disable unused services and protocols in the device's admin panel.",
        ],
        effort="low",
        impact="medium",
        attack_scenario=(
            "Default credentials like admin/admin or admin/1234 are published online for "
            "every printer model. An attacker logs into the admin panel, changes settings, "
            "captures print jobs, or uses the device as a pivot point into the rest of "
            "the network."
        ),
        likelihood=(
            "High — default credentials on printers and IoT devices are extremely common "
            "and rarely changed by home users."
        ),
    ),
    "outdated_banner": _Advice(
        title="Update outdated service software",
        description=(
            "One or more services are advertising version banners that suggest outdated software "
            "with known CVEs. Update to current stable releases to patch known vulnerabilities."
        ),
        steps=[
            "Identify the exact software and version from the service banner.",
            "Check the vendor's security advisories for relevant CVEs.",
            "Apply available OS or package updates: e.g. sudo apt upgrade <package>",
            "If the OS is end-of-life, plan a migration to a supported version.",
            "After updating, re-scan to confirm the old version banner is no longer present.",
        ],
        effort="medium",
        impact="low",
        attack_scenario=(
            "An attacker reads the version banner, looks up known CVEs for that exact "
            "version on a public database, and runs a publicly available exploit. "
            "Old software often has unpatched remote code execution vulnerabilities."
        ),
        likelihood=(
            "Medium — automated vulnerability scanners do this constantly. Exploitation "
            "depends on whether a known CVE exists for the detected version."
        ),
    ),
    "rdp_exposed": _Advice(
        title="Restrict RDP access",
        description=(
            "RDP (Remote Desktop Protocol) on port 3389 is a frequent target for "
            "brute-force and ransomware attacks. Restrict access to trusted hosts only."
        ),
        steps=[
            "Determine whether RDP is actively needed on this device.",
            "If not needed, disable Remote Desktop in System → Remote Settings.",
            "If needed, restrict RDP access via a firewall rule to specific trusted IPs only.",
            "Enable Network Level Authentication (NLA) if RDP must stay enabled.",
            "Consider using a VPN instead of exposing RDP directly on the LAN.",
        ],
        effort="low",
        impact="high",
        attack_scenario=(
            "Attackers use tools like BlueKeep exploits or credential stuffing to take "
            "over RDP sessions. Once inside, they have full desktop access to the machine. "
            "On a LAN, RDP is also a primary lateral movement target after initial compromise."
        ),
        likelihood=(
            "High — RDP is one of the most attacked protocols. Even on a LAN, "
            "a compromised device can be used to pivot to others via RDP."
        ),
    ),
    "vnc_exposed": _Advice(
        title="Secure or disable VNC",
        description=(
            "VNC (Virtual Network Computing) on port 5900 often uses weak passwords and "
            "transmits data unencrypted. Tunnel through SSH or a VPN, or disable it."
        ),
        steps=[
            "Determine whether VNC is actively in use on this device.",
            "If not needed, stop and disable the VNC server service.",
            "If needed, configure VNC to only listen on localhost and tunnel via SSH "
            "(ssh -L 5900:localhost:5900 user@host).",
            "Set a strong VNC password (8+ characters, mixed case and symbols).",
            "Apply any available VNC server security updates.",
        ],
        effort="low",
        impact="high",
        attack_scenario=(
            "Many VNC servers use weak or no passwords by default. An attacker gains "
            "full graphical access to the desktop. VNC traffic is also unencrypted, "
            "so passwords can be sniffed off the network."
        ),
        likelihood=(
            "Medium — VNC is less common than RDP but frequently misconfigured with "
            "weak or no credentials on home lab devices."
        ),
    ),
    "mqtt_open": _Advice(
        title="Secure MQTT broker with TLS and authentication",
        description=(
            "The unencrypted MQTT port (1883) allows anyone on the LAN to publish or "
            "subscribe to any topic. Switch to MQTT over TLS (port 8883) and enable "
            "broker-level authentication."
        ),
        steps=[
            "Install a TLS certificate on the MQTT broker (e.g., Mosquitto).",
            "Configure the broker to use port 8883 and require TLS.",
            "Enable username/password or client-certificate authentication in broker config.",
            "Update all MQTT clients to connect on 8883 with credentials.",
            "Disable the plaintext port 1883 listener in the broker configuration.",
        ],
        effort="medium",
        impact="medium",
        attack_scenario=(
            "An attacker connects to the MQTT broker without authentication and subscribes "
            "to all topics (#). They can read sensor data, home automation commands, and "
            "in some cases publish malicious commands to smart home devices."
        ),
        likelihood=(
            "Medium — unauthenticated MQTT brokers are common in home automation setups. "
            "Risk escalates when smart locks, alarms, or switches are connected."
        ),
    ),
    "open_dns_resolver": _Advice(
        title="Restrict DNS to authorised clients",
        description=(
            "A DNS service accessible from the whole LAN may be abused as an open resolver "
            "in amplification attacks or used to intercept DNS queries."
        ),
        steps=[
            "If this device is not intended to be a DNS server, disable the DNS service.",
            "If it is a DNS server, configure it to only answer queries from "
            "trusted IP ranges (e.g., your LAN subnet).",
            "For Pi-hole or AdGuard Home, verify the listen interface is set to LAN only.",
            "Block DNS (port 53) on the WAN-facing interface of your router.",
            "Enable DNSSEC validation if supported by your resolver.",
        ],
        effort="low",
        impact="medium",
        attack_scenario=(
            "An attacker uses your device to amplify a DNS DDoS attack against a third party, "
            "sending small queries that generate large responses directed at the victim. "
            "Your IP appears as the source, implicating you."
        ),
        likelihood=(
            "Low on home networks — unless you're running a DNS server intentionally. "
            "The risk is primarily misuse for amplification attacks."
        ),
    ),
    "modbus_open": _Advice(
        title="Disable Modbus or isolate the device",
        description=(
            "Modbus is an industrial control protocol with no built-in authentication "
            "or encryption. Its presence on a home LAN is a significant security risk."
        ),
        steps=[
            "Identify the device running Modbus on port 502.",
            "Determine whether the service is intentional or a misconfiguration.",
            "If not needed, disable the Modbus service on the device.",
            "If the device is an IoT or industrial device that requires Modbus, isolate it "
            "on a separate VLAN with strict firewall rules.",
            "Block port 502 on your router/firewall for all but the specific device.",
        ],
        effort="medium",
        impact="high",
        attack_scenario=(
            "Modbus has no authentication. An attacker sends raw Modbus commands to read "
            "sensor values, modify control registers, or issue commands to connected hardware. "
            "On a home LAN, this likely indicates a misconfigured device."
        ),
        likelihood=(
            "Low — Modbus on a home LAN is unusual and almost always a misconfiguration. "
            "Risk is high if the device controls physical systems."
        ),
    ),
    "snmp_exposed": _Advice(
        title="Secure or disable SNMP",
        description=(
            "SNMP with the default 'public' community string leaks full device information "
            "to anyone on the network. Upgrade to SNMPv3 or disable SNMP entirely."
        ),
        steps=[
            "Log in to the device management interface.",
            "Locate the SNMP configuration section.",
            "If SNMP is not required, disable it completely.",
            "If SNMP is needed, change the community string from 'public' "
            "to a strong random value.",
            "Upgrade to SNMPv3 with AuthPriv mode (authentication + encryption) where supported.",
            "Restrict SNMP access to specific management hosts using an ACL.",
        ],
        effort="low",
        impact="high",
        attack_scenario=(
            "An attacker sends SNMP queries with the default 'public' community string and "
            "receives full device information — interfaces, routing tables, connected devices, "
            "and system details. This information is used to plan deeper attacks."
        ),
        likelihood=(
            "Medium — default SNMP community strings are present on most network devices "
            "out of the box. Automated LAN scanners query port 161 routinely."
        ),
    ),
    "redis_exposed": _Advice(
        title="Bind Redis to localhost and require authentication",
        description=(
            "An unauthenticated Redis instance accessible from the network is a critical "
            "vulnerability enabling data theft and remote code execution via CONFIG commands."
        ),
        steps=[
            "Edit redis.conf and set 'bind 127.0.0.1' to restrict listening to localhost only.",
            "Set a strong password: 'requirepass <strong-password>'.",
            "If Redis must be network-accessible, use TLS (Redis 6+) and require authentication.",
            "Apply a firewall rule to block port 6379 from all but authorised hosts.",
            "Restart Redis and verify the configuration with 'redis-cli ping' from a remote host.",
        ],
        effort="low",
        impact="critical",
        attack_scenario=(
            "An attacker connects to Redis and runs: CONFIG SET dir /root/.ssh && "
            "CONFIG SET dbfilename authorized_keys, then writes their public key — "
            "gaining passwordless SSH root access to the server in under 30 seconds."
        ),
        likelihood=(
            "High on misconfigured servers — exposed Redis instances are compromised within "
            "hours of being discovered. Any LAN user can execute this without special tools."
        ),
    ),
    "docker_daemon_tcp": _Advice(
        title="Disable the unauthenticated Docker TCP socket",
        description=(
            "The Docker TCP daemon without TLS allows anyone to run containers, mount the "
            "host filesystem, and gain root access. This must be remediated immediately."
        ),
        steps=[
            "Edit /etc/docker/daemon.json and remove or comment out the 'hosts' entry for tcp://.",
            "If remote Docker access is required, configure TLS with client "
            "certificates instead "
            "(dockerd --tlsverify --tlscacert=ca.pem "
            "--tlscert=server-cert.pem --tlskey=server-key.pem).",
            "Restart Docker: 'sudo systemctl restart docker'.",
            "Apply a firewall rule to block port 2375 immediately as a temporary measure.",
            "Verify the TCP socket is no longer listening with 'ss -tlnp | grep 2375'.",
        ],
        effort="low",
        impact="critical",
        attack_scenario=(
            "An attacker runs: docker -H tcp://your-ip:2375 run -v /:/host alpine chroot /host. "
            "In one command they have root access to your entire filesystem. "
            "No password, no authentication — just a TCP connection."
        ),
        likelihood=(
            "High if exposed — this is a critical misconfiguration. Any device on your LAN "
            "can execute this in seconds using standard Docker tools."
        ),
    ),
    "docker_daemon_tls": _Advice(
        title="Restrict Docker TLS daemon access",
        description=(
            "The Docker TLS daemon port exposes the full Docker API remotely. "
            "Verify that mutual TLS client authentication is enforced and access is restricted."
        ),
        steps=[
            "Confirm TLS is configured with --tlsverify and a CA, server cert, and server key.",
            "Ensure --tlsverify is set so only clients with a valid certificate can connect.",
            "Apply a firewall rule to allow port 2376 only from trusted management hosts.",
            "Rotate certificates periodically and revoke access for unused clients.",
        ],
        effort="medium",
        impact="high",
        attack_scenario=(
            "If TLS client verification is misconfigured (e.g., --tls instead of --tlsverify), "
            "anyone can still connect. Even with proper TLS, the Docker API gives full host "
            "root access to anyone who can authenticate."
        ),
        likelihood=(
            "Low if properly configured with --tlsverify enforced. "
            "Medium if --tlsverify is not set or certificates are shared insecurely."
        ),
    ),
    "elasticsearch_open": _Advice(
        title="Enable Elasticsearch authentication and restrict network access",
        description=(
            "Elasticsearch without authentication has led to numerous data breaches. "
            "Enable X-Pack security and restrict network access."
        ),
        steps=[
            "Enable X-Pack security in elasticsearch.yml: 'xpack.security.enabled: true'.",
            "Set passwords for built-in users: 'bin/elasticsearch-setup-passwords interactive'.",
            "Configure TLS for inter-node and client communication.",
            "Apply a firewall rule to allow port 9200 only from authorised application hosts.",
            "Review cluster settings to confirm no anonymous access is permitted.",
        ],
        effort="medium",
        impact="high",
        attack_scenario=(
            "An attacker queries http://your-ip:9200/_cat/indices to list all data stores, "
            "then dumps the entire database. On a home network, this might expose personal "
            "files or application data with a single HTTP request."
        ),
        likelihood=(
            "Medium — Elasticsearch without authentication is a well-known misconfiguration. "
            "Automated scanners specifically target port 9200."
        ),
    ),
    "portainer_exposed": _Advice(
        title="Secure Portainer and restrict network access",
        description=(
            "Portainer controls your entire Docker environment. A compromised Portainer "
            "instance gives full access to all running containers and the host."
        ),
        steps=[
            "Set a strong admin password if not already done (Portainer will prompt on first run).",
            "Enable HTTPS-only access — disable port 9000 (HTTP) and use 9443 (HTTPS) only.",
            "Apply a firewall rule to allow Portainer ports only from trusted management hosts.",
            "Consider placing Portainer behind a VPN or SSH tunnel.",
            "Enable two-factor authentication in Portainer settings if available.",
        ],
        effort="low",
        impact="medium",
        attack_scenario=(
            "An attacker accesses the Portainer web UI, browses your containers, and uses "
            "the built-in terminal to exec into any running container. From there they can "
            "access the host filesystem and all other containers."
        ),
        likelihood=(
            "Low on typical home networks — medium for home lab users. Risk is high "
            "if the Portainer admin password has not been set after installation."
        ),
    ),
    "home_assistant_exposed": _Advice(
        title="Secure Home Assistant and enable 2FA",
        description=(
            "Home Assistant controls smart home devices. Ensure it is properly secured "
            "against unauthorised access from the local network."
        ),
        steps=[
            "Enable two-factor authentication (TOTP) in your Home Assistant profile settings.",
            "Set a strong password for all user accounts.",
            "Apply a firewall rule or network policy to restrict port 8123 to trusted devices.",
            "If remote access is needed, use the Nabu Casa cloud service or a VPN rather than "
            "direct port forwarding.",
            "Keep Home Assistant updated to receive security patches.",
        ],
        effort="low",
        impact="medium",
        attack_scenario=(
            "An attacker authenticates to Home Assistant (guessing a weak password or "
            "exploiting a vulnerability), then uses it to unlock smart locks, disable alarms, "
            "or enumerate all connected smart home devices."
        ),
        likelihood=(
            "Low — requires the attacker to be on your LAN or the service to be "
            "internet-exposed. Risk increases significantly if Home Assistant is port-forwarded."
        ),
    ),
    "tftp_open": _Advice(
        title="Disable TFTP if not actively required",
        description=(
            "TFTP has no authentication and transfers files in plaintext. "
            "Disable it unless it is actively used for network booting or firmware updates."
        ),
        steps=[
            "Identify the service using TFTP (port 69/udp) — "
            "common culprits: tftpd, dnsmasq, routers.",
            "If TFTP is not required, disable or stop the service.",
            "If TFTP is needed (e.g., PXE booting), restrict access to specific client IPs.",
            "Apply a firewall rule to block port 69/udp from untrusted network segments.",
        ],
        effort="low",
        impact="medium",
        attack_scenario=(
            "An attacker requests well-known config files (e.g., startup-config, passwd) "
            "from the TFTP server without any credentials. TFTP is also used to replace "
            "firmware on network devices."
        ),
        likelihood=(
            "Low — TFTP on home networks is usually enabled for PXE booting and "
            "rarely hardened against unauthorised access."
        ),
    ),
    "wireguard_vpn": _Advice(
        title="Review WireGuard peer configuration",
        description=(
            "WireGuard is a secure VPN protocol. This entry is informational — "
            "verify the peer list and keep WireGuard updated."
        ),
        steps=[
            "Review the WireGuard configuration (/etc/wireguard/*.conf) for authorised peers only.",
            "Remove any stale or unused peer entries.",
            "Ensure the WireGuard package is kept up to date.",
            "Consider using a non-default port if the VPN endpoint "
            "should not be easily discoverable.",
        ],
        effort="low",
        impact="low",
        attack_scenario=(
            "WireGuard itself is cryptographically secure. The risk is stale peer entries — "
            "if a former network user's public key is still listed, they can still connect "
            "to the VPN."
        ),
        likelihood=(
            "Very low — WireGuard is designed to be secure. "
            "This finding is informational and the main risk is key hygiene."
        ),
    ),
    "multiple_admin_panels": _Advice(
        title="Reduce the management attack surface",
        description=(
            "Having many admin and remote-access ports open simultaneously increases the "
            "number of ways an attacker can attempt to compromise the device."
        ),
        steps=[
            "Audit each open management port and identify which services are actually in use.",
            "Disable or stop any admin interfaces, remote desktop, or web UIs not actively needed.",
            "Where possible, consolidate management to a single encrypted channel (SSH or HTTPS).",
            "Apply firewall rules to restrict remaining management ports to trusted hosts only.",
        ],
        effort="low",
        impact="medium",
        attack_scenario=(
            "Each additional management port is another login form to brute-force or "
            "vulnerability to exploit. An attacker methodically tests each one for default "
            "credentials or known CVEs, increasing their chances of finding a weak entry point."
        ),
        likelihood=(
            "Medium — the more services exposed, the more likely one has a misconfiguration "
            "or weak password. Compound exposure multiplies the overall risk."
        ),
    ),
    "database_and_web_exposed": _Advice(
        title="Isolate the database from the network and enforce HTTPS",
        description=(
            "A database port open alongside an unencrypted web interface creates a "
            "two-step path from public HTTP exploit to full database access."
        ),
        steps=[
            "Bind the database to 127.0.0.1 or a private interface only — "
            "it should never be network-accessible from outside the host.",
            "If the database must be remotely managed, use an SSH tunnel.",
            "Redirect all HTTP (port 80) traffic to HTTPS and obtain a TLS certificate.",
            "Apply a firewall rule blocking the database port from all external sources.",
        ],
        effort="medium",
        impact="high",
        attack_scenario=(
            "An attacker finds an SQL injection or file upload vulnerability in the web "
            "application, then uses it to connect directly to the open database port and "
            "exfiltrate all data — bypassing authentication entirely."
        ),
        likelihood=(
            "Medium — web application vulnerabilities are extremely common. The combination "
            "of an open web UI and an open database port is a classic two-step exploitation path."
        ),
    ),
    "cleartext_credential_surface": _Advice(
        title="Replace all cleartext protocols immediately",
        description=(
            "Running Telnet, FTP, and HTTP together means any credential entered on "
            "this device can be captured by a passive network observer."
        ),
        steps=[
            "Disable Telnet and replace with SSH for remote shell access.",
            "Disable FTP and replace with SFTP or SCP.",
            "Disable plain HTTP and serve all web content over HTTPS only.",
            "After disabling, verify the ports are no longer listening with 'ss -tlnp'.",
        ],
        effort="low",
        impact="high",
        attack_scenario=(
            "A single tcpdump or Wireshark session on your Wi-Fi captures passwords from "
            "Telnet, FTP usernames and files, and HTTP form data simultaneously. An attacker "
            "captures valid credentials within minutes of observing network traffic."
        ),
        likelihood=(
            "High — if all three cleartext services are in active use, credential capture "
            "is trivially easy for anyone on your network."
        ),
    ),
    "remote_access_no_encryption": _Advice(
        title="Tunnel remote desktop through an encrypted channel",
        description=(
            "RDP and VNC without an encrypted wrapper expose session content and "
            "credentials to anyone on the same network."
        ),
        steps=[
            "Do not expose RDP (3389) or VNC (5900) directly on the LAN if avoidable.",
            "Set up a VPN (WireGuard, OpenVPN) and access the device only through it.",
            "Alternatively, tunnel RDP/VNC over an SSH port forward.",
            "If direct access is required, enable NLA (Network Level Authentication) "
            "for RDP and set a strong VNC password with TLS where supported.",
            "Apply a firewall rule to restrict RDP/VNC to specific trusted host IPs.",
        ],
        effort="medium",
        impact="high",
        attack_scenario=(
            "An attacker on your network runs a packet capture, extracts the VNC or RDP "
            "session data, and reconstructs the screen contents. For RDP without NLA, "
            "credentials are sent before the TLS handshake completes."
        ),
        likelihood=(
            "Medium — requires LAN access, but ARP spoofing can silently position an "
            "attacker between you and the target device."
        ),
    ),
    "ssh_and_telnet_both_open": _Advice(
        title="Disable Telnet — SSH is already available",
        description=(
            "SSH is already running, making Telnet entirely redundant and dangerous. "
            "Disable it immediately."
        ),
        steps=[
            "Identify and stop the Telnet service: "
            "'sudo systemctl stop telnet' or 'sudo systemctl disable inetd'.",
            "Verify Telnet is no longer listening: 'ss -tlnp | grep 23'.",
            "Ensure SSH is configured with key-based authentication and "
            "PasswordAuthentication disabled in /etc/ssh/sshd_config.",
        ],
        effort="low",
        impact="medium",
        attack_scenario=(
            "An attacker targets the Telnet port (much easier to exploit than SSH) to "
            "capture credentials in cleartext. Even if SSH is hardened, Telnet provides "
            "an easy alternative entry point that bypasses all SSH security controls."
        ),
        likelihood=(
            "Medium — Telnet is trivially exploitable once an attacker is on the LAN. "
            "Its co-existence with SSH suggests it was never intentionally kept."
        ),
    ),
    "iot_admin_panel_http": _Advice(
        title="Enable HTTPS on the IoT device admin panel",
        description=(
            "This IoT device exposes its admin interface over plain HTTP. "
            "Credentials and settings can be intercepted by anyone on the same network."
        ),
        steps=[
            "Access the IoT device's admin panel in your browser.",
            "Check the Settings or Network section for HTTPS or TLS options.",
            "If HTTPS is available, enable it and disable plain HTTP.",
            "If HTTPS is not available, check for a firmware update that adds TLS support.",
            "As a mitigation, apply a firewall rule limiting access to the admin port "
            "to trusted management hosts only.",
        ],
        effort="low",
        impact="medium",
        attack_scenario=(
            "An attacker on your Wi-Fi intercepts the HTTP session to your IoT device "
            "and captures your login credentials or session cookie. They then change "
            "device settings, disable firmware updates, or use the device as a pivot "
            "point into the rest of the network."
        ),
        likelihood=(
            "Medium — many consumer IoT devices ship with HTTP-only management interfaces. "
            "The risk is amplified on networks where IoT devices share Wi-Fi with workstations."
        ),
    ),
    "iot_remote_shell": _Advice(
        title="Disable the remote shell on this IoT device",
        description=(
            "Consumer IoT devices should not expose SSH or Telnet. "
            "Its presence may indicate a debug port, backdoor, or compromised firmware."
        ),
        steps=[
            "Identify the shell service (SSH port 22 or Telnet port 23).",
            "Access the device's admin UI and disable remote shell access if the option exists.",
            "Check the manufacturer's support pages for a firmware update or security advisory.",
            "If the service cannot be disabled, apply a firewall rule to block the port.",
            "Consider whether the device should be replaced if no fix is available.",
        ],
        effort="medium",
        impact="high",
        attack_scenario=(
            "Many consumer IoT devices ship with hard-coded credentials for debug SSH or "
            "Telnet access. An attacker connects using published default credentials, gains "
            "root access to the device, and uses it as a persistent foothold in your network."
        ),
        likelihood=(
            "Medium — especially for older or budget IoT devices. Hard-coded credentials "
            "for SSH/Telnet on IoT firmware are a known vulnerability class with "
            "published exploit databases."
        ),
    ),
}


# ── Public functions ──────────────────────────────────────────────────────────


def generate_recommendations(db: Session, device_id: int) -> list[Recommendation]:
    """Create or update Recommendation rows for every current Risk on *device_id*.

    Existing recommendations for the device are fully replaced so that resolved
    risks no longer have stale recommendations.  Caller must commit the session.
    """
    from app.models.recommendation import Recommendation
    from app.models.risk import Risk

    # Remove stale recommendations for this device
    existing = (
        db.execute(select(Recommendation).where(Recommendation.device_id == device_id))
        .scalars()
        .all()
    )
    for rec in existing:
        db.delete(rec)
    db.flush()

    # Fetch current risks for this device
    risks = db.execute(select(Risk).where(Risk.device_id == device_id)).scalars().all()

    written: list[Recommendation] = []
    now = datetime.now(tz=UTC)

    for risk in risks:
        advice = _CATALOGUE.get(risk.check_id)
        if advice is None:
            logger.warning(
                "No advice catalogue entry for check_id=%r (device %d, risk %d)",
                risk.check_id,
                device_id,
                risk.id,
            )
            continue

        rec = Recommendation(
            device_id=device_id,
            risk_id=risk.id,
            check_id=risk.check_id,
            severity=risk.severity,
            title=advice.title,
            description=advice.description,
            steps=json.dumps(advice.steps),
            effort=advice.effort,
            impact=advice.impact,
            attack_scenario=advice.attack_scenario,
            likelihood=advice.likelihood,
            created_at=now,
            updated_at=now,
        )
        db.add(rec)
        written.append(rec)

    logger.debug("Device %d: %d recommendation(s) written", device_id, len(written))
    return written


def generate_all_recommendations(db: Session) -> int:
    """Generate recommendations for every device.  Returns total count written."""
    from app.models.device import Device

    device_ids = db.execute(select(Device.id)).scalars().all()
    total = 0
    for device_id in device_ids:
        recs = generate_recommendations(db, device_id)
        total += len(recs)
    db.commit()
    logger.info(
        "generate_all_recommendations: %d recommendation(s) across %d device(s)",
        total,
        len(device_ids),
    )
    return total
