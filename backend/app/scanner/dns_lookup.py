"""
dns_lookup.py — Reverse DNS lookup fallback for hostname resolution.

resolve_hostnames() is the only public function; it operates on a list of
NmapHost objects in-place and fills in hostname where nmap returned none.

Resolution is attempted in two stages per host:
  1. Standard PTR lookup via socket.gethostbyaddr()
  2. Direct mDNS PTR query to 224.0.0.251:5353 — no avahi-daemon required.
     Works inside Docker containers using network_mode: host.
"""

from __future__ import annotations

import logging
import socket
import struct
from concurrent.futures import ThreadPoolExecutor

from app.scanner.nmap_scan import NmapHost

logger = logging.getLogger(__name__)

_LOOKUP_TIMEOUT_SECONDS = 2
_MAX_WORKERS = 20
_MDNS_ADDR = "224.0.0.251"
_MDNS_PORT = 5353


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


# ── mDNS helpers ──────────────────────────────────────────────────────────────


def _encode_dns_name(name: str) -> bytes:
    """Encode a dotted DNS name into label-length-prefixed wire format."""
    out = b""
    for label in name.rstrip(".").split("."):
        enc = label.encode("ascii")
        out += bytes([len(enc)]) + enc
    return out + b"\x00"


def _read_dns_name(data: bytes, offset: int) -> tuple[str, int]:
    """
    Decode a DNS name at *offset*, following compression pointers.
    Returns (name, new_offset_after_name).
    """
    parts: list[str] = []
    end_offset: int | None = None

    while offset < len(data):
        length = data[offset]
        if length == 0:
            if end_offset is None:
                end_offset = offset + 1
            break
        if length & 0xC0 == 0xC0:  # compression pointer
            if end_offset is None:
                end_offset = offset + 2
            ptr = struct.unpack("!H", data[offset : offset + 2])[0] & 0x3FFF
            offset = ptr
            continue
        offset += 1
        parts.append(data[offset : offset + length].decode("ascii", errors="replace"))
        offset += length

    return ".".join(parts), (end_offset if end_offset is not None else offset + 1)


def _skip_dns_name(data: bytes, offset: int) -> int:
    """Advance *offset* past a DNS name and return the new position."""
    while offset < len(data):
        length = data[offset]
        if length == 0:
            return offset + 1
        if length & 0xC0 == 0xC0:
            return offset + 2
        offset += length + 1
    return offset


def _mdns_ptr_query(ip: str) -> str:
    """
    Send a unicast-requesting mDNS PTR query directly to the multicast group
    (224.0.0.251:5353) and return the first PTR hostname found, or "".

    Does not require avahi-daemon or any system service — only a UDP socket
    on the host network namespace (network_mode: host).
    """
    parts = ip.split(".")
    if len(parts) != 4:
        return ""
    ptr_name = ".".join(reversed(parts)) + ".in-addr.arpa"

    # DNS header: ID=0, FLAGS=0 (query, no recursion), QDCOUNT=1
    header = struct.pack("!HHHHHH", 0, 0x0000, 1, 0, 0, 0)
    # Question: name + QTYPE=PTR(12) + QCLASS=IN with QU bit (0x8001 → unicast response)
    question = _encode_dns_name(ptr_name) + struct.pack("!HH", 12, 0x8001)
    packet = header + question

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
        sock.settimeout(_LOOKUP_TIMEOUT_SECONDS)
        sock.sendto(packet, (_MDNS_ADDR, _MDNS_PORT))

        data, _ = sock.recvfrom(4096)
        return _parse_mdns_ptr(data)
    except (OSError, struct.error):
        return ""
    finally:
        sock.close()


def _parse_mdns_ptr(data: bytes) -> str:
    """Extract the first PTR RDATA name from a raw DNS/mDNS response."""
    if len(data) < 12:
        return ""

    qdcount = struct.unpack("!H", data[4:6])[0]
    ancount = struct.unpack("!H", data[6:8])[0]
    if ancount == 0:
        return ""

    offset = 12
    for _ in range(qdcount):
        offset = _skip_dns_name(data, offset)
        offset += 4  # QTYPE + QCLASS

    for _ in range(ancount):
        offset = _skip_dns_name(data, offset)  # owner name
        if offset + 10 > len(data):
            break
        rtype = struct.unpack("!H", data[offset : offset + 2])[0]
        offset += 8  # TYPE + CLASS + TTL
        rdlength = struct.unpack("!H", data[offset : offset + 2])[0]
        offset += 2
        if rtype == 12:  # PTR
            name, _ = _read_dns_name(data, offset)
            return name.rstrip(".")
        offset += rdlength

    return ""


# ── public API ────────────────────────────────────────────────────────────────


def _resolve(ip: str) -> str:
    """Try PTR first, fall back to direct mDNS for .local names."""
    name = _rdns(ip)
    if not name:
        name = _mdns_ptr_query(ip)
    return name


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
            futures[pool.submit(_resolve, host.ip)] = host

    resolved = 0
    for future, host in futures.items():
        name = future.result()
        if name:
            host.hostname = name
            resolved += 1
            logger.debug("DNS %s → %s", host.ip, name)
        else:
            logger.debug("DNS %s → (no record)", host.ip)

    logger.info("Reverse DNS resolved %d/%d hostname(s)", resolved, len(missing))
