# ── Stage 1: build dependencies ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY app/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="I-love-geekos Marketplace"
LABEL org.opencontainers.image.description="Demo marketplace app for SUSECon 2026"
LABEL org.opencontainers.image.source="https://github.com/rossella/susecon26-demo"

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app
COPY app/ .

# Persistent volume mount point
RUN mkdir -p /data

# Unprivileged user
RUN useradd --no-create-home --uid 1000 geeko
RUN chown geeko:geeko /data /app
USER geeko

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STORAGE_BACKEND=file \
    DATA_DIR=/data \
    PORT=5000

EXPOSE 5000

# Use gunicorn for production; fall back to flask dev server with FLASK_DEBUG=true
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "2", "app:app"]
