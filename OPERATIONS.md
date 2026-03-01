# NetworkCrawler — Operations Guide

Backup, restore, upgrade, and maintenance procedures for self-hosted deployments.

---

## Table of Contents

1. [Data Locations](#data-locations)
2. [Backup](#backup)
3. [Restore](#restore)
4. [Upgrade](#upgrade)
5. [Configuration Reference](#configuration-reference)
6. [Logs and Troubleshooting](#logs-and-troubleshooting)
7. [Uninstall](#uninstall)

---

## Data Locations

All persistent data lives in a single Docker named volume:

| Path inside container | Description                        |
|-----------------------|------------------------------------|
| `/app/data/networkcrawler.db` | SQLite database — scan history, devices, risks, recommendations |

The named volume is `networkcrawler_data` (created automatically by `docker compose`).

On the Docker host the volume data is stored at:

```
/var/lib/docker/volumes/networkcrawler_data/_data/
```

> **Note:** Never write directly to this directory while the container is running.

---

## Backup

### Quick backup (recommended)

Copy the SQLite database out of the running container:

```bash
docker cp networkcrawler:/app/data/networkcrawler.db ./networkcrawler-$(date +%Y%m%d).db
```

### SQLite online backup (zero downtime)

Using SQLite's `.backup` command ensures a consistent snapshot even while the container is running:

```bash
docker exec networkcrawler \
  sqlite3 /app/data/networkcrawler.db ".backup /tmp/backup.db"
docker cp networkcrawler:/tmp/backup.db ./networkcrawler-$(date +%Y%m%d).db
```

### Volume snapshot

To back up the entire named volume:

```bash
docker run --rm \
  -v networkcrawler_data:/data \
  -v "$(pwd)":/backup \
  alpine tar czf /backup/networkcrawler-volume-$(date +%Y%m%d).tar.gz -C /data .
```

### Automation

Add a cron job on the Docker host to run one of the above commands daily:

```cron
0 3 * * * docker cp networkcrawler:/app/data/networkcrawler.db /backups/networkcrawler-$(date +\%Y\%m\%d).db
```

---

## Restore

1. **Stop the container** to avoid write conflicts:

   ```bash
   docker compose -f docker/docker-compose.yml down
   ```

2. **Copy the backup database** into the volume:

   ```bash
   # Start a temporary helper container to write to the volume
   docker run --rm \
     -v networkcrawler_data:/data \
     -v "$(pwd)":/backup \
     alpine cp /backup/networkcrawler-20240101.db /data/networkcrawler.db
   ```

3. **Restart the container**:

   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```

4. **Verify** the database loaded correctly by opening the UI at `http://<host-ip>:8000`.

---

## Upgrade

NetworkCrawler uses automatic schema migration on startup — new columns are added via `ALTER TABLE` if they are missing from an existing database. No manual SQL is required.

### Upgrade steps

1. **Pull the latest image**:

   ```bash
   docker compose -f docker/docker-compose.yml pull
   ```

2. **Recreate the container** (data volume is preserved):

   ```bash
   docker compose -f docker/docker-compose.yml up -d --force-recreate
   ```

3. **Check startup logs** for any migration or error messages:

   ```bash
   docker compose -f docker/docker-compose.yml logs --tail=50 networkcrawler
   ```

### Pinning to a specific version

Set the `IMAGE_TAG` environment variable before starting:

```bash
IMAGE_TAG=sha-abc1234 docker compose -f docker/docker-compose.yml up -d
```

Available tags are listed on the [Docker Hub page](https://hub.docker.com/r/talesofthemoon/networkcrawler/tags).

### Rolling back

1. Stop the container.
2. Restore a backup taken before the upgrade (see [Restore](#restore)).
3. Start the container with the previous image tag:

   ```bash
   IMAGE_TAG=sha-<previous-sha> docker compose -f docker/docker-compose.yml up -d
   ```

---

## Configuration Reference

All configuration is supplied via environment variables. Copy `.env.example` to `.env` and edit before first run.

| Variable | Default | Description |
|---|---|---|
| `NETWORK_INTERFACE` | `eth0` | Host NIC used for ARP scan |
| `SCAN_SUBNET` | `192.168.1.0/24` | CIDR subnet to scan |
| `SCAN_INTERVAL_SECONDS` | `3600` | Seconds between scheduled scans (0 = disable) |
| `LOG_LEVEL` | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `DATABASE_URL` | `sqlite:////app/data/networkcrawler.db` | SQLAlchemy database URL (do not change for standard deployments) |

> **Security:** Never commit `.env` to source control. It is in `.gitignore` by default.

---

## Logs and Troubleshooting

### View live logs

```bash
docker compose -f docker/docker-compose.yml logs -f networkcrawler
```

### Common issues

| Symptom | Likely cause | Fix |
|---|---|---|
| Scan finds 0 devices | Wrong `NETWORK_INTERFACE` or `SCAN_SUBNET` | Confirm interface with `ip addr`; update `.env` |
| Container exits immediately | Missing `NET_RAW` capability | Ensure `cap_add: [NET_RAW]` in compose file |
| UI shows "Scan failed" | nmap not found in container or timed out | Check logs; rebuild image with `docker compose build` |
| Database locked error | Two containers writing to the same volume | Ensure only one container runs at a time |
| Avahi/mDNS not resolving | `avahi-daemon` not running on the host | Start `avahi-daemon` on the Docker host |

### Health check

The container exposes a health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response: `{"status": "ok"}`

---

## Uninstall

To remove NetworkCrawler completely, including all scan data:

```bash
# Stop and remove the container
docker compose -f docker/docker-compose.yml down

# Remove the data volume (IRREVERSIBLE — back up first!)
docker volume rm networkcrawler_data

# Remove the image
docker rmi talesofthemoon/networkcrawler:latest
```

To keep your scan history, back up the database before running these commands.
