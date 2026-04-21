# Architecture

This document describes the design choices behind **Helpers Platform**.
Read it alongside [`../README.md`](../README.md), which covers day-to-day
operations.

## High-level layout

```
┌─ src/ ─────────────────────────────────────────────┐
│                                                    │
│  helpers_core/     (the shared library)            │
│    config/         Pydantic settings               │
│    logging/        structlog + correlation-id      │
│    security/       Fernet MultiFernet (rotation)   │
│    db/             async engine, Base, custom      │
│                    EncryptedString column type     │
│    cache/          shared Redis client + Lua       │
│                    rate limiter                    │
│    http/           aiohttp facade + tenacity       │
│                    retries + circuit breaker       │
│    marketplaces/   typed WB / Ozon clients         │
│    telegram/       shared aiogram middlewares and  │
│                    a bot bundle factory            │
│    messaging/      Celery application factory      │
│    telemetry/      Prometheus registry & helpers   │
│    domain/         ORM models + repositories       │
│                                                    │
│  wb_bot, ozon_bot, task_planner_bot, network_bot   │
│                    aiogram entrypoints + handlers  │
│  admin_api        FastAPI (health + metrics +      │
│                    admin CRUD)                     │
│  worker           Celery worker / beat             │
│                                                    │
└────────────────────────────────────────────────────┘
```

## Key decisions

### Single shared library, multiple deployables

Cross-cutting concerns (DB access, encryption, subscription checks, task
planning, rate limiting, HTTP clients) live in one place — `helpers_core`.
One implementation, one set of tests, one deployment story; bug fixes
and security patches land in a single module and propagate to every
service automatically.

Each bot is a **separate service** with its own Telegram token and its
own Docker container, but they all import the same core library and
share the same Postgres, Redis and RabbitMQ instances.

### Strict config via Pydantic

`os.getenv` is forbidden outside `helpers_core/config/settings.py`. Every
value has a type, a default, and in many cases a validator — so the
process refuses to start if something critical is missing, instead of
crashing deep in a handler at 3 AM.

### Security baked in

* `FERNET_KEYS` env var with `MultiFernet` for zero-downtime rotation
  of the symmetric key used to encrypt marketplace API tokens.
* `EncryptedString` SQLAlchemy column type handles encryption once, at
  the ORM boundary. It's impossible to "forget" to decrypt.
* Admin API endpoints are gated by a header secret (`X-Admin-Token`);
  swap in OAuth2 / mTLS for production.
* Docker image runs as a non-root user, under `tini` for signal handling.
* `.env` is in `.gitignore` and `SECURITY.md` documents reporting policy.

### Performance choices

| Concern               | Choice                                                                 |
| --------------------- | ---------------------------------------------------------------------- |
| Event loop            | `uvloop` on Linux (≈2× faster than default asyncio)                    |
| JSON                  | `orjson` everywhere, including FastAPI responses                       |
| Postgres driver       | `asyncpg` (vs `psycopg`)                                               |
| Connection pool       | `AsyncAdaptedQueuePool` with configurable size + `pool_pre_ping`       |
| Redis                 | Single pool shared by FSM, throttling and ad-hoc cache                 |
| Rate limiting         | Atomic Lua script — safe across horizontally-scaled bot replicas       |
| External HTTP         | Persistent `ClientSession` per host; TCP keep-alive via `TCPConnector` |
| Retries               | `tenacity` exponential + full jitter; idempotent methods only          |
| Downstream protection | Per-service circuit breaker prevents queue build-up during outages     |
| Heavy jobs            | Celery on RabbitMQ — they no longer block the polling coroutine        |
| Metrics               | Prometheus instruments at every boundary (HTTP, DB, bot, Celery)       |

### Why Celery + RabbitMQ + Redis (not just one)

* **RabbitMQ** is the broker — enqueueing is guaranteed even when
  workers are offline. Redis as a broker loses tasks on eviction.
* **Redis** is the result backend — cheap, in-memory, supports TTLs.
* They coexist well and each is already used for other things
  (Redis for FSM, RabbitMQ in upcoming management integrations).

### Aiogram middleware order

Outer middlewares — i.e. closest to the dispatcher — matter most because
they wrap everything that follows:

1. `StructlogMiddleware` — assigns a correlation id to the update; every
   log line for this update carries it, including DB queries via
   `echo_pool=True` if enabled.
2. `ErrorLoggingMiddleware` — catches `TelegramBadRequest`/
   `TelegramForbiddenError` (expected, logs at INFO) and any other
   exception (logs at ERROR + notifies the user).
3. `ThrottlingMiddleware` — atomic Redis-Lua counter per user id.
4. `DbSessionMiddleware` — opens a short-lived session, auto-commits on
   success, rolls back on exception, injects under `data["session"]`.

### Database schema

The schema is intentionally unified across both marketplaces:

* one `users` record per Telegram user, not per marketplace;
* one `magazines` table covers both Wildberries and Ozon stores,
  discriminated by the `marketplace` column — clients dispatch to the
  right API based on that value;
* API tokens are stored in `EncryptedString` columns, transparently
  encrypted at the ORM boundary;
* `created_at` / `updated_at` timestamps are present on every table;
* foreign keys use `ON DELETE CASCADE` for consistent cleanup;
* Alembic manages schema changes — `Base.metadata.create_all()` is
  deliberately not used, so all structural changes are reviewable and
  reversible.

### Roadmap

The core library and service skeletons are production-ready. The
natural next steps are feature-driven and can be shipped incrementally:

* expanding per-service handler packages (`wb_bot/handlers/`,
  `ozon_bot/handlers/`) into the full seller workflow — profile,
  registration, reports, reviews, bidder, admin;
* splitting the keyboard layer into one submodule per feature area
  (main menu, magazines, reports, tasks, settings);
* adding discrete Celery tasks under `src/worker/tasks.py` for each
  scheduled workflow (review polling, report generation, advertising
  auto-bidding). Each task is independently deployable and monitorable.
