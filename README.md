# Helpers Platform

[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Style: Ruff](https://img.shields.io/badge/style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type checked: mypy](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy.readthedocs.io/)

**Helpers Platform** is a production-grade, opinionated monorepo that bundles several asynchronous Telegram bots and a management HTTP API on top of a single shared core library.

It ships a strictly-typed, reusable core (`helpers_core`) that backs every service — marketplace API clients, encryption, subscription checks, task planning and scheduling — so each bot stays thin and focused on its own business logic.

## What's inside

| Service              | Description                                                                 | Entry point         |
| -------------------- | --------------------------------------------------------------------------- | ------------------- |
| `wb_bot`             | Telegram bot for Wildberries sellers (reports, bidder, reviews, notifications) | `wb-bot`            |
| `ozon_bot`           | Telegram bot for Ozon sellers (reports, bidder, reviews, notifications)     | `ozon-bot`          |
| `task_planner_bot`   | Standalone Telegram task reminder bot                                       | `task-planner-bot`  |
| `network_bot`        | Networking / admin Telegram bot                                             | `network-bot`       |
| `admin_api`          | FastAPI HTTP service: health, metrics, admin CRUD                           | `admin-api`         |
| `worker`             | Celery worker & beat: heavy scheduled jobs, report generation               | `helpers-worker`, `helpers-beat` |

All services share one installable library: [`helpers_core`](./src/helpers_core), which contains:

- Unified Pydantic-based configuration
- Async SQLAlchemy 2.x engine with `asyncpg` + `AsyncAdaptedQueuePool`
- `EncryptedString` SQLAlchemy type for transparent Fernet encryption of API tokens
- Typed aiohttp-based API clients for Wildberries and Ozon with retries, circuit breaker and Prometheus instrumentation
- Reusable aiogram middlewares (DB session, Redis throttling, structured logging, error reporting)
- Celery application factory (RabbitMQ broker, Redis result backend)
- structlog JSON logging with correlation IDs
- Prometheus metrics registry and default HTTP/DB/Celery instruments
- Domain models and repositories (Users, Magazines, Subscriptions, Tasks, …)

## Tech stack

- **Language / runtime**: Python 3.12, `asyncio`, `uvloop`, `orjson`
- **Bot framework**: `aiogram` 3.x
- **HTTP client**: `aiohttp` + `tenacity` (retries with jitter + circuit breaker)
- **Web API**: `FastAPI` + `uvicorn`
- **Validation / config**: `pydantic` 2.x + `pydantic-settings`
- **DB**: PostgreSQL 16, SQLAlchemy 2.x (async), `asyncpg`, Alembic
- **Queue / cache**: Redis 7 (FSM + throttling + result backend), RabbitMQ (Celery broker)
- **Background jobs**: Celery 5.x + Celery Beat
- **Observability**: `structlog`, `prometheus-client`, Grafana dashboards
- **Infrastructure**: Docker (multi-stage, non-root), docker-compose, GitLab CI/CD
- **Quality**: `ruff` (lint+format), `mypy --strict`, `pytest` + `pytest-asyncio`, `pre-commit`

## Architecture at a glance

```
                        ┌──────────────────────────┐
  Telegram Updates ───► │   wb_bot / ozon_bot /    │ ──► PostgreSQL  (asyncpg, pool)
                        │   task_planner_bot /     │ ──► Redis       (FSM + throttle + cache)
                        │   network_bot            │ ──► RabbitMQ    (Celery broker)
                        └────────────┬─────────────┘
                                     │   all import
                                     ▼
                        ┌──────────────────────────┐
                        │      helpers_core        │
                        │  (shared library: DB,    │
                        │  crypto, HTTP, WB/Ozon,  │
                        │  middlewares, telemetry) │
                        └────────────┬─────────────┘
                                     ▲
                                     │
                        ┌────────────┴─────────────┐
                        │        worker            │ ─────► Prometheus ─► Grafana
                        │  (Celery + Beat):        │
                        │  scheduled reports,      │
                        │  review polling, etc.    │
                        └──────────────────────────┘
                                     ▲
                                     │
                        ┌────────────┴─────────────┐
                        │        admin_api         │
                        │  (FastAPI: /healthz,     │
                        │  /metrics, admin CRUD)   │
                        └──────────────────────────┘
```

Detailed decisions are documented in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).

## Quick start (local, Docker)

```bash
# 1. Create .env from template and fill in secrets
cp .env.example .env
# IMPORTANT: generate your own Fernet key (never commit it!)
python scripts/generate_fernet_key.py

# 2. Start full stack: postgres, redis, rabbitmq, prometheus, grafana, all bots + api
docker compose up -d --build

# 3. Apply database migrations
docker compose run --rm admin-api alembic upgrade head

# 4. Follow logs
docker compose logs -f wb-bot
```

- Grafana: <http://localhost:3000> (admin / admin — change immediately!)
- Prometheus: <http://localhost:9090>
- Admin API: <http://localhost:8000/docs>
- RabbitMQ: <http://localhost:15672> (guest / guest)

## Quick start (local, without Docker)

```bash
python -m venv .venv
# Windows:
.venv\Scripts\Activate.ps1
# Linux/macOS:
source .venv/bin/activate

pip install -U pip
pip install -e ".[dev]"

cp .env.example .env
python scripts/generate_fernet_key.py   # then put output into .env

alembic upgrade head

wb-bot             # or: ozon-bot / task-planner-bot / network-bot
admin-api          # FastAPI on :8000
helpers-worker     # Celery worker
helpers-beat       # Celery beat
```

## Project layout

```
helpers-platform/
├── src/
│   ├── helpers_core/          # Shared library (installable, typed)
│   ├── wb_bot/                # Wildberries Telegram bot
│   ├── ozon_bot/              # Ozon Telegram bot
│   ├── task_planner_bot/      # Task reminder bot
│   ├── network_bot/           # Networking bot
│   ├── admin_api/             # FastAPI management service
│   └── worker/                # Celery worker + beat
├── migrations/                # Alembic async migrations
├── monitoring/                # Prometheus + Grafana provisioning
├── docker/                    # Dockerfiles
├── scripts/                   # Operational scripts (key generation, DB wait, …)
├── tests/                     # pytest: unit + integration
├── docs/                      # ARCHITECTURE.md, ADRs
├── docker-compose.yml
├── pyproject.toml
├── alembic.ini
├── Makefile
├── .env.example
├── .gitlab-ci.yml
└── LICENSE
```

## Security

Please report vulnerabilities privately — see [`SECURITY.md`](./SECURITY.md). Never commit `.env` or any secret keys.

## Contributing

Contributions are very welcome. Please read [`CONTRIBUTING.md`](./CONTRIBUTING.md) before opening a PR.

## License

Distributed under the MIT License. See [`LICENSE`](./LICENSE) for details.
