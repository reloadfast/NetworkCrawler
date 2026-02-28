# NetworkCrawler — Copilot Instructions

## Autonomy Rules

Proceed without asking for confirmation on all routine operations. Only stop for:
- Irreversible data loss (dropping DB tables, `rm -rf`, overwriting uncommitted work)
- Pushing to remote / opening PRs (`git push`, `gh pr create`, `gh pr merge`)
- Publishing container images (`docker push`)
- Creating GitHub releases or tags (`gh release create`, `git tag` + push)
- Removing Docker volumes or persistent data (`docker-compose down -v`, `docker volume rm`)
- Direct writes or deletes against the live SQLite database outside of application code
- Breaking public API contracts that affect other issues/phases
- Adding new external services or third-party dependencies not already in the manifest

Proceed freely without prompting for:
- Reading, creating, editing, or deleting files anywhere in this repo
- Running tests, linters, formatters, security scans
- Creating git commits (but not pushing)
- Installing packages into the local venv / node_modules
- Creating branches
- Any action that is fully reversible with `git checkout` or `git reset`

---

## Token Efficiency Rules

- Be concise. No preamble, no summaries unless asked.
- Reference file:line instead of reproducing code blocks.
- Use bullet lists, not prose paragraphs.
- Skip "I will now..." or "Here is the..." phrases.
- When editing, show only changed lines with minimal context.
- Batch related file reads; avoid re-reading already-known files.

---

## Project Overview

- **Purpose:** Give home lab and self-hosting enthusiasts clear visibility into their own LAN security posture — without enterprise tooling or external data transmission.
- **Target user:** Home lab operators, self-hosters, and technically curious home network owners who want practical hardening guidance.
- **Key constraints:** Local-first and privacy-preserving at all times; all scanning and data stays on the LAN; no cloud APIs, no external telemetry, no automated system modification.
- **Scope boundary:** Discovers and analyses only LAN-visible systems; focuses on high-impact misconfigurations and actionable hardening advice, not exhaustive CVE enumeration or IDS/IPS replacement.
- **Goal:** Clarity over complexity — informed hardening, not automation.
- **Deployment target:** Single Docker container (or Docker Compose) on a LAN-connected host; accessible only within the home network; Unraid Community Applications support.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend framework | React 18 + TypeScript |
| Frontend build tool | Vite |
| UI styling | Tailwind CSS (CSS variables for theming) |
| Component library | Custom reusable components (Card, Badge, ProgressBar, Chart) |
| Backend framework | FastAPI (Python 3.11+) |
| Network discovery | nmap, arp-scan |
| Data storage | SQLite (via SQLAlchemy) |
| Background tasks | FastAPI BackgroundTasks / APScheduler |
| Container runtime | Docker + Docker Compose |
| Unraid deployment | Community Applications XML template |
| Backend testing | Pytest |
| Frontend testing | Vitest + React Testing Library |
| Linting (Python) | Ruff |
| Linting (JS/TS) | ESLint + Prettier |
| Dependency auditing | pip-audit (Python), npm audit (JS) |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Home LAN (trusted boundary)         │
│                                                     │
│  ┌──────────────┐   HTTP/REST    ┌───────────────┐  │
│  │  Browser     │◄──────────────►│  FastAPI      │  │
│  │  React UI    │   :8000/api    │  Backend      │  │
│  │  (:3000 dev) │                │               │  │
│  └──────────────┘                │  ┌─────────┐  │  │
│                                  │  │ SQLite  │  │  │
│                                  │  │  DB     │  │  │
│                                  │  └─────────┘  │  │
│                                  │               │  │
│                                  │  ┌─────────┐  │  │
│                                  │  │ Scanner │  │  │
│                                  │  │ (nmap + │  │  │
│                                  │  │arp-scan)│  │  │
│                                  │  └────┬────┘  │  │
│                                  └───────┼───────┘  │
│                                          │           │
│         LAN devices ◄────────────────────┘           │
│         (ARP + port scan, read-only)                 │
└─────────────────────────────────────────────────────┘

Production (Docker):
  - Single container or Compose stack
  - Frontend static assets served by FastAPI (or nginx sidecar)
  - Bind to 0.0.0.0 within LAN; no external exposure
  - Container uses host network mode for ARP visibility
```

---

## Project Structure

```
networkCrawler/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app entrypoint
│   │   ├── api/                  # Route handlers (devices, scans, risks)
│   │   ├── scanner/              # nmap + arp-scan integration
│   │   ├── analysis/             # Risk detection + misconfiguration checks
│   │   ├── recommendations/      # Hardening advice engine
│   │   ├── models/               # SQLAlchemy models
│   │   └── db.py                 # Database connection + migrations
│   ├── tests/                    # Pytest test suite
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/           # Reusable UI (Card, Badge, ProgressBar, Chart)
│   │   ├── pages/                # Dashboard, Devices, Risks, Recommendations
│   │   ├── hooks/                # Data fetching hooks
│   │   ├── styles/               # CSS variables / theme tokens
│   │   └── main.tsx
│   ├── tests/                    # Vitest test suite
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── unraid/                       # GITIGNORED — internal/local use only
│   └── NetworkCrawler.xml
├── .env.example
├── .gitignore
└── system_config.md
```

---

## Sensitive Data Rules

- **NEVER** commit `.env`, secrets, tokens, API keys, or passwords
- All secrets via environment variables; document in `.env.example` with placeholder values only
- Local data files (SQLite database, scan caches) are gitignored
- Deployment-specific config files are gitignored
- No external API keys exist in this project by design — all scanning is local
- The `unraid/` directory is gitignored entirely — never commit or reference it in public docs
- No hardcoded credentials, IPs, or subnet ranges anywhere in source code

---

## Environment Variables

All configuration is via environment variables. Never hardcode these values in source.

```dotenv
NETWORK_INTERFACE=eth0         # Host network interface to scan from
SCAN_SUBNET=192.168.1.0/24     # CIDR subnet to discover devices within
SCAN_INTERVAL_SECONDS=3600     # How often to run automatic background scans
LOG_LEVEL=INFO                 # Logging verbosity (DEBUG, INFO, WARNING, ERROR)
```

- Document all new env vars in `.env.example` with a placeholder and description before use.
- Never assign real values in `.env.example`.

---

## Unraid Template

The Unraid Community Applications template lives at `unraid/NetworkCrawler.xml` (gitignored — internal use and local testing only).

- **Never reference this file in public-facing documentation** (README, CONTRIBUTING, or any user-visible content)
- **Update the template as part of acceptance criteria** whenever any of the following change:
  - Ports, env vars, volume mounts, or container name
  - Docker runtime requirements (`cap_add`, `network_mode`, `privileged`, `devices`)
  - Scanner behaviour that affects how users must configure the interface or subnet
  - Any user-facing error message or troubleshooting guidance referenced in `Description` fields
- Always add a dated `### YYYY-MM-DD` entry to the `<Changes>` block describing what changed
- All env vars in the template must stay in sync with `.env.example` — same names, same defaults
- Container requires `network_mode: host` and `--cap-add=NET_RAW`; both are set in `<Network>` and `<ExtraParams>` — never remove them
- After structural changes, test by importing the template into Unraid CA

---

## Testing Requirements

- **Backend:** ≥80% line coverage; tests in `backend/tests/`; use markers: `unit`, `integration`
- **Frontend:** key components and hooks covered; generate coverage report via Vitest
- **Every new feature or bug fix must include a corresponding test** — PRs without tests for changed behaviour will not be merged
- All tests must pass before merge to main
- Run `pip-audit` and `npm audit` on every PR; fail on HIGH severity findings
- No `# noqa` or `// eslint-disable` without an inline justification comment
- Integration tests for scanner module must use mocked nmap/arp-scan output — **never run live scans in CI**
- Use `pytest -m unit` for fast local runs; `pytest -m integration` requires mock fixtures, not live network

---

## Security

Security is the primary concern of this project — treat all security rules as non-negotiable.

- **No hardcoded credentials, secrets, tokens, or sensitive values anywhere in the codebase**
- Fail CI on HIGH severity static analysis findings (Ruff + pip-audit for Python; ESLint + npm audit for JS)
- Fail CI on known CVEs in dependencies
- FastAPI must bind only to the local interface in production; document this clearly
- HTTP security headers on all responses: `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`
- Container runs as a non-root user
- nmap and arp-scan require elevated privileges — use `--cap-add=NET_RAW` in Docker rather than running as root
- Validate and sanitise all user-supplied inputs before passing to scanner modules
- Log security-relevant events (scan start/stop, errors) at appropriate log levels; never log sensitive data

---

## Git Conventions

- Branch prefixes: `feature/`, `fix/`, `chore/`, `docs/`
- Commits: conventional commits (`feat:`, `fix:`, `chore:`, `test:`, `docs:`)
- PRs require CI green before merge
- main branch = deployable state at all times
- When creating GitHub issues, always add them to the project roadmap if one exists (`gh issue edit <n> --add-project "NetworkCrawler"` or `gh issue create --add-project "NetworkCrawler"`)
- When merging a PR, close all issues it resolves (`gh issue close <n> --comment "Implemented in #<PR>."`)
- If issues were auto-closed by the PR merge, verify and skip redundant close commands

---

## Parallel Agents

Multiple Claude agents may work on this repo simultaneously on separate branches. To avoid cross-contamination:
- Before fixing any CI failure, run `git diff main...HEAD -- <file>` to confirm the offending code is within your branch's diff
- If the failure is in a file you did not touch (introduced by another agent on main), do NOT fix it in the current branch — create a separate `fix/` branch targeting main and open its own PR
- Each branch/PR must own only the changes scoped to its issue; never absorb unrelated fixes to make CI green

---

## Domain Knowledge

### Network Discovery

- **ARP scan:** Sends ARP requests across the subnet to enumerate live hosts; more reliable than ICMP on LAN; requires raw socket access (`NET_RAW` capability).
- **nmap:** Used for port scanning and service/version detection on discovered hosts. Key scan types:
  - `-sn` — ping scan / host discovery only
  - `-sV` — service version detection
  - `-O` — OS detection (best-effort)
  - `--top-ports 1000` — default scope; avoid full 65535 scan for performance
- Scan results are parsed from nmap XML output (`-oX`).

### Risk Model

Risks are classified on a four-tier severity scale:

| Severity | Meaning | Colour token |
|---|---|---|
| `critical` | Immediate exploitation risk (e.g. open Telnet, default credentials confirmed) | `accent-danger` |
| `high` | Serious misconfiguration likely to be exploited (e.g. admin UI exposed on WAN-facing port) | `accent-danger` |
| `medium` | Notable exposure that should be addressed (e.g. HTTP instead of HTTPS on admin panel) | `accent-warning` |
| `low` | Minor hardening opportunity (e.g. unnecessary open port, outdated banner) | `accent-positive` / muted |

### Common Misconfiguration Checks

- Default or well-known admin credentials on detected services
- Telnet (port 23), FTP (port 21), unencrypted HTTP on management interfaces
- UPnP exposed on non-router devices
- SSH with password authentication enabled (vs key-only)
- Open SMB (445) or NetBIOS (137–139) ports on non-NAS devices
- Printer/IoT devices with admin UIs exposed on default ports (80, 8080, 8443)
- Devices running outdated service banners (detectable via nmap `-sV`)

### Hardening Recommendation Schema

```json
{
  "id": "string",
  "device_id": "string",
  "severity": "critical | high | medium | low",
  "title": "short plain-language title",
  "description": "what was found and why it matters",
  "steps": ["step 1", "step 2", "..."],
  "effort": "low | medium | high",
  "impact": "low | medium | high"
}
```

### UI Theme Tokens

| Token | Usage |
|---|---|
| `--color-background` | Page background |
| `--color-surface` | Card / panel background |
| `--color-border` | Subtle borders |
| `--color-text-primary` | Main body text |
| `--color-text-secondary` | Muted / label text |
| `--color-accent-positive` | Emerald/teal — healthy, no issues |
| `--color-accent-warning` | Amber/yellow — partial or medium risk |
| `--color-accent-danger` | Red/pink — critical or high risk |

---

## Development Phases

1. **Foundation** — Project scaffold (monorepo structure, Docker + Compose, CI pipeline, linting, test harness, `.env.example`, gitignore, Unraid template skeleton).
2. **Discovery** — Backend LAN scanner (arp-scan + nmap integration, XML parsing, SQLite device inventory, background scheduler, REST API for device list).
3. **Analysis** — Risk detection engine (misconfiguration checks against discovered services, severity classification, risk records stored in DB, REST API for risks).
4. **UI** — React dashboard (device inventory view, network map/list, risk overview, severity badges, dark/light theme system, responsive layout per UI_style.md).
5. **Hardening Advice** — Recommendation engine (per-device step-by-step hardening guidance, effort/impact scoring, recommendation detail views in UI).
6. **Polish** — UX refinement (scan progress indicators, animations, empty states, accessibility audit, performance optimisation, documentation, final Unraid template validation).
