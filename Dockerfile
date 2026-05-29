# ── Stage 1: Build frontend ──
FROM node:20-slim AS frontend

WORKDIR /build
COPY web/frontend/package.json web/frontend/package-lock.json ./web/frontend/
RUN cd web/frontend && npm ci --no-audit --no-fund
COPY web/frontend/ ./web/frontend/
RUN cd web/frontend && npm run build

# ── Stage 2: Python runtime (slim — no local embedding) ──
FROM python:3.12-slim AS slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (cache-friendly: only re-runs when pyproject.toml changes)
COPY pyproject.toml ./
COPY kb_studio/__init__.py ./kb_studio/__init__.py
RUN pip install --no-cache-dir . || true

# Copy full source and install
COPY kb_studio/ ./kb_studio/
RUN pip install --no-cache-dir .

# Copy built frontend from Stage 1
COPY --from=frontend /build/web/frontend/dist/ ./web/frontend/dist/

# Default config (override via volume mount at /app/config/)
COPY config/active.example.yaml ./config/active.yaml

# Persistent data directory (mount at /app/data/)
RUN mkdir -p ./data

EXPOSE 8000

# Mount volumes: /app/config (LLM config), /app/data (knowledge bases)
ENTRYPOINT ["kb-studio", "serve"]
CMD ["--port", "8000"]

# ── Stage 3: Full image (local embedding + Claude) ──
# Build with: docker build --target full -t kb-studio:full .
FROM slim AS full

RUN pip install --no-cache-dir ".[all]"
