# NetworkCrawler — Multi-stage Dockerfile
#
# Stage 1: build the React frontend
# Stage 2: production image serving both FastAPI + static frontend assets
#
# Security: container runs as non-root user (uid 1000)
# Network:  requires host network mode + --cap-add=NET_RAW for arp-scan/nmap

# ── Stage 1: frontend build ────────────────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline

COPY frontend/ ./
RUN npm run build
# Output: /build/frontend/dist

# ── Stage 2: production image ─────────────────────────────────────────────
FROM python:3.11-slim AS production

# Install system dependencies (nmap, arp-scan)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    arp-scan \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r crawler && useradd -r -g crawler -u 1000 crawler

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend static assets
COPY --from=frontend-build /build/frontend/dist ./frontend/dist

# Set ownership
RUN chown -R crawler:crawler /app

USER crawler

EXPOSE 8000

# Note: nmap/arp-scan need NET_RAW capability — add via docker-compose or --cap-add=NET_RAW
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
