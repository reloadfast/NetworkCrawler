"""ntopng data analyzer — transforms raw API data into structured findings.

Parsers handle:
- Bandwidth anomalies (top talkers with disproportionate usage)
- Unusual protocol detection
- Suspicious host patterns
- Alert correlation
- Flow-based anomaly detection
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────────────


@dataclass
class BandwidthFinding:
    """A bandwidth-related finding from ntopng data."""

    severity: str
    summary: str
    device: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProtocolFinding:
    """A protocol-related finding from ntopng data."""

    severity: str
    summary: str
    protocol: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class HostFinding:
    """A host-related finding from ntopng data."""

    severity: str
    summary: str
    host_ip: str
    host_name: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class FlowFinding:
    """A flow-based anomaly finding from ntopng data."""

    severity: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)


# Sentinel class (not a real dataclass)
_ntopng_result_cls: type

_ntopng_result_cls = type(
    "ntopngResult",
    (),
    {
        "bandwidth_findings": list,
        "protocol_findings": list,
        "host_findings": list,
        "flow_findings": list,
        "anomalies": list,
        "total_bytes": int,
        "fetched_at": str,
        # methods
        "to_list": lambda self: [
            {
                "source": "ntopng",
                "category": "bandwidth",
                "severity": f.severity,
                "summary": f.summary,
                "device": f.device,
                "details": f.details,
            }
            for f in self.bandwidth_findings  # noqa: C416 — avoid creating a redundant list
        ],
    },
)


def _empty_result() -> Any:
    """Create an empty analysis result."""
    r = _ntopng_result_cls()
    r.bandwidth_findings = []
    r.protocol_findings = []
    r.host_findings = []
    r.flow_findings = []
    r.anomalies = []
    r.total_bytes = 0
    r.fetched_at = ""
    return r


# ── Constants ─────────────────────────────────────────────────────────────────


COMMON_PROTOCOLS = frozenset(
    {
        "TCP",
        "UDP",
        "HTTP",
        "HTTPS",
        "DNS",
        "ICMP",
        "TLS",
        "SSH",
        "SMB",
        "MQTT",
        "UPnP",
        "SNMP",
        "ARP",
        "DHCP",
        "NTP",
        "RTSP",
        "RDP",
        "FTP",
        "SMTP",
        "POP3",
        "IMAP",
        "TELNET",
        "WIREGUARD",
        "WIREGUAR",
        "L2TP",
        "PPTP",
    }
)

SUSPICIOUS_PROTOCOL_THRESHOLDS: dict[str, int] = {
    "MODBUS": 1_000,  # >1KB Modbus traffic is suspicious
    "OPC": 1_000,  # >1KB OPC traffic is suspicious
    "COPPERWIRE": 1_000,  # >1KB Copperwire traffic is suspicious
    "DNP3": 1_000,  # >1KB DNP3 traffic is suspicious
}

HIGH_BANDWIDTH_BYTES = 100 * 1024 * 1024  # 100 MB

# port → known-malicious or high-risk service
SUSPICIOUS_PORTS: dict[int, str] = {
    631: "CUPS (printer admin — often exploitable)",
    23: "Telnet (cleartext)",
    21: "FTP (cleartext)",
    5555: "Potential reverse shell",
    8888: "Potential proxy/backdoor",
    9999: "Potential reverse shell",
    1337: "Common malware port",
    31337: "Back Orifice (Trojan)",
    6666: "Common IRC / botnet C2",
    6667: "Common IRC / botnet C2",
    7777: "Potential reverse shell",
}


# ═══════════════════════════════════════════════════════════════════════════════


def ntopng_analyze(ntopng_data: dict[str, Any]) -> Any:
    """Analyze raw ntopng data and return structured findings.

    Args:
        ntopng_data: Raw data dict from fetcher.all_data().

    Returns:
        Object with bandwidth_findings, protocol_findings, host_findings,
        flow_findings, anomalies, total_bytes, fetched_at.
    """
    result = _empty_result()
    result.total_bytes = ntopng_data.get("total_bytes", 0)
    result.fetched_at = ntopng_data.get("fetched_at", "")

    result.bandwidth_findings = _analyze_bandwidth(ntopng_data)
    result.protocol_findings = _analyze_protocols(ntopng_data)
    result.host_findings = _analyze_hosts(ntopng_data)
    result.flow_findings = _analyze_flows(ntopng_data)
    result.anomalies = _collect_anomalies(ntopng_data)

    # Normalise to list-of-dicts for the pipeline
    result._findings = _to_findings_list(
        result.bandwidth_findings,
        result.protocol_findings,
        result.host_findings,
        result.flow_findings,
    )
    return result


# ═══════════════════════════════════════════════════════════════════════════════


def _to_findings_list(bw, proto, host, flow) -> list[dict[str, Any]]:
    """Flatten all finding types into a common list-of-dicts."""
    out: list[dict[str, Any]] = []

    for f in bw:
        out.append(
            {
                "source": "ntopng",
                "category": "bandwidth",
                "severity": f.severity,
                "summary": f.summary,
                "device": f.device,
                "details": f.details,
            }
        )
    for f in proto:
        out.append(
            {
                "source": "ntopng",
                "category": "protocol",
                "severity": f.severity,
                "summary": f.summary,
                "protocol": f.protocol,
                "details": f.details,
            }
        )
    for f in host:
        out.append(
            {
                "source": "ntopng",
                "category": "host",
                "severity": f.severity,
                "summary": f.summary,
                "device": f.host_ip,
                "hostname": f.host_name,
                "details": f.details,
            }
        )
    for f in flow:
        out.append(
            {
                "source": "ntopng",
                "category": "flow_anomaly",
                "severity": f.severity,
                "summary": f.summary,
                "details": f.details,
            }
        )
    return out


# ── Analysis phases ─────────────────────────────────────────────────────────


def _analyze_bandwidth(data: dict[str, Any]) -> list[BandwidthFinding]:
    """Detect bandwidth anomalies."""
    findings: list[BandwidthFinding] = []
    top_talkers = data.get("top_talkers", [])
    if not top_talkers:
        return findings

    for talker in top_talkers:
        device = talker.get("device", "unknown")
        b_sent = talker.get("bytes_sent", 0) or 0
        b_recv = talker.get("bytes_recv", 0) or 0
        total = b_sent + b_recv

        if total > HIGH_BANDWIDTH_BYTES:
            findings.append(
                BandwidthFinding(
                    severity="high" if total > 1024 * 1024 * 1024 else "medium",
                    summary=f"High bandwidth: {_fmt_bytes(total)} on {device}",
                    device=device,
                    details={
                        "bytes_sent": b_sent,
                        "bytes_recv": b_recv,
                        "total_bytes": total,
                    },
                )
            )

    # Disproportionate usage: top talker >> others
    if len(top_talkers) >= 2:
        sorted_talkers = sorted(
            top_talkers,
            key=lambda t: (t.get("bytes_sent", 0) or 0) + (t.get("bytes_recv", 0) or 0),
            reverse=True,
        )
        top_bytes = (sorted_talkers[0].get("bytes_sent", 0) or 0) + (
            sorted_talkers[0].get("bytes_recv", 0) or 0
        )
        rest_bytes = sum(
            (t.get("bytes_sent", 0) or 0) + (t.get("bytes_recv", 0) or 0)
            for t in sorted_talkers[1:]
        )
        if rest_bytes > 0 and top_bytes > rest_bytes:
            ratio = top_bytes / rest_bytes
            if ratio > 5:
                findings.append(
                    BandwidthFinding(
                        severity="medium",
                        summary=(
                            f"Top talker ({sorted_talkers[0].get('device', 'unknown')}) "
                            f"exercises {ratio:.1f}x more traffic than all others"
                        ),
                        device=sorted_talkers[0].get("device", "unknown"),
                        details={"ratio": ratio, "top_bytes": top_bytes, "rest_bytes": rest_bytes},
                    )
                )
    return findings


def _analyze_protocols(data: dict[str, Any]) -> list[ProtocolFinding]:
    """Detect unusual or suspicious protocols."""
    findings: list[ProtocolFinding] = []
    protocols = data.get("protocols", {})
    if not isinstance(protocols, dict):
        return findings

    for proto, byte_count in protocols.items():
        pu = proto.upper()

        if pu in SUSPICIOUS_PROTOCOL_THRESHOLDS and byte_count > SUSPICIOUS_PROTOCOL_THRESHOLDS[pu]:
            findings.append(
                ProtocolFinding(
                    severity="high",
                    summary=f"Suspicious {pu} traffic: {_fmt_bytes(byte_count)}",
                    protocol=pu,
                    details={"bytes": byte_count},
                )
            )
        elif pu not in COMMON_PROTOCOLS and byte_count > 0:
            findings.append(
                ProtocolFinding(
                    severity="medium",
                    summary=f"Unusual protocol: {pu} ({_fmt_bytes(byte_count)})",
                    protocol=pu,
                    details={"bytes": byte_count},
                )
            )
    return findings


def _analyze_hosts(data: dict[str, Any]) -> list[HostFinding]:
    """Detect suspicious host patterns."""
    findings: list[HostFinding] = []
    hosts = data.get("host_stats", [])
    if not hosts:
        return findings

    seen: set[str] = set()

    for host in hosts:
        ip = host.get("host", "")
        name = host.get("hostname", "") or ip
        port_list = host.get("open_ports", [])
        total_packets = (host.get("packets_sent", 0) or 0) + (host.get("packets_recv", 0) or 0)
        b_sent = host.get("bytes_sent", 0) or 0

        # Check suspicious ports
        ports = port_list if isinstance(port_list, list) else []
        for p in ports:
            pn = p.get("port", 0) if isinstance(p, dict) else p
            if pn in SUSPICIOUS_PORTS:
                key = f"{ip}:{pn}"
                if key not in seen:
                    seen.add(key)
                    findings.append(
                        HostFinding(
                            severity="critical",
                            summary=f"{ip} has {SUSPICIOUS_PORTS[pn]} (port {pn})",
                            host_ip=ip,
                            host_name=name,
                            details={"port": pn},
                        )
                    )

        # Very high packet count (potential scanner/bot)
        if total_packets > 1_000_000:
            key = f"{ip}:packets"
            if key not in seen:
                seen.add(key)
                findings.append(
                    HostFinding(
                        severity="medium",
                        summary=f"{ip} has high packet count ({total_packets:,})",
                        host_ip=ip,
                        host_name=name,
                        details={"packets": total_packets},
                    )
                )

        # Small average packet size over huge volume (potential covert channel)
        if b_sent > 0 and total_packets > 100_000:
            avg = b_sent / total_packets
            if avg < 64:
                key = f"{ip}:covert"
                if key not in seen:
                    seen.add(key)
                    findings.append(
                        HostFinding(
                            severity="high",
                            summary=f"{ip} has small avg pkt size ({avg:.0f}B) over {total_packets:,} pkts — possible covert channel",
                            host_ip=ip,
                            host_name=name,
                            details={"avg_bytes_per_packet": avg, "total_packets": total_packets},
                        )
                    )
    return findings


def _analyze_flows(data: dict[str, Any]) -> list[FlowFinding]:
    """Detect flow-based anomalies."""
    findings: list[FlowFinding] = []
    flows = data.get("flows", [])
    if not flows:
        return findings

    for flow in flows:
        src = flow.get("src_host", "") or flow.get("source", {}).get("address", "")
        dst = flow.get("dst_host", "") or flow.get("destination", {}).get("address", "")
        if not src or not dst:
            continue

        bts = flow.get("bytes", 0) or flow.get("bytes_sent", 0) or 0
        dur = flow.get("duration", flow.get("duration_sec", 0) or 0) or 0
        proto = flow.get("l4_proto", flow.get("protocol", "unknown"))
        dport = flow.get("dst_port", flow.get("destination_port", -1))

        # Long-lived high-bandwidth flow
        if dur > 3600 and bts > HIGH_BANDWIDTH_BYTES:
            findings.append(
                FlowFinding(
                    severity="medium",
                    summary=(
                        f"Long-lived flow {_fmt_bytes(bts)} {src}→{dst}:{dport} "
                        f"over {dur / 3600:.1f}h"
                    ),
                    details={
                        "src_ip": src,
                        "dst_ip": dst,
                        "dst_port": dport,
                        "protocol": proto,
                        "bytes": bts,
                        "duration_s": dur,
                    },
                )
            )

        # Port to known-bad target
        if isinstance(dport, int) and dport in SUSPICIOUS_PORTS:
            findings.append(
                FlowFinding(
                    severity="high",
                    summary=f"Flow to bad port {dport} ({SUSPICIOUS_PORTS[dport]}): {src}→{dst}",
                    details={
                        "src_ip": src,
                        "dst_ip": dst,
                        "dst_port": dport,
                        "reason": SUSPICIOUS_PORTS[dport],
                        "bytes": bts,
                    },
                )
            )
    return findings


def _collect_anomalies(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect raw anomalies that don't fit standard categories."""
    anomalies: list[dict[str, Any]] = []
    unusual = data.get("unusual_protocols", {})
    if isinstance(unusual, dict) and unusual:
        anomalies.append(
            {
                "type": "unusual_protocols",
                "protocols": list(unusual.keys()),
                "count": len(unusual),
            }
        )
    return anomalies


def _fmt_bytes(n: int) -> str:
    """Format bytes to human-readable string."""
    if n < 1_024:
        return f"{n} B"
    elif n < 1_024**2:
        return f"{n / 1_024:.1f} KB"
    elif n < 1_024**3:
        return f"{n / (1_024**2):.1f} MB"
    return f"{n / (1_024**3):.2f} GB"
