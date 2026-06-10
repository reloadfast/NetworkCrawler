"""Digest builder — structured data assembly and LLM prompt generation.

Takes analyzed data from ntopng_analyzer, crowdsec_analyzer, and
cross_reference, assembles context, calls LLM, and parses structured
response (findings + actions + commands).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.nightwatch import llm_client
from app.nightwatch.analyzers import cross_reference, crowdsec_analyzer, ntopng_analyzer

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a home network security analyst reviewing a daily digest
of LAN traffic and threat intelligence.

You have ALREADY received structured analysis from dedicated
analyzers — your job is to refine, prioritize, and suggest concrete
remediation actions.

Return ONLY valid JSON with no explanation, markdown, or extra text.

Output schema:
{
  "findings": [
    {
      "source": "networkcrawler" | "ntopng" | "crowdsec" | "cross_reference",
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
- Merge overlapping findings from different sources.
- Always include actionable commands — the operator needs concrete remediation.
- Prioritize by severity in the actions array (critical first).
- If the LLM finds the analysis insufficient, note what data would help.
"""


def _assemble_ntopng_section(ntopng_data: dict[str, Any]) -> str:
    """Format pre-analyzed ntopng data into structured text."""
    lines = ["## Ntopng Analysis"]

    # Run analyzer if not already analyzed
    if isinstance(ntopng_data.get("findings"), list) and ntopng_data["findings"]:
        analysis = ntopng_data
    else:
        analysis = ntopng_analyzer.ntopng_analyze(ntopng_data)

    bw_findings = getattr(analysis, "bandwidth_findings", []) or []
    proto_findings = getattr(analysis, "protocol_findings", []) or []
    host_findings = getattr(analysis, "host_findings", []) or []
    flow_findings = getattr(analysis, "flow_findings", []) or []

    if bw_findings:
        lines.append("- Bandwidth anomalies:")
        for f in bw_findings[:10]:
            lines.append(f"  - [{f.severity}] {f.summary}")
    else:
        lines.append("- Bandwidth: normal")

    if proto_findings:
        lines.append("- Protocol issues:")
        for f in proto_findings[:10]:
            lines.append(f"  - [{f.severity}] {f.summary}")
    else:
        lines.append("- Protocols: normal")

    if host_findings:
        lines.append("- Host issues:")
        for f in host_findings[:10]:
            lines.append(f"  - [{f.severity}] {f.summary}")
    else:
        lines.append("- Hosts: normal")

    if flow_findings:
        lines.append("- Flow anomalies:")
        for f in flow_findings[:5]:
            lines.append(f"  - [{f.severity}] {f.summary}")
    else:
        lines.append("- Flows: normal")

    return "\n".join(lines)


def _assemble_crowdsec_section(crowdsec_data: dict[str, Any]) -> str:
    """Format pre-analyzed CrowdSec data into structured text."""
    lines = ["## CrowdSec Analysis"]

    analysis = crowdsec_analyzer.crowdsec_analyze(crowdsec_data)

    ban_findings = analysis.get("ban_findings", [])
    scenario_findings = analysis.get("scenario_findings", [])
    temporal_findings = analysis.get("temporal_findings", [])

    if ban_findings:
        lines.append("- Banned repeat offenders:")
        for f in ban_findings[:10]:
            lines.append(f"  - [{f.severity}] {f.summary}")
    else:
        lines.append("- No repeat offenders found")

    if scenario_findings:
        lines.append("- Attack scenarios:")
        for f in scenario_findings[:10]:
            lines.append(f"  - [{f.severity}] {f.summary}")
    else:
        lines.append("- No notable attack scenarios")

    if temporal_findings:
        lines.append("- Temporal patterns:")
        for f in temporal_findings:
            lines.append(f"  - [{f.severity}] {f.summary}")
    else:
        lines.append("- No temporal anomalies")

    lines.append(f"- Total alerts: {analysis.get('total_alerts', 0)}")
    lines.append(f"- Active bans: {analysis.get('active_ban_count', 0)}")

    return "\n".join(lines)


def _assemble_cross_ref_section(crowdsec_data: dict[str, Any], ntopng_data: dict[str, Any]) -> str:
    """Format cross-reference findings into text."""
    lines = ["## Cross-Reference Analysis"]

    cross_findings = cross_reference.cross_reference(crowdsec_data, ntopng_data)

    if cross_findings:
        lines.append("- Correlations:")
        for f in cross_findings:
            lines.append(f"  - [{f.severity}] {f.summary}")
    else:
        lines.append("- No cross-source correlations")

    return "\n".join(lines)


def _get_networkcrawler_data(db) -> str:
    """Get NetworkCrawler scan data from database."""
    try:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

        from app.models.risk import Risk

        if not isinstance(db, Session):
            return "- NetworkCrawler data: unavailable"

        risks = db.execute(select(Risk).where(Risk.acknowledged_at.is_(None))).scalars().all()

        if risks:
            counts: dict[str, int] = {}
            for risk in risks:
                sev = risk.severity
                counts[sev] = counts.get(sev, 0) + 1
            sev_strs = [
                f"{s}: {counts[s]}" for s in ["critical", "high", "medium", "low"] if counts.get(s)
            ]
            return f"- Active risks: {', '.join(sev_strs)}"
        else:
            return "- Active risks: 0"

    except Exception:
        return "- NetworkCrawler data: unavailable"


def call_llm(
    db,
    ntopng_data: dict,
    crowdsec_data: dict,
) -> dict[str, Any]:
    """Call LLM with compiled context and return parsed response.

    Args:
        db: SQLAlchemy session.
        ntopng_data: pre-analyzed ntopng data.
        crowdsec_data: pre-analyzed CrowdSec data.

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

    # Build structured prompt from pre-analyzed data
    prompt_parts = []
    prompt_parts.append(_assemble_ntopng_section(ntopng_data))
    prompt_parts.append(_assemble_crowdsec_section(crowdsec_data))
    prompt_parts.append(_assemble_cross_ref_section(crowdsec_data, ntopng_data))
    prompt_parts.append(_get_networkcrawler_data(db))

    context_text = "\n".join(prompt_parts)

    user_prompt = (
        f"Analyze the following structured findings and return actions as JSON:\n\n"
        f"{context_text}\n\n"
        f"Provide findings and actions. Focus on high-impact remediation. "
        f"Include specific commands where actionable."
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
        lines.append(f"_summary: {summary}_")
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
