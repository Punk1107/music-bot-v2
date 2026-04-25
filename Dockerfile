# ── Music Bot V2 — Dockerfile ─────────────────────────────────────────────────
# P4-3: Containerisation-ready build
#
# Build:  docker build -t musicbot-v2 .
# Run:    docker run --env-file .env musicbot-v2
# Or use: docker compose up

FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────────────────
# FFmpeg is required for audio encoding/decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Create non-root user for security ────────────────────────────────────────
RUN useradd --create-home --shell /bin/bash botuser

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────────────────
COPY --chown=botuser:botuser . .

# ── Create writable directories ───────────────────────────────────────────────
RUN mkdir -p data logs && chown -R botuser:botuser data logs

# ── Switch to non-root user ───────────────────────────────────────────────────
USER botuser

# ── Health check (for Docker / Render / Railway) ─────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# ── Entrypoint ────────────────────────────────────────────────────────────────
CMD ["python", "main.py"]
