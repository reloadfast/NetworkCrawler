"""Cross-referencing between data sources.

Matches CrowdSec ban IPs against ntopng hosts, NetworkCrawler device list,
and detects correlations that single-source analysis would miss.
"""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CrossReferenceFinding:
    """A finding from cross-referencing multiple data sources."""

    severity: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════


def cross_reference(
    crowdsec_data: dict[str, Any],
    ntopng_data: dict[str, Any],
    networkcrawler_data: Any = None,
) -> list[CrossReferenceFinding]:
    """Cross-reference data sources to find correlated security signals.

    Args:
        crowdsec_data: Raw CrowdSec data from fetcher.
        ntopng_data: Raw ntopng data from fetcher.
        networkcrawler_data: Optional device data from NetworkCrawler.

    Returns:
        List of findings that require investigation across sources.
    """
    findings: list[CrossReferenceFinding] = []

    # 1. Match CrowdSec ban IPs against ntopng active hosts
    ntopng_ips = _extract_ips(ntopng_data)
    ban_findings = _match_bans_against_hosts(crowdsec_data, ntopng_ips)
    findings.extend(ban_findings)

    # 2. Check if banned IPs are still active (same subnet, same CIDR)
    subnet_findings = _check_subnet_presence(crowdsec_data, ntopng_data)
    findings.extend(subnet_findings)

    # 3. Match against NetworkCrawler device list if available
    if networkcrawler_data is not None:
        device_match = _check_device_match(crowdsec_data, networkcrawler_data)
        findings.extend(device_match)

    return findings


# ═══════════════════════════════════════════════════════════════════════════════


def _extract_ips(ntopng_data: dict[str, Any]) -> set[str]:
    """Extract all unique host IPs from ntopng data."""
    ips: set[str] = set()

    for talker in ntopng_data.get("top_talkers", []):
        dev = talker.get("device", "")
        if dev:
            ips.add(dev)

    for host in ntopng_data.get("host_stats", []):
        ip = host.get("host", "")
        if ip:
            ips.add(ip)

    for flow in ntopng_data.get("flows", []):
        src = flow.get("src_host", "") or flow.get("source", {}).get("address", "")
        dst = flow.get("dst_host", "") or flow.get("destination", {}).get("address", "")
        if src:
            ips.add(src)
        if dst:
            ips.add(dst)

    return ips


def _match_bans_against_hosts(
    crowdsec_data: dict[str, Any], ntopng_ips: set[str]
) -> list[CrossReferenceFinding]:
    """Find IPs that are both banned by CrowdSec and active on the network (ntopng)."""
    alerts = crowdsec_data.get("alerts", [])
    findings: list[CrossReferenceFinding] = []

    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        ip = alert.get("ip", "")
        reason = alert.get("reason", alert.get("scenario", "unknown"))
        score = alert.get("score", 0)

        if ip and ip in ntopng_ips:
            # This IP is still on the network despite being banned!
            if score >= 9:
                sev = "high"
            else:
                sev = "medium"

            findings.append(
                CrossReferenceFinding(
                    severity=sev,
                    summary=(
                        f"Active device with active CrowdSec ban: {ip} "
                        f"(ban score: {score}, reason: {reason})"
                    ),
                    details={
                        "ip": ip,
                        "ban_score": score,
                        "reason": reason,
                        "category": "active_ban_on_lan",
                    },
                )
            )

    return findings


def _check_subnet_presence(
    crowdsec_data: dict[str, Any], ntopng_data: dict[str, Any]
) -> list[CrossReferenceFinding]:
    """Check if banned IPs share subnets with active hosts (potential lateral movement)."""
    alerts = crowdsec_data.get("alerts", [])
    findings: list[CrossReferenceFinding] = []
    ntopng_ips = _extract_ips(ntopng_data)

    banned_ips = []
    for alert in alerts:
        if isinstance(alert, dict):
            ip = alert.get("ip", "")
            if ip:
                banned_ips.append(ip)

    if len(banned_ips) < 2 or len(ntopng_ips) < 2:
        return findings

    # Group banned IPs by /24
    banned_subnets: dict[str, list[str]] = {}
    for ip in banned_ips:
        try:
            net = ipaddress.ip_network(f"{ip}/24", strict=False)
            net_str = str(net)
            banned_subnets.setdefault(net_str, []).append(ip)
        except ValueError:
            continue

    # Check if any ntopng host shares a subnet with multiple banned IPs
    for n_ip in ntopng_ips:
        try:
            n_net = ipaddress.ip_network(f"{n_ip}/24", strict=False)
            n_net_str = str(n_net)

            if n_net_str in banned_subnets and len(banned_subnets[n_net_str]) >= 2:
                findings.append(
                    CrossReferenceFinding(
                        severity="high",
                        summary=(
                            f"Network {n_net_str} has {len(banned_subnets[n_net_str])} banned IPs "
                            f"and active host {n_ip} — possible lateral movement vector"
                        ),
                        details={
                            "subnet": n_net_str,
                            "active_host": n_ip,
                            "banned_ips": banned_subnets[n_net_str],
                            "count": len(banned_subnets[n_net_str]),
                            "category": "subnet_lateral_movement",
                        },
                    )
                )
        except ValueError:
            continue

    return findings


def _check_device_match(
    crowdsec_data: dict[str, Any], device_data: Any
) -> list[CrossReferenceFinding]:
    """Match CrowdSec bans against NetworkCrawler device inventory."""
    findings: list[CrossReferenceFinding] = []
    alerts = crowdsec_data.get("alerts", [])
    banned_ips = set()

    for alert in alerts:
        if isinstance(alert, dict):
            ip = alert.get("ip", "")
            if ip and ":" not in ip:  # skip IPv6 for now
                banned_ips.add(ip)

    # device_data is expected to be a list of dicts or a list of Device objects
    device_ips: set[str] = set()
    if isinstance(device_data, list):
        for dev in device_data:
            ip = (
                dev.get("ip_address", "")
                if isinstance(dev, dict)
                else getattr(dev, "ip_address", "")
            )
            if ip:
                device_ips.add(ip)
    elif isinstance(device_data, (set, list)):
        device_ips = device_data

    # Find devices that are also banned
    overlap = banned_ips & device_ips
    if overlap:
        findings.append(
            CrossReferenceFinding(
                severity="high",
                summary=f"{len(overlap)} tracked device(s) also appear in CrowdSec bans: {', '.join(overlap[:5])}",
                details={
                    "banned_ips": list(overlap)[:10],
                    "total_devices_tracked": len(device_ips),
                    "category": "device_in_ban_list",
                },
            )
        )

    return findings
