# NetworkCrawler — Multi-stage Dockerfile
#
# Stage 1 — frontend build (Node): compiles the React/Vite app to static assets.
# Stage 2 — production image (Python slim): runs FastAPI and serves frontend assets.
#
# Security notes:
#   • Container runs as a non-root user (uid/gid 1000).
#   • Raw socket access for nmap/arp-scan is granted via --cap-add=NET_RAW at
#     runtime (see docker-compose.yml). Do NOT run the container as root.
#   • Host network mode is required so arp-scan can reach the LAN broadcast domain.

# ── Stage 1: build the React frontend ────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /build

COPY frontend/package.json frontend/package-lock.json* ./
# ci install — deterministic, skips devDep postinstall scripts on prod
RUN npm ci --prefer-offline

COPY frontend/ ./
RUN npm run build
# Outputs compiled assets to /build/dist


# ── Stage 2: production runtime ──────────────────────────────────────────────
FROM python:3.11-slim AS production

LABEL org.opencontainers.image.title="NetworkCrawler" \
      org.opencontainers.image.description="LAN security posture scanner for home lab operators" \
      org.opencontainers.image.source="https://github.com/reloadfast/NetworkCrawler"

# Install system-level scanning tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nmap \
        arp-scan \
    && rm -rf /var/lib/apt/lists/*

# Create a dedicated non-root user
RUN groupadd --gid 1000 crawler \
    && useradd --uid 1000 --gid crawler --no-create-home --shell /usr/sbin/nologin crawler

WORKDIR /app

# Install Python dependencies before copying source (layer-cache friendly)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY backend/ ./backend/

# Copy compiled frontend assets — served as static files by FastAPI
COPY --from=frontend-build /build/dist ./frontend/dist

# Persist the SQLite database in a dedicated data directory
RUN mkdir -p /app/data && chown -R crawler:crawler /app

# Drop to non-root
USER crawler

# FastAPI listens on 8000; the host-network container is accessible on <host-ip>:8000
EXPOSE 8000

# Healthcheck — lightweight; used by Docker and Compose
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "backend.app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
