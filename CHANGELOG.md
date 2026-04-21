# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial monorepo layout with four Telegram bot services
  (`wb_bot`, `ozon_bot`, `task_planner_bot`, `network_bot`) plus an
  `admin_api` (FastAPI) and a `worker` (Celery) service.
- `helpers_core` shared library with configuration, logging, security
  (Fernet key rotation + `EncryptedString` SQLAlchemy type), async DB layer,
  HTTP client with retries and circuit-breaking, typed Wildberries and Ozon
  API clients, Telegram middlewares (DB / throttling / errors / logging),
  Celery application factory, Prometheus telemetry and domain models.
- Docker multi-stage image, docker-compose for local stack
  (Postgres, Redis, RabbitMQ, Prometheus, Grafana) and GitLab CI pipeline.
- Alembic async migrations.
- pytest / ruff / mypy strict quality gates.

### Security

- Symmetric encryption of marketplace API tokens via Fernet, configured
  through the `FERNET_KEYS` environment variable with `MultiFernet` for
  zero-downtime key rotation.

### Infrastructure

- Bot tokens and all other secrets are loaded from the environment via
  typed Pydantic settings — no values are embedded in the source tree.
- Async SQLAlchemy engine uses `AsyncAdaptedQueuePool` with configurable
  sizing and `pool_pre_ping` for resilience under load.
