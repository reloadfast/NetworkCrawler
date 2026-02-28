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
      org.opencontainers.image.source="https://github.com/reloadfast/NetworkCrawler" \
      org.opencontainers.image.url="https://hub.docker.com/r/talesofthemoon/networkcrawler" \
      org.opencontainers.image.vendor="talesofthemoon" \
      org.opencontainers.image.licenses="MIT"

# Install system-level scanning tools + libcap2-bin for setcap
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nmap \
        arp-scan \
        libcap2-bin \
    && rm -rf /var/lib/apt/lists/*

# Grant cap_net_raw to the scanner binaries so they can open raw sockets when
# running as non-root uid 1000.  --cap-add=NET_RAW at runtime puts NET_RAW in
# the bounding set; setcap +ep promotes it to the effective set on exec.
RUN setcap cap_net_raw+ep /usr/sbin/arp-scan \
    && setcap cap_net_raw+ep "$(which nmap)"

# Create a dedicated non-root user
RUN groupadd --gid 1000 crawler \
    && useradd --uid 1000 --gid crawler --no-create-home --shell /usr/sbin/nologin crawler

WORKDIR /app

# backend/ is the Python root — app.main, app.db, etc. are top-level packages
ENV PYTHONPATH=/app/backend

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

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
