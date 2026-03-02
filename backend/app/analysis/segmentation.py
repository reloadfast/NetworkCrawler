"""Segmentation advisor — flat network detection and VLAN recommendations.

Analyses the device list to detect flat networks where IoT devices and
servers/NAS share the same subnet, and returns advisory recommendations.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

_RECOMMENDATIONS: list[str] = [
    (
        "Create a dedicated IoT VLAN and move smart devices onto it"
        " — block inter-VLAN routing to your main LAN."
    ),
    "Use a guest Wi-Fi network for IoT devices so they cannot reach servers, NAS, or workstations.",
    (
        "Apply firewall rules (or ACLs) that prevent IoT devices from initiating"
        " connections to your server subnet."
    ),
]


@dataclass
class MixedRiskPair:
    iot_device_id: int
    iot_ip: str
    server_device_id: int
    server_ip: str
    shared_subnet: str


@dataclass
class SegmentationResult:
    flat_network: bool
    iot_count: int
    server_count: int
    mixed_risk_pairs: list[MixedRiskPair] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


def _same_24(ip_a: str, ip_b: str) -> str | None:
    """Return the /24 network string if both IPs share it, else None."""
    try:
        net_a = ipaddress.ip_network(f"{ip_a}/24", strict=False)
        net_b = ipaddress.ip_network(f"{ip_b}/24", strict=False)
        if net_a == net_b:
            return str(net_a)
    except ValueError:
        pass
    return None


def analyse_segmentation(db: Session) -> SegmentationResult:
    """Detect flat-network conditions from the persisted device list."""
    from sqlalchemy import select

    from app.models.device import Device

    devices = db.execute(select(Device)).scalars().all()

    iot_devices = [d for d in devices if d.device_type == "iot"]
    server_devices = [d for d in devices if d.device_type in ("server", "nas")]

    flat_network = bool(iot_devices and server_devices)

    pairs: list[MixedRiskPair] = []
    for iot in iot_devices:
        for srv in server_devices:
            subnet = _same_24(iot.ip_address, srv.ip_address)
            if subnet and iot.ports:  # IoT device has open ports — higher risk
                pairs.append(
                    MixedRiskPair(
                        iot_device_id=iot.id,
                        iot_ip=iot.ip_address,
                        server_device_id=srv.id,
                        server_ip=srv.ip_address,
                        shared_subnet=subnet,
                    )
                )

    return SegmentationResult(
        flat_network=flat_network,
        iot_count=len(iot_devices),
        server_count=len(server_devices),
        mixed_risk_pairs=pairs,
        recommendations=_RECOMMENDATIONS if flat_network else [],
    )
