"""Network context profiles — adjust how risk severities are displayed.

The stored severity is never mutated; only the presentation layer uses
these overrides so that re-scans don't lose the original classification.

Supported profiles:
  standard_home   Conservative defaults (the out-of-the-box experience).
  home_lab        Relaxed — SSH/multiple ports are expected, not alarming.
  privacy_focused Stricter — unencrypted protocols escalate to critical.
"""

from __future__ import annotations

VALID_PROFILES = ("standard_home", "home_lab", "privacy_focused")
DEFAULT_PROFILE = "standard_home"

PROFILE_LABELS: dict[str, str] = {
    "standard_home": "Standard Home",
    "home_lab": "Home Lab",
    "privacy_focused": "Privacy Focused",
}

PROFILE_DESCRIPTIONS: dict[str, str] = {
    "standard_home": ("Conservative defaults. SSH open = high. Any open admin panel = high."),
    "home_lab": (
        "Relaxed. SSH with key-auth = low. Multiple open ports are expected."
        " Focus on externally-reachable risks."
    ),
    "privacy_focused": ("Stricter. Any unencrypted protocol = critical. DNS resolver = critical."),
}

# check_id → override severity per profile.
# Only entries that differ from the stored severity need to be listed.
_OVERRIDES: dict[str, dict[str, str]] = {
    "home_lab": {
        "open_ssh": "low",
        "open_telnet": "medium",  # still bad but less alarming in a lab
        "multiple_open_ports": "low",
        "open_rdp": "medium",
    },
    "privacy_focused": {
        "open_http": "critical",
        "open_telnet": "critical",
        "open_ftp": "critical",
        "open_dns": "critical",
        "open_snmp": "critical",
        "weak_tls": "critical",
        "unencrypted_protocol": "critical",
    },
}


def display_severity(stored_severity: str, profile: str) -> str:
    """Return the display severity for a check under the given profile.

    Falls back to ``stored_severity`` when no override exists.
    """
    if profile not in VALID_PROFILES:
        profile = DEFAULT_PROFILE
    overrides = _OVERRIDES.get(profile, {})
    return overrides.get(stored_severity, stored_severity)


def display_severity_for_check(check_id: str, stored_severity: str, profile: str) -> str:
    """Return display severity using check_id-specific overrides."""
    if profile not in VALID_PROFILES:
        profile = DEFAULT_PROFILE
    overrides = _OVERRIDES.get(profile, {})
    return overrides.get(check_id, stored_severity)
