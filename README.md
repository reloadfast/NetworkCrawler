# NetworkCrawler

A local-first LAN security posture scanner for home lab operators and self-hosters.

NetworkCrawler discovers every device on your network, checks for common misconfigurations (open Telnet, unencrypted admin interfaces, default-credential risks, exposed SMB/UPnP), and delivers actionable, per-device hardening recommendations — all running entirely within your LAN, with no cloud connectivity or external telemetry of any kind.

---

## Features

- **Automatic LAN discovery** — ARP scan + nmap identify all live hosts, open ports, and service versions
- **Risk detection** — four-tier severity model (critical / high / medium / low) across common home-network misconfigurations
- **Hardening recommendations** — step-by-step guidance with effort and impact scores, per device
- **Persistent history** — SQLite database retains scan history across restarts
- **Dark/light theme UI** — modern dashboard built with React + Tailwind
- **Scheduled scanning** — configurable background scans; manual re-scan on demand
- **Privacy by design** — nothing leaves your LAN

---

## Quickstart

### Prerequisites

- Docker (with Compose v2)
- Container host must be connected to the LAN you want to scan

### Pull and run

```bash
# 1. Copy and edit the environment file
cp .env.example .env
$EDITOR .env            # set NETWORK_INTERFACE and SCAN_SUBNET at minimum

# 2. Start the container
docker compose -f docker/docker-compose.yml up -d

# 3. Open the UI
open http://localhost:8000
```

The container uses **host network mode** so arp-scan can reach the LAN broadcast domain; the app is reachable on `http://<host-ip>:8000` from any device on the same network.

### Build from source

```bash
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up -d
```

---

## Environment Variables

Copy `.env.example` to `.env` and adjust as needed.

| Variable | Default | Required | Description |
|---|---|---|---|
| `NETWORK_INTERFACE` | `eth0` | Yes | Host network interface arp-scan listens on. Run `ip link` to find yours (common: `eth0`, `bond0`, `br0`, `ens18`). |
| `SCAN_SUBNET` | `192.168.1.0/24` | Yes | CIDR subnet to scan. Must match your LAN (e.g. `10.0.0.0/24`). |
| `SCAN_INTERVAL_SECONDS` | `3600` | No | Background scan frequency in seconds. Minimum recommended: `300`. |
| `LOG_LEVEL` | `INFO` | No | Logging verbosity: `DEBUG` \| `INFO` \| `WARNING` \| `ERROR`. Use `DEBUG` to troubleshoot scan issues. |

`DATABASE_URL` is wired automatically by the container to `/app/data/networkcrawler.db` — do not override it unless you know what you are doing.

---

## Ports and Network

| Port | Protocol | Purpose |
|---|---|---|
| `8000` | TCP | FastAPI backend + React UI (served as static files) |

The container runs with `network_mode: host` — no port mapping is needed. Access the UI at `http://<host-ip>:8000`.

**Required capabilities:** `--cap-add=NET_RAW` — grants raw socket access for arp-scan and nmap. The container still runs as a non-root user (uid 1000).

### Data persistence

Scan history and device inventory are stored in a SQLite database inside the `/app/data` volume:

```
networkcrawler_data:/app/data   (named Docker volume, survives upgrades)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                Home LAN (trusted boundary)           │
│                                                     │
│  ┌──────────────┐   HTTP/REST    ┌───────────────┐  │
│  │  Browser     │◄──────────────►│  FastAPI      │  │
│  │  React UI    │   :8000/api    │  Backend      │  │
│  └──────────────┘                │               │  │
│                                  │  ┌─────────┐  │  │
│                                  │  │ SQLite  │  │  │
│                                  │  └─────────┘  │  │
│                                  │               │  │
│                                  │  ┌─────────┐  │  │
│                                  │  │ Scanner │  │  │
│                                  │  │(arp +   │  │  │
│                                  │  │ nmap)   │  │  │
│                                  │  └────┬────┘  │  │
│                                  └───────┼───────┘  │
│                                          │           │
│        LAN devices ◄─────────────────────┘           │
│        (ARP + port scan, read-only)                  │
└─────────────────────────────────────────────────────┘

Single container — frontend static assets served by FastAPI.
Host network mode — container sees the full LAN broadcast domain.
```

---

## Project Structure

```
NetworkCrawler/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI entrypoint, scheduler
│   │   ├── api/                  # REST route handlers
│   │   ├── scanner/              # arp-scan + nmap integration
│   │   ├── analysis/             # Risk detection engine
│   │   ├── recommendations/      # Hardening advice engine
│   │   ├── models/               # SQLAlchemy ORM models
│   │   └── db.py                 # DB connection + init
│   ├── tests/                    # Pytest suite
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/           # Reusable UI (Card, Badge, ProgressBar, Chart)
│   │   ├── pages/                # Dashboard, Devices, Risks, Recommendations
│   │   ├── hooks/                # Data-fetching hooks
│   │   └── styles/               # CSS variable theme tokens
│   ├── tests/                    # Vitest suite
│   └── package.json
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example
└── CONTRIBUTING.md
```

---

## Operations

Backup, restore, upgrade, and troubleshooting procedures are documented in [OPERATIONS.md](OPERATIONS.md).

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT
