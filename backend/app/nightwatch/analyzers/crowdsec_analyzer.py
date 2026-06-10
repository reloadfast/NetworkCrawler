"""CrowdSec data analyzer — transforms raw alert/journal data into structured findings.

Handles:
- Top banned IPs (frequency-aggregated)
- Attack scenario clustering
- New/escalating threats
- Temporal patterns (rapid-fire bans)
- Cross-reference helper: match against ntopng hosts
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ── Data classes ─────────────────────────────────────────────────────────────────


@dataclass
class BanFinding:
    """A finding about banned IPs."""

    severity: str
    summary: str
    ip: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioFinding:
    """A finding about attack scenarios."""

    severity: str
    summary: str
    scenario: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class TemporalFinding:
    """A finding about temporal attack patterns."""

    severity: str
    summary: str
    details: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════


def crowdsec_analyze(crowdsec_data: dict[str, Any]) -> dict[str, Any]:
    """Analyze raw CrowdSec data and return structured findings.

    Args:
        crowdsec_data: Raw data dict from fetcher.fetch_all_data().

    Returns:
        Dict with ban_findings, scenario_findings, temporal_findings,
        total_alerts, active_ban_count, and findings list.
    """
    alerts = crowdsec_data.get("alerts", [])
    journal = crowdsec_data.get("journal", [])

    ban_findings = _analyze_bans(alerts)
    scenario_findings = _analyze_scenarios(alerts, journal)
    temporal_findings = _analyze_temporal(alerts, journal)

    findings = _to_findings_list(ban_findings, scenario_findings, temporal_findings)

    return {
        "ban_findings": ban_findings,
        "scenario_findings": scenario_findings,
        "temporal_findings": temporal_findings,
        "findings": findings,
        "total_alerts": len(alerts),
        "active_ban_count": crowdsec_data.get("active_ban_count", len(alerts)),
        "ban_by_ip": crowdsec_data.get("bans", {}),
        "ban_by_reason": crowdsec_data.get("reasons", {}),
    }


# ═══════════════════════════════════════════════════════════════════════════════


def _to_findings_list(bans, scenarios, temporal) -> list[dict[str, Any]]:
    """Flatten all finding types into common list-of-dicts."""
    out: list[dict[str, Any]] = []

    for f in bans:
        out.append(
            {
                "source": "crowdsec",
                "category": "ban",
                "severity": f.severity,
                "summary": f.summary,
                "device": f.ip,
                "details": f.details,
            }
        )
    for f in scenarios:
        out.append(
            {
                "source": "crowdsec",
                "category": "scenario",
                "severity": f.severity,
                "summary": f.summary,
                "details": f.details,
            }
        )
    for f in temporal:
        out.append(
            {
                "source": "crowdsec",
                "category": "temporal_pattern",
                "severity": f.severity,
                "summary": f.summary,
                "details": f.details,
            }
        )
    return out


# ── Analysis phases ─────────────────────────────────────────────────────────


def _analyze_bans(alerts: list[dict[str, Any]]) -> list[BanFinding]:
    """Aggregate bans by IP, flag repeat offenders and high-severity scenarios."""
    findings: list[BanFinding] = []
    if not alerts:
        return findings

    # Count bans per IP
    ip_counter: Counter = Counter()
    ip_reasons: dict[str, list[str]] = {}
    ip_scores: dict[str, int] = {}

    for alert in alerts:
        ip = alert.get("ip", "unknown") if isinstance(alert, dict) else "unknown"
        reason = alert.get("reason", alert.get("scenario", "unknown"))
        score = alert.get("score", 0)

        ip_counter[ip] += 1
        ip_reasons.setdefault(ip, []).append(reason)
        ip_scores[ip] = max(ip_scores.get(ip, 0), score)

    for ip, count in ip_counter.most_common():
        if count == 1:
            continue  # single ban is noise

        score = ip_scores.get(ip, 0)
        reasons = ip_reasons[ip]
        reason_cats = _categorize_reasons(reasons)

        if score >= 9:
            sev = "critical"
            summary = (
                f"Persistent attacker: {ip} banned {count} times "
                f"(score: {score}) — {', '.join(set(reason_cats))}"
            )
        elif score >= 5:
            sev = "high"
            summary = f"Repeat offender: {ip} banned {count} times"
        elif count >= 5:
            sev = "high"
            summary = f"High-frequency bans: {ip} ({count} times)"
        else:
            sev = "medium"
            summary = f"Multiple bans: {ip} ({count} times)"

        findings.append(
            BanFinding(
                severity=sev,
                summary=summary,
                ip=ip,
                details={
                    "ban_count": count,
                    "max_score": score,
                    "reasons": list(set(reason_cats)),
                    "raw_reasons": reasons,
                },
            )
        )

    # Flag IPs that are still actively banned with score >= critical
    still_active = [
        a
        for a in alerts
        if a.get("expire", "") and datetime.now().isoformat().replace("Z", "") < a.get("expire", "")
    ]
    active_ips = Counter(a.get("ip", "unknown") for a in still_active if isinstance(a, dict))

    for ip, count in active_ips.most_common(10):
        if count >= 3:
            already = [f for f in findings if f.ip == ip]
            if not already:
                findings.append(
                    BanFinding(
                        severity="medium",
                        summary=f"Still actively banned {count} times: {ip}",
                        ip=ip,
                        details={"remaining_bans": count, "status": "active_ban"},
                    )
                )
    return findings


def _analyze_scenarios(
    alerts: list[dict[str, Any]], journal: list[dict[str, Any]]
) -> list[ScenarioFinding]:
    """Cluster attack scenarios by frequency and severity."""
    findings: list[ScenarioFinding] = []
    if not alerts:
        return findings

    # Count scenarios
    scenario_counter: Counter = Counter()
    scenario_scores: dict[str, int] = {}

    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        scenario = alert.get("scenario", alert.get("reason", "unknown"))
        score = alert.get("score", 0)
        scenario_counter[scenario] += 1
        scenario_scores[scenario] = max(scenario_scores.get(scenario, 0), score)

    for scenario, count in scenario_counter.most_common():
        score = scenario_scores.get(scenario, 0)

        if score >= 9:
            sev = "critical"
        elif score >= 5:
            sev = "high"
        elif count >= 5:
            sev = "high"
        elif count >= 3:
            sev = "medium"
        else:
            sev = "low"

        summary = f"Attack scenario: {scenario} ({count} times, score {score})"

        findings.append(
            ScenarioFinding(
                severity=sev,
                summary=summary,
                scenario=scenario,
                details={"count": count, "score": score},
            )
        )

    # Check journal for new scenarios not present in active alerts
    if journal:
        active_scenarios = set(scenario_counter.keys())
        for event in (e for e in journal if isinstance(e, dict)):
            scen = event.get("scenario", event.get("id", ""))
            if scen and scen not in active_scenarios:
                findings.append(
                    ScenarioFinding(
                        severity="medium",
                        summary=f"New scenario detected (journal only): {scen}",
                        scenario=scen,
                        details={"source": "journal_not_in_alerts"},
                    )
                )
    return findings


def _categorize_reasons(reasons: list[str]) -> set[str]:
    """Map raw CrowdSec reasons to high-level categories."""
    cats: set[str] = set()
    for r in reasons:
        rl = r.lower()
        if "brute" in rl or "password" in rl:
            cats.add("Brute-force")
        elif "scan" in rl:
            cats.add("Scanning")
        elif "exploit" in rl or "cve" in rl or "rce" in rl:
            cats.add("Exploitation")
        elif "malware" in rl or "trojan" in rl or "botnet" in rl:
            cats.add("Malware/Botnet")
        elif "wp" in rl:
            cats.add("WordPress attack")
        elif "email" in rl or "smtp" in rl:
            cats.add("Email attack")
        elif "dns" in rl:
            cats.add("DNS abuse")
        else:
            cats.add("Other")
    return cats


def _analyze_temporal(
    alerts: list[dict[str, Any]], journal: list[dict[str, Any]]
) -> list[TemporalFinding]:
    """Detect temporal attack patterns: rapid-fire, sustained pressure."""
    findings: list[TemporalFinding] = []

    # Parse alert timestamps
    timestamps: list[datetime] = []
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        ts_str = alert.get("expire", "") or alert.get("created", "")
        if ts_str:
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                timestamps.append(dt)
            except ValueError:
                pass

    timestamps.sort()
    if len(timestamps) < 2:
        return findings

    # Check for burst: many alerts in short window
    best_window_size = max(1, len(timestamps) // 3)
    for i in range(len(timestamps) - best_window_size + 1):
        window_ts = timestamps[i : i + best_window_size]
        span = (window_ts[-1] - window_ts[0]).total_seconds()
        if span < 60 * 60 and best_window_size >= 5:
            findings.append(
                TemporalFinding(
                    severity="high",
                    summary=f"Attack burst: {best_window_size} alerts in {span:.0f}s",
                    details={
                        "window_start": window_ts[0].isoformat(),
                        "window_end": window_ts[-1].isoformat(),
                        "count": best_window_size,
                        "span_seconds": span,
                    },
                )
            )
            break

    # Check for sustained: alerts spanning >24h
    if len(timestamps) > 2:
        total_span = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
        if total_span > 24:
            rate = len(timestamps) / total_span
            if rate > 0.5:
                findings.append(
                    TemporalFinding(
                        severity="medium",
                        summary=f"Sustained pressure: {len(timestamps)} alerts over {total_span:.0f}h "
                        f"(~{rate:.2f}/hr)",
                        details={
                            "total_alerts": len(timestamps),
                            "span_hours": total_span,
                            "per_hour_rate": rate,
                        },
                    )
                )
    return findings
