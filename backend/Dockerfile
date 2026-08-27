# syntax=docker/dockerfile:1.6
# ====================================================================
# Automatic Video Dubbing Engine — backend image
# Python 3.11 + FFmpeg + all dubbing dependencies (CPU-only friendly).
# ====================================================================
FROM python:3.11-slim AS base

# --- System packages: ffmpeg + fonts (for any drawtext) + ca-certs ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python dependencies (cached layer) ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Application code ---
COPY app/ ./app/
COPY run.py ./
COPY .env.example ./

# Storage lives outside the app code so it can be a volume.
RUN mkdir -p /app/storage/jobs

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=8000 \
    STORAGE_DIR=/app/storage

EXPOSE 8000

# Healthcheck hits the /api/health endpoint.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -fs http://localhost:8000/api/health || exit 1

CMD ["python3", "run.py"]
