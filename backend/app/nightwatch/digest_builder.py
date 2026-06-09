"""Digest builder — LLM prompt assembly and response parsing.

Takes raw data from ntopng, CrowdSec, and NetworkCrawler, assembles context,
calls LLM, and parses structured response (findings + actions + commands).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.nightwatch import llm_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a home network security analyst reviewing a daily digest
of LAN traffic and threat intelligence.

Your task is to analyze the provided data and return ONLY valid JSON
with no explanation, markdown, or extra text.

Output schema:
{
  "findings": [
    {
      "source": "networkcrawler" | "ntopng" | "crowdsec",
      "summary": "one-line description of the event",
      "severity": "critical" | "high" | "medium" | "low",
      "device": "IP, hostname, or description"
    }
  ],
  "actions": [
    {
      "title": "brief action name",
      "description": "what to do and why",
      "priority": "critical" | "high" | "medium" | "low",
      "commands": ["one or two shell commands to execute"]
    }
  ]
}

Guidelines:
- Return EVERY significant finding (all critical, high, and notable medium).
- Always include actionable commands — the operator needs concrete remediation steps.
- Prioritize by severity in the actions array (critical first).
- If NetworkCrawler scan found new risky devices, note them.
- If CrowdSec shows active bans, note IPs and recommend firewall rule updates.
- If ntopng shows unusual traffic patterns, identify the device and protocol causing it.
"""


def _format_data_for_prompt(ntopng_data: dict, crowdsec_data: dict, db) -> str:
    """Format all data sources into a single prompt payload string.

    Args:
        ntopng_data: Data from ntopng_fetcher.fetch_all_data().
        crowdsec_data: Data from crowdsec_fetcher.fetch_all_data().
        db: SQLAlchemy session (for NetworkCrawler data).

    Returns:
        Concatenated formatted string.
    """
    parts: list[str] = []

    # ntopng section
    lines = ["## ntopng Data"]
    if ntopng_data.get("top_talkers"):
        for talker in ntopng_data["top_talkers"][:10]:
            name = talker.get("device", "unknown")
            b_sent = talker.get("bytes_sent", 0)
            b_recv = talker.get("bytes_recv", 0)
            total = b_sent + b_recv
            lines.append(f"- {name}: {total} bytes total (sent: {b_sent}, recv: {b_recv})")
    else:
        lines.append("- No top talkers available")

    protocols = ntopng_data.get("protocols", {})
    if isinstance(protocols, dict):
        total_bytes = sum(protocols.values())
        if total_bytes > 0:
            lines.append("- Protocol distribution:")
            for proto, count in sorted(protocols.items(), key=lambda x: x[1], reverse=True)[:10]:
                pct = count / total_bytes * 100
                lines.append(f"  {proto}: {count} bytes ({pct:.1f}%)")
        else:
            lines.append("- Protocol distribution: empty or zero bytes")
    else:
        lines.append("- Protocol data not available")

    if ntopng_data.get("alerts"):
        lines.append("- ntopng alerts:")
        for alert in ntopng_data["alerts"][:5]:
            lines.append(f"  - {alert.get('alert', 'unknown')}")

    if ntopng_data.get("unusual_protocols"):
        # unusual protocols are those not in common set
        unusual = ntopng_data["unusual_protocols"]
        if unusual:
            lines.append("- Unusual protocols detected:")
            for proto, count in list(unusual.items())[:5]:
                lines.append(f"  - {proto}: {count} bytes")
    else:
        # compute if not pre-computed
        all_proto = ntopng_data.get("protocols", {})
        if isinstance(all_proto, dict):
            common = {
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
            }
            unusual = {k: v for k, v in all_proto.items() if k.upper() not in common and v > 0}
            if unusual:
                lines.append("- Unusual protocols detected:")
                for proto, count in list(unusual.items())[:5]:
                    lines.append(f"  - {proto}: {count} bytes")

    parts.append("\n".join(lines))

    # CrowdSec section
    lines = ["## CrowdSec Data"]
    bans = crowdsec_data.get("bans", {})
    if isinstance(bans, dict) and bans:
        lines.append("- Active bans by IP:")
        for ip, count in sorted(bans.items(), key=lambda x: x[1], reverse=True)[:10]:
            lines.append(f"  - {ip}: {count} ban(s)")
    else:
        lines.append("- No active bans")

    reasons = crowdsec_data.get("reasons", {})
    if isinstance(reasons, dict) and reasons:
        lines.append("- Ban reasons:")
        for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"  - {reason}: {count}")

    alerts = crowdsec_data.get("alerts", [])
    if alerts and isinstance(alerts, list):
        lines.append(f"- Active threat alerts ({len(alerts)}):")
        for alert in alerts[:10]:
            ip = alert.get("ip", "unknown") if isinstance(alert, dict) else "unknown"
            reason = (
                alert.get("reason", "unspecified") if isinstance(alert, dict) else "unspecified"
            )
            lines.append(f"  - {ip}: {reason}")

    parts.append("\n".join(lines))

    # NetworkCrawler section
    lines = ["## NetworkCrawler Scan Data"]
    _nctx = _get_networkcrawler_data(db)
    if _nctx:
        lines.append(_nctx)
    else:
        lines.append("- NetworkCrawler data not available")

    parts.append("\n".join(lines))

    return "\n".join(parts)


def _get_networkcrawler_data(db) -> str | None:
    """Get NetworkCrawler scan data from database.

    Args:
        db: SQLAlchemy session.

    Returns:
        Formatted string or None if no database.
    """
    try:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from app.models.risk import Risk
        from app.models.scan_event import ScanEvent

        if not isinstance(db, Session):
            return None

        # Active risks
        risks = db.execute(select(Risk).where(Risk.acknowledged_at.is_(None))).scalars().all()

        if risks:
            counts = {}
            for risk in risks:
                sev = risk.severity
                counts[sev] = counts.get(sev, 0) + 1
            sev_strs = [
                f"{s}: {counts[s]}" for s in ["critical", "high", "medium", "low"] if counts.get(s)
            ]
            return f"- Active risks: {', '.join(sev_strs)}"
        else:
            return "- Active risks: 0"

        # New devices
        new_events = (
            db.execute(
                select(ScanEvent)
                .where(
                    ScanEvent.event_type == "new_device",
                )
                .order_by(ScanEvent.occurred_at.desc())
                .limit(5)
            )
            .scalars()
            .all()
        )

        if new_events:
            return f"- New devices: {len(new_events)}"

    except Exception:  # noqa: BLE001 — broad catch for best-effort digest generation
        return None

    return None


def call_llm(
    db,
    ntopng_data: dict,
    crowdsec_data: dict,
) -> dict[str, Any]:
    """Call LLM with compiled context and return parsed response.

    Args:
        db: SQLAlchemy session.
        ntopng_data: ntopng data from fetcher.
        crowdsec_data: CrowdSec data from fetcher.

    Returns:
        Dict with 'findings' and 'actions' arrays.

    Raises:
        ValueError: If LLM call or JSON parse fails.
    """
    config = llm_client.get_config(db)
    llm_type = config.get("nightwatch_llm_type") or "ollama"
    endpoint = config.get("nightwatch_llm_endpoint") or ""
    model = config.get("nightwatch_llm_model") or "llama3.1:8b"
    api_key_enc = config.get("nightwatch_openai_api_key_enc")

    api_key = None
    if api_key_enc:
        api_key = llm_client.decrypt_api_key(api_key_enc)

    if not endpoint:
        raise ValueError("Nightwatch: LLM endpoint not configured")

    data_text = _format_data_for_prompt(ntopng_data, crowdsec_data, db)

    user_prompt = (
        f"Here is the data for today's Nightwatch digest:\n\n"
        f"{data_text}\n\n"
        f"Analyze this data and return findings and actions as JSON. "
        f"Include specific shell commands where actionable."
    )

    import httpx

    try:
        result = llm_client._call_llm(
            llm_type=llm_type,
            endpoint=endpoint,
            model=model,
            api_key=api_key,
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
    except httpx.HTTPError as exc:
        logger.error("LLM call failed: %s", exc)
        raise ValueError(f"Nightwatch: LLM call failed: {exc}") from exc

    # Parse JSON response
    try:
        parsed = llm_client._extract_json(result)
        if isinstance(parsed, dict):
            if "findings" in parsed and "actions" in parsed:
                return parsed
            # Model might have wrapped in other keys
            return {
                "findings": parsed.get("findings", []),
                "actions": parsed.get("actions", []),
            }
        return {"findings": [], "actions": []}
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("LLM JSON parse failed: %s (raw: %s)", exc, result[:200])
        raise ValueError(f"Nightwatch: LLM returned non-JSON (or malformed JSON): {exc}") from exc


def format_findings_as_text(findings: list[dict], actions: list[dict]) -> str:
    """Format findings and actions into a readable Telegram message.

    Args:
        findings: List of finding dicts.
        actions: List of action dicts.

    Returns:
        Formatted string message ready for Telegram.
    """
    lines = [
        "*Nightwatch Daily Digest*",
        "",
        "*Findings:*",
    ]

    for finding in findings:
        severity = finding.get("severity", "medium")
        severity_icons = {
            "critical": "\U0001f534",
            "high": "\U0001f7e0",
            "medium": "\U0001f7e1",
            "low": "\U0001f535",
        }
        emoji = severity_icons.get(severity, "\U0001f7e2")
        source = finding.get("source", "unknown").upper()
        lines.append(f"{emoji} *{severity.upper()}* ({source})")
        summary = finding.get("summary", "No summary")
        lines.append(f"*_summary: {summary}_*")
        device = finding.get("device", "")
        if device:
            lines.append(f"*Device:* `{device}`")
        lines.append("")

    if actions:
        lines.append("*Actions to Take:*")
        for idx, action in enumerate(actions, 1):
            title = action.get("title", f"Action {idx}")
            lines.append(f"*{idx}. {title}*")
            desc = action.get("description", "")
            if desc:
                lines.append(f"*Description: {desc}*")

            if action.get("commands"):
                lines.append("*_Commands:_*")
                for cmd in action["commands"]:
                    lines.append(f"`{cmd}`")

        lines.append("")

    import datetime

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"_Generated at {timestamp}._")

    return "\n".join(lines)
