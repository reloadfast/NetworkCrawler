"""Device type classifier — infers device category from vendor/hostname/OS heuristics.

Returns one of: 'iot' | 'server' | 'router' | 'workstation' | 'unknown'
"""

from __future__ import annotations

# Vendor substring → device type (checked in order: router > server > IoT > workstation)
_ROUTER_VENDORS = (
    "mikrotik",
    "ubiquiti",
    "ubnt",
    "avm",
    "netgear",
    "asus",
    "linksys",
    "cisco",
    "juniper",
    "aruba",
    "zyxel",
    "draytek",
    "gl.inet",
    "gl inet",
    "openwrt",
)
_SERVER_VENDORS = (
    "qnap",
    "synology",
    "truenas",
    "dell",
    "hewlett packard",
    "hp ",  # prefix space to avoid matching "php"
    "supermicro",
    "western digital",
    "wd ",
    "seagate",
    "thecus",
    "buffalo",
    "asustor",
)
_IOT_VENDORS = (
    "raspberry pi",
    "espressif",
    "philips",
    "xiaomi",
    "nest",
    "tp-link",
    "tplink",
    "tuya",
    "shelly",
    "sonos",
    "roku",
    "amazon",
    "google",
    "belkin",
    "wemo",
    "ring",
    "arlo",
    "wyze",
    "eufy",
    "anker",
    "lifx",
    "yeelight",
    "meross",
    "sengled",
    "ikea",
    "sonoff",
    "ewelink",
    "tasmota",
    "particle",
    "arduino",
    "nordic semi",
)
_WORKSTATION_VENDORS = (
    "apple",
    "microsoft",
    "intel",
    "lenovo",
    "samsung",
    "lg electron",
    "acer",
    "asus",
)

# Hostname substring → device type
_ROUTER_HOSTNAMES = (
    "router",
    "gateway",
    "mikrotik",
    "ubnt",
    "unifi",
    "openwrt",
    "pfsense",
    "opnsense",
    "fritzbox",
    "fritz",
    "draytek",
)
_SERVER_HOSTNAMES = (
    "nas",
    "plex",
    "jellyfin",
    "truenas",
    "synology",
    "qnap",
    "proxmox",
    "homeassistant",
    "home-assistant",
    "pihole",
    "pi-hole",
    "adguard",
    "dockerhost",
    "unraid",
)
_IOT_HOSTNAMES = (
    "esp",
    "sonoff",
    "shelly",
    "tasmota",
    "homebridge",
    "philips-hue",
    "hue",
    "roku",
    "echo",
    "alexa",
    "google-home",
    "chromecast",
    "nest",
    "arlo",
    "wyze",
    "ring",
    "lifx",
    "yeelight",
    "meross",
    "sonos",
    "tplink",
    "tp-link",
)


def classify_device_type(
    vendor: str | None,
    hostname: str | None,
    os_guess: str | None,
) -> str:
    """Return the device type inferred from vendor, hostname, and OS.

    Priority order: router > server > iot > workstation > unknown
    """
    vendor_l = (vendor or "").lower()
    hostname_l = (hostname or "").lower()
    os_l = (os_guess or "").lower()

    # ── Router ────────────────────────────────────────────────────────────────
    if any(v in vendor_l for v in _ROUTER_VENDORS):
        return "router"
    if any(h in hostname_l for h in _ROUTER_HOSTNAMES):
        return "router"

    # ── Server ────────────────────────────────────────────────────────────────
    if any(v in vendor_l for v in _SERVER_VENDORS):
        return "server"
    if any(h in hostname_l for h in _SERVER_HOSTNAMES):
        return "server"

    # ── IoT ───────────────────────────────────────────────────────────────────
    if any(v in vendor_l for v in _IOT_VENDORS):
        return "iot"
    if any(h in hostname_l for h in _IOT_HOSTNAMES):
        return "iot"

    # ── Workstation ───────────────────────────────────────────────────────────
    if any(v in vendor_l for v in _WORKSTATION_VENDORS):
        return "workstation"
    if "windows" in os_l or "macos" in os_l or "mac os" in os_l:
        return "workstation"

    return "unknown"
