# NetworkCrawler — CLAUDE.md

## Autonomy Rules
Proceed without asking for confirmation on all routine operations. Only stop for:
- Irreversible data loss (dropping DB tables, `rm -rf`, overwriting uncommitted work)
- Pushing to remote / opening PRs
- Breaking public API contracts that affect other issues/phases
- Adding new external services or third-party dependencies not already in the manifest

Proceed freely without prompting for:
- Reading, creating, editing, or deleting files anywhere in this repo
- Running tests, linters, formatters, security scans
- Creating git commits (but not pushing)
- Installing packages into the local venv / node_modules
- Creating branches
- Any action that is fully reversible with `git checkout` or `git reset`

## Token Efficiency Rules
- Be concise. No preamble, no summaries unless asked.
- Reference file:line instead of reproducing code blocks.
- Use bullet lists, not prose paragraphs.
- Skip "I will now..." or "Here is the..." phrases.
- When editing, show only changed lines with minimal context.
- Batch related file reads; avoid re-reading already-known files.

## Project Overview
- LAN security posture scanner for home lab operators
- Discovers devices via ARP/nmap, scores risk, and surfaces actionable recommendations
- Runs as a single Docker container; no external service dependencies (SQLite only)
- Deployed on Unraid (Tower) in host-network mode; operator is a solo user (Wind)
- Enhancement phase — core features complete; all work is incremental improvement

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy, SQLite |
| Scanner | arp-scan, nmap (subprocess), dns lookup |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Flow |
| Backend tests | pytest, pytest-cov, pytest-asyncio |
| Frontend tests | Vitest, @testing-library/react |
| Linting | ruff (Python), ESLint + Prettier (TS/CSS) |
| Container | Docker (multi-stage), gosu for privilege drop |
| CI | Forgejo Actions (self-hosted runner: `unraid-runner`) |
| Registry | Forgejo Container Registry (`forgejo.moseisley.es`) |

## Architecture

```
┌─────────────────────────────────────────────┐
│  Docker container (host network, NET_RAW)   │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │  uvicorn / FastAPI  :8000            │   │
│  │   ├── /api/*        REST endpoints   │   │
│  │   ├── /health       healthcheck      │   │
│  │   └── /*            static React SPA │   │
│  └──────────────┬───────────────────────┘   │
│                 │                           │
│  ┌──────────────▼───────────────────────┐   │
│  │  SQLite  /app/data/networkcrawler.db │   │
│  └──────────────────────────────────────┘   │
│                 │                           │
│  ┌──────────────▼───────────────────────┐   │
│  │  Scanner  (arp-scan, nmap, dns)      │   │
│  │  scheduled via SCAN_INTERVAL_SECONDS │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
         ↕  host network (LAN broadcast domain)
┌─────────────────────────────────────────────┐
│  LAN: Flint 2 router → 2.5 GB switch        │
│       → Tower (Unraid) + Fijo (workstation) │
└─────────────────────────────────────────────┘
```

## Project Structure

```
NetworkCrawler/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI router + all REST endpoints
│   │   ├── models/       # SQLAlchemy models (device, scan, risk, …)
│   │   ├── scanner/      # arp-scan, nmap, dns, os-inference submodules
│   │   ├── analysis/     # risk scoring logic
│   │   ├── recommendations/
│   │   ├── db.py         # engine, SessionLocal, schema migrations
│   │   ├── main.py       # app factory, lifespan, static file mount
│   │   ├── notifications.py
│   │   └── scan_runner.py
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   └── …
│   ├── tests/
│   ├── package.json
│   └── vite.config.ts
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── entrypoint.sh
├── tests/                # top-level integration / smoke tests
├── unraid/               # gitignored — internal Unraid CA template
└── .forgejo/workflows/   # CI (ci.yml + docker.yml)
```

## Sensitive Data Rules
- NEVER commit `.env`, secrets, tokens, API keys, or passwords
- All secrets via environment variables; document in `.env.example` with placeholder values only
- Local data files (databases, caches) are gitignored
- Deployment-specific config files are gitignored
- `unraid/` is gitignored — never commit the Unraid CA template

## Environment Variables

```
# Network scanning
NETWORK_INTERFACE=eth0        # interface arp-scan binds to
SCAN_SUBNET=192.168.1.0/24   # CIDR range to scan
SCAN_INTERVAL_SECONDS=3600   # auto-scan cadence in seconds

# Application
LOG_LEVEL=INFO                # DEBUG | INFO | WARNING | ERROR
DATABASE_URL=sqlite:////app/data/networkcrawler.db  # SQLite path inside container
APP_VERSION=dev               # injected by CI as git short SHA; do not set manually
```

## Unraid Template
The Unraid Community Applications template lives at `unraid/NetworkCrawler.xml`
- **Never reference this file in public-facing documentation** (README, CONTRIBUTING, or any user-visible content)
- Update the template as part of acceptance criteria whenever any of the following change: ports, env vars, volume mounts, container name
- All env vars in the template must stay in sync with `.env.example`
- If the project ever requires >1 container, create a separate `.xml` per container
- After structural changes, test by importing the template into Unraid CA through Izanagi
- Do not automatically deploy the container — that is done by the user
- Do not include traefik labels — that is done through Izanagi by the user
- Image reference in the template must point to `forgejo.moseisley.es/wind/networkcrawler:latest` — never DockerHub

## Testing Requirements
- Backend: ≥80% line coverage; tests in `backend/tests/`; use markers: `unit`, `integration`
- Frontend: key components and hooks covered; `npm run test:coverage`
- All tests must pass before merge to main
- Run security scans (pip-audit, npm audit) on every PR
- No `# noqa` or `// eslint-disable` without an inline justification comment

## Security
- Fail CI on HIGH severity static analysis findings (ruff S-rules, pip-audit, npm audit)
- No hardcoded credentials anywhere in the codebase
- Container runs as uid 1000 (non-root); NET_RAW granted via `--cap-add` at runtime, not Privileged
- `cap_net_raw+ep` set on `arp-scan` and `nmap` binaries via `setcap` in Dockerfile so non-root UID can open raw sockets

## Version Visibility
The application version must always be readable in the UI to aid troubleshooting.

**Source of truth** — git short SHA baked into the Docker image at build time:
- `docker/Dockerfile`: `ARG APP_VERSION=dev` → `ENV APP_VERSION=$APP_VERSION` in runtime stage
- CI passes `build-args: APP_VERSION=<7-char sha>` to `docker/build-push-action`
- Backend reads `os.environ.get("APP_VERSION", "dev")` in `app/main.py:_read_version()` and exposes via `GET /api/version`
- Frontend fetches and renders it in the UI

Do NOT use semver from `pyproject.toml` as the runtime version — it can drift from what is deployed. The git SHA is the only unambiguous identifier.

**Two image tags on every push to main:**
- `latest` — always points to the current main build
- `sha-XXXXXXX` — immutable; use for pinning, rollback, and identifying what is running

**Acceptance criteria — every release PR must satisfy:**
- [ ] Version renders correctly in the UI showing the deployed SHA
- [ ] `CHANGELOG.md` entry written (`## [YYYY-MM-DD] – sha-XXXXXXX` with Added / Changed / Fixed / Removed)

## Backlog / Roadmap Conventions
- All backlog, roadmap, and milestone tracking files must use codified IDs for every item (e.g. `SEC-001`, `BUG-003`, `UX-011`)
- ID format: `<CATEGORY>-<NNN>` — category is uppercase, number is zero-padded to 3 digits
- IDs must never be reused or renumbered once assigned; retired items stay in the file marked `[DONE]` or `[DROPPED]`
- When referencing a backlog item in a commit message, PR, or comment, always use its ID (e.g. "fixes BUG-001")
- New items are appended at the bottom of their category table; do not insert mid-table to avoid ID churn
- Backlog files are gitignored — they are local working documents, not public artefacts

## CI / Forgejo Actions Efficiency

**Structure rules — one workflow file per concern, jobs grouped by language:**
- Fold lint + test + security audit into a single job per language (`python`, `javascript`)
  — do NOT create a separate `security.yml`; bake pip-audit/npm-audit into the CI jobs
- Docker build/push only on `push` to `main`
  (`if: github.event_name == 'push' && github.ref == 'refs/heads/main'`)
- Secret scanning (gitleaks) may be its own lightweight job but stays in the same workflow file
- **`gitleaks/gitleaks-action@v2` is NOT available on `data.forgejo.org`** — install the binary directly:
  ```yaml
  - name: Install gitleaks
    run: |
      curl -sSfL https://github.com/gitleaks/gitleaks/releases/download/v8.27.2/gitleaks_8.27.2_linux_x64.tar.gz \
        | tar -xz -C /usr/local/bin gitleaks
  - name: gitleaks
    run: gitleaks detect --source . --log-opts "origin/main..HEAD" --redact -v
  ```

**Every workflow must include a concurrency block to cancel stale runs:**
```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

**Always cache package managers:**
- Python: `cache: pip` + `cache-dependency-path: backend/requirements.txt` in `actions/setup-python`
- Node: `cache: npm` + `cache-dependency-path: frontend/package-lock.json` in `actions/setup-node`

**Do not create a scheduled cron for security scans** — it runs on every PR already.

**Target job count:** ≤ 4 jobs per workflow trigger (python, javascript, secret-scan, docker).

**Self-hosted runner disk hygiene — prune dangling images after every successful push:**
```yaml
- name: Prune dangling images
  if: success()
  run: docker image prune -f
```

**`docker/metadata-action` tag generation — use explicit ref, not template:**

`enable={{is_default_branch}}` does **not** resolve in Forgejo Actions. Always use the explicit form:
```yaml
tags: |
  type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}
  type=sha,prefix=sha-,format=short
```

Add a step to compute the short SHA and pass it as a build arg:
```yaml
- name: Get short SHA
  id: sha
  run: echo "short=$(echo ${{ github.sha }} | head -c7)" >> $GITHUB_OUTPUT

- name: Build and push
  uses: docker/build-push-action@v6
  with:
    build-args: APP_VERSION=${{ steps.sha.outputs.short }}
```

**CI workflow path hygiene:** when deleting a module, directory, or package, immediately update all CI workflow references to it (`ruff check`, `bandit -r`, `--cov=`, etc.).

## Forgejo Docker Registry

The registry is served over HTTPS at `forgejo.moseisley.es` — standard `docker/login-action` works fine.

**Login:**
```yaml
- name: Log in to Forgejo registry
  uses: docker/login-action@v3
  with:
    registry: forgejo.moseisley.es
    username: ${{ github.actor }}
    password: ${{ secrets.FORGEJO_TOKEN }}
```

**Image naming:** `forgejo.moseisley.es/wind/networkcrawler`

**Tags — use explicit ref:**
```yaml
- name: Generate Docker image tags
  id: meta
  uses: docker/metadata-action@v5
  with:
    images: forgejo.moseisley.es/wind/networkcrawler
    tags: |
      type=raw,value=latest,enable=${{ github.ref == 'refs/heads/main' }}
      type=sha,prefix=sha-,format=short
```

**`GITHUB_TOKEN` does NOT have package registry write access in Forgejo Actions** — create a Forgejo PAT with `package` scope (Forgejo → Settings → Applications → Generate Token) and store it as repo secret `FORGEJO_TOKEN`.

**Forgejo Actions API:**
- `GET /api/v1/repos/{owner}/{repo}/actions/tasks` — lists runs/jobs (works)
- `GET /api/v1/repos/{owner}/{repo}/actions/runs` — returns **404** on current Forgejo versions; do not use

## Forgejo Debugging

**MCP `mcp__forgejo__actions_run_read` — broken methods (all return 404):**
- `list_runs`, `list_jobs`, `list_workflows`, `get_job_log_preview` — do NOT attempt these

**Working approach to inspect CI:**
1. Runner logs: `ssh root@192.168.1.110 "docker logs forgejo-runner 2>&1 | tail -50"`
2. Task status via curl:
   ```bash
   curl -s "https://forgejo.moseisley.es/api/v1/repos/Wind/NetworkCrawler/actions/tasks" \
     -H "Authorization: Bearer $TOKEN"
   ```
3. Container registry packages:
   ```bash
   curl -s "https://forgejo.moseisley.es/api/v1/packages/Wind?type=container&limit=20" \
     -H "Authorization: Bearer $TOKEN"
   ```

**Generating a temporary scoped API token:**
```bash
ssh root@192.168.1.110 "docker exec -u git Forgejo forgejo admin user generate-access-token \
  --username Wind --token-name debug-tmp --raw --scopes read:repository,read:package"
```
- Container name is `Forgejo` (capital F)
- Must use `-u git` — running as root fails
- Delete temporary tokens after use via Forgejo UI → Settings → Applications

## Docker Best Practices

**HEALTHCHECK — use `curl`, not `python3`:**
- The current Dockerfile uses `python3 -c "import urllib.request; ..."` — this spawns a full interpreter every 30 s causing constant CPU spikes. Replace with `curl`:
  ```dockerfile
  RUN apt-get install -y --no-install-recommends curl  # add to existing apt layer
  HEALTHCHECK --interval=60s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/health > /dev/null || exit 1
  ```
- Mirror the same check in `docker/docker-compose.yml`

**OCI image labels — use Forgejo source URL, not GitHub:**
```dockerfile
LABEL org.opencontainers.image.source="https://forgejo.moseisley.es/Wind/NetworkCrawler"
```
Remove all `hub.docker.com` references from labels.

**CI smoke tests on self-hosted runners — use `docker exec`, not `-p HOST:CONTAINER`:**
```yaml
- name: Smoke test
  run: |
    IMAGE=$(echo "${{ steps.meta.outputs.tags }}" | head -1)
    docker rm -f app-ci 2>/dev/null || true
    docker run -d --rm --name app-ci -e APP_DATA_DIR=/tmp "$IMAGE"
    for i in $(seq 1 30); do
      docker exec app-ci curl -sf http://localhost:8000/health \
        2>/dev/null && echo "Health OK" && break
      [ "$i" -eq 30 ] && { docker logs app-ci; docker stop app-ci; exit 1; }
      sleep 1
    done
    docker stop app-ci
```

## Git Conventions
- Branch prefixes: `feature/`, `fix/`, `chore/`, `docs/`, `release/`
- Commits: conventional commits (`feat:`, `fix:`, `chore:`, `test:`, `docs:`, `release:`)
- PRs require CI green before merge
- `main` branch = deployable state at all times
- When creating Forgejo issues, reference them in commits by ID
- **Never push to a branch after its PR is open** — if the PR is already merged, create a new branch from `origin/main`, cherry-pick, and open a new PR

**Remote:**
- `origin` → `forgejo:Wind/NetworkCrawler.git` — uses the `forgejo` SSH alias in `~/.ssh/config` (resolves to `192.168.1.110:1022`)
- Always use the alias form — never the raw `ssh://git@192.168.1.110:1022/` URL

**Forgejo API / issue management:**
- Use `mcp__forgejo__*` MCP tools — authenticate via configured token automatically
- For curl-based API calls in CI: `Authorization: Bearer $FORGEJO_TOKEN` where `FORGEJO_TOKEN` is a PAT with `package` + `repo` scopes stored as a repo secret

## Local Pre-Push Checks

CI failures are expensive to fix once a PR is open. Mirror all CI gates locally.

**Install the hook once per clone:**
```bash
git config core.hooksPath .githooks
```

**`.githooks/pre-push`** (commit this file; `chmod +x .githooks/pre-push`):
```bash
#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# 1. Python lint
python -m ruff check backend/

# 2. Python tests + coverage gate
python -m pytest backend/tests/ --cov=app --cov-fail-under=80 -q --tb=short

# 3. Frontend lint
(cd frontend && npm run lint --silent)

# 4. TypeScript type errors
(cd frontend && npx tsc -b --noEmit)

echo "All checks passed — push allowed."
```

**Claude Code hook** — add to `.claude/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "input=$(cat); cmd=$(echo \"$input\" | jq -r '.tool_input.command // \"\"'); echo \"$cmd\" | grep -qE 'git (commit|push)' || exit 0; echo \"$cmd\" | grep -q 'git push' && bash .githooks/pre-push || ruff check backend/",
            "statusMessage": "Running pre-push checks (ruff + pytest + eslint + tsc)..."
          }
        ]
      }
    ]
  }
}
```

## Parallel Agents
Multiple Claude agents may work on this repo simultaneously on separate branches. To avoid cross-contamination:
- Before fixing any CI failure, run `git diff main...HEAD -- <file>` to confirm the offending code is within your branch's diff
- If the failure is in a file you did not touch (introduced by another agent on main), do NOT fix it in the current branch — create a separate `fix/` branch targeting main and open its own PR
- Each branch/PR must own only the changes scoped to its issue; never absorb unrelated fixes to make CI green

## Domain Knowledge

### Network Topology
```
Fiber ISP (bridge mode)
  └─ Flint 2 router (LAN gateway, DHCP server)
       ├─ WiFi clients
       └─ 2.5 GB wired port
            └─ 2.5 GB switch
                 ├─ Tower  (Unraid server — 192.168.1.110)
                 └─ Fijo   (workstation)
```

### Why Host Networking + NET_RAW
- ARP broadcast discovery (`arp-scan`) only works when the scanning process is on the same L2 segment as targets
- Host networking places the container directly on the LAN interface — without it, ARP traffic is invisible
- `nmap` and `arp-scan` require raw socket access (NET_RAW) to send/receive crafted packets as non-root
- These are not workarounds; they are hard requirements of the scanning technique

### Scan Pipeline
1. `arp-scan` — enumerates all live hosts on the subnet (L2 discovery, fast)
2. `nmap` — port scan + OS fingerprint on discovered hosts
3. DNS reverse lookup — resolves hostnames for discovered IPs
4. OS inference — combines nmap output + MAC OUI to classify device type
5. Risk scoring — evaluates open ports, firmware age, known CVEs against device profile
6. Recommendations — generates actionable suggestions per device based on risk findings

### Device Trust Model
- Devices are classified as `trusted` (bool) by the operator
- Untrusted devices with open sensitive ports receive higher risk scores
- Trust state persists in SQLite and survives container restarts

### Database Migrations
- Schema changes are applied via `_migrate_schema()` in `backend/app/db.py` using raw `ALTER TABLE ADD COLUMN IF NOT EXISTS`
- No Alembic — migrations are additive-only; columns are never dropped or renamed
- New columns must have a DEFAULT value so existing rows stay valid
