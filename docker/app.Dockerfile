# syntax=docker/dockerfile:1.7
# ---------- Stage 1: builder ----------
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
      curl \
      && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only dependency-relevant files for better layer caching.
COPY pyproject.toml README.md /app/
COPY src /app/src

RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip wheel \
 && /opt/venv/bin/pip install .

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq5 \
      tini \
      && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --home /app --shell /sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

WORKDIR /app
USER app:app

# Sensible default; each service overrides via `command:` in compose/k8s.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["admin-api"]
