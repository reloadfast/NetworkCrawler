# Contributing to NetworkCrawler

Thanks for taking the time to contribute. This document covers everything you need to get from idea to merged PR.

---

## Table of Contents

1. [Branch conventions](#branch-conventions)
2. [Commit style](#commit-style)
3. [Development setup](#development-setup)
4. [Running tests](#running-tests)
5. [PR checklist](#pr-checklist)

---

## Branch conventions

| Prefix | Use for |
|---|---|
| `feature/` | New functionality |
| `fix/` | Bug fixes |
| `chore/` | Build, CI, deps, tooling (no production code change) |
| `docs/` | Documentation only |

Name branches descriptively after the issue or change:

```
feature/phase2-arp-scanner
fix/nmap-xml-parse-timeout
docs/update-contributing
```

`main` is the deployable branch. Direct pushes to `main` are blocked; all changes must go through a PR.

---

## Commit style

This project follows [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<scope>): <short description>

[optional body]

[optional footer(s)]
```

### Types

| Type | When to use |
|---|---|
| `feat` | New feature or user-visible behaviour |
| `fix` | Bug fix |
| `chore` | Build, CI, dependency updates, tooling |
| `test` | Adding or updating tests only |
| `docs` | Documentation only |
| `refactor` | Code restructuring with no behaviour change |
| `perf` | Performance improvement |
| `style` | Formatting, whitespace (no logic change) |

### Scope (optional)

Use the affected area: `backend`, `frontend`, `scanner`, `analysis`, `docker`, `ci`, etc.

### Examples

```
feat(scanner): add OS detection via nmap -O flag
fix(frontend): correct severity badge colour for medium risks
chore(deps): bump fastapi to 0.111.0
test(analysis): add unit tests for SMB misconfiguration check
docs: add CONTRIBUTING.md
```

### Closing issues

Reference issues in the commit footer when the change resolves them:

```
feat(recommendations): implement per-device hardening advice engine

Closes #12
```

---

## Development setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # if present; otherwise: pip install pytest pytest-cov ruff
```

### Frontend

```bash
cd frontend
npm ci
```

### Environment

```bash
cp .env.example .env
# Edit .env: set NETWORK_INTERFACE and SCAN_SUBNET to match your LAN
```

### Run locally (without Docker)

```bash
# Terminal 1 — backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend dev server
cd frontend
npm run dev          # proxies /api → localhost:8000
```

### Run with Docker Compose

```bash
docker compose -f docker/docker-compose.yml up --build
```

---

## Running tests

All tests must pass before a PR can merge.

### Backend

```bash
cd backend
pytest -v --cov=app --cov-report=term-missing
```

- Coverage target: **≥ 80% line coverage**
- Use markers: `@pytest.mark.unit` and `@pytest.mark.integration`
- Scanner integration tests must mock nmap/arp-scan output — **never run live scans in CI**

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Frontend

```bash
cd frontend
npm test               # Vitest watch mode
npm run test:coverage  # coverage report
```

- Key components and data-fetching hooks must have test coverage

### Linting

```bash
# Python
cd backend && ruff check .

# TypeScript/JS
cd frontend && npm run lint
```

### Security scans

```bash
pip-audit          # Python dependencies
npm audit          # JS dependencies
```

CI fails on any HIGH severity finding.

---

## PR checklist

Before marking your PR ready for review, confirm all of the following:

**Code**
- [ ] All existing tests pass (`pytest` / `npm test`)
- [ ] New code has tests; coverage does not drop below 80% for the backend
- [ ] No `# noqa` or `// eslint-disable` without an inline justification comment
- [ ] No hardcoded secrets, credentials, or environment-specific values

**Linting and security**
- [ ] `ruff check .` passes in `backend/`
- [ ] `npm run lint` passes in `frontend/`
- [ ] `pip-audit` and `npm audit` report no HIGH severity CVEs

**Scope**
- [ ] PR addresses exactly one issue / feature; unrelated changes are in separate PRs
- [ ] Branch is rebased onto (or merged from) `main` and has no unrelated diff
- [ ] Commit messages follow Conventional Commits format

**Documentation**
- [ ] `README.md` updated if ports, env vars, or quickstart steps changed
- [ ] `.env.example` updated if new environment variables were added

**Infrastructure** *(when ports, env vars, or volumes changed)*
- [ ] `docker/docker-compose.yml` env block is in sync with `.env.example`
- [ ] The Unraid template has been updated locally to match (ports, env vars, volume mounts)

---

## Code of conduct

Be respectful. Constructive feedback only. This is a home-lab project — keep it fun.
