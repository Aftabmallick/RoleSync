# syntax=docker/dockerfile:1.4
FROM python:3.12-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Build Stage: Download and unpack verified Typst standalone binary
FROM base AS typst-builder
RUN apt-get update && apt-get install -y --no-install-recommends curl tar ca-certificates xz-utils && \
    curl -fsSL https://github.com/typst/typst/releases/download/v0.11.1/typst-x86_64-unknown-linux-musl.tar.xz | \
    tar -xJ --strip-components=1 -C /usr/local/bin typst-x86_64-unknown-linux-musl/typst && \
    chmod +x /usr/local/bin/typst

# Application Runtime Stage
FROM base AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    fonts-liberation \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=typst-builder /usr/local/bin/typst /usr/local/bin/typst

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Dedicated non-root application user for unprivileged execution
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

