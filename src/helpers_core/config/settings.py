"""Strictly-typed application settings loaded from environment variables.

Using Pydantic Settings gives us:

* eager validation at startup (the process dies immediately if something
  required is missing instead of failing deep inside a handler at 3 AM);
* explicit, self-documenting schema that doubles as ``.env.example``;
* a single typed object that can be injected into every layer of the app.

The settings object is cached (:func:`functools.lru_cache`) because it is
immutable after startup and we want to avoid re-parsing env on every access.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    """Deployment environments.

    Having a real enum (instead of a free-form string) lets other modules
    switch behaviour safely — e.g. different log format or stricter
    timeouts in production — without risking typos.
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogFormat(StrEnum):
    JSON = "json"
    CONSOLE = "console"


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection parameters and pool tuning."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_", extra="ignore")

    host: str = "postgres"
    port: int = 5432
    db: str = "helpers"
    user: str = "helpers"
    password: SecretStr = SecretStr("helpers")

    @property
    def dsn(self) -> str:
        """SQLAlchemy DSN using ``asyncpg`` driver."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.db}"
        )


class DatabasePoolSettings(BaseSettings):
    """Connection-pool tuning, separated so it can be overridden per-service."""

    model_config = SettingsConfigDict(env_prefix="DB_", extra="ignore")

    pool_size: Annotated[int, Field(ge=1, le=1000)] = 20
    max_overflow: Annotated[int, Field(ge=0, le=1000)] = 10
    pool_timeout: Annotated[int, Field(ge=1, le=300)] = 30
    pool_recycle: Annotated[int, Field(ge=60, le=86_400)] = 1800
    echo: bool = False


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    redis_url: str = "redis://redis:6379/0"


class RabbitSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672//"
    celery_result_backend: str = "redis://redis:6379/1"


class SecuritySettings(BaseSettings):
    """Fernet keys for transparent symmetric encryption of API tokens.

    Multiple keys can be provided (comma-separated) to support zero-downtime
    key rotation: the first key is used for encryption, all keys are tried on
    decryption (see :mod:`helpers_core.security.crypto`).
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    fernet_keys: SecretStr

    @field_validator("fernet_keys")
    @classmethod
    def _non_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            msg = (
                "FERNET_KEYS must not be empty. "
                "Generate one with `python scripts/generate_fernet_key.py`."
            )
            raise ValueError(msg)
        return value

    @property
    def keys(self) -> tuple[str, ...]:
        """Parsed list of keys — primary first, then fallbacks for rotation."""
        raw = self.fernet_keys.get_secret_value()
        return tuple(k.strip() for k in raw.split(",") if k.strip())


class TelegramSettings(BaseSettings):
    """Per-bot tokens. An empty value disables the corresponding bot locally."""

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    wb_bot_token: SecretStr = SecretStr("")
    ozon_bot_token: SecretStr = SecretStr("")
    task_planner_bot_token: SecretStr = SecretStr("")
    network_bot_token: SecretStr = SecretStr("")
    admin_tg_ids: str = ""

    @property
    def admin_ids(self) -> tuple[int, ...]:
        """Parsed comma-separated list of admin Telegram user IDs."""
        out: list[int] = []
        for raw in self.admin_tg_ids.split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(int(raw))
            except ValueError:
                continue
        return tuple(out)


class HttpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HTTP_", extra="ignore")

    timeout_seconds: Annotated[float, Field(gt=0, le=600)] = 30
    max_retries: Annotated[int, Field(ge=0, le=20)] = 3
    max_connections: Annotated[int, Field(ge=1, le=10_000)] = 100
    max_connections_per_host: Annotated[int, Field(ge=1, le=1_000)] = 20


class MarketplaceSettings(BaseSettings):
    """Base URLs for Wildberries and Ozon APIs.

    Kept configurable so that sandbox / staging endpoints or custom proxies
    (corporate gateways) can be plugged in without code changes.
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    wb_api_base_url: str = "https://suppliers-api.wildberries.ru"
    wb_stats_api_base_url: str = "https://statistics-api.wildberries.ru"
    wb_feedbacks_api_base_url: str = "https://feedbacks-api.wildberries.ru"
    wb_content_api_base_url: str = "https://content-api.wildberries.ru"
    wb_advert_api_base_url: str = "https://advert-api.wildberries.ru"

    ozon_api_base_url: str = "https://api-seller.ozon.ru"
    ozon_performance_api_base_url: str = "https://performance.ozon.ru:443"


class AdminApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADMIN_API_", extra="ignore")

    host: str = "0.0.0.0"  # noqa: S104  (bind-all in container is expected)
    port: Annotated[int, Field(gt=0, lt=65_536)] = 8000
    workers: Annotated[int, Field(ge=1, le=64)] = 2


class MetricsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="METRICS_", extra="ignore")

    host: str = "0.0.0.0"  # noqa: S104
    port: Annotated[int, Field(gt=0, lt=65_536)] = 9100


class Settings(BaseSettings):
    """Top-level application settings.

    Rather than declaring one giant flat model we compose smaller ones,
    which keeps ``.env`` readable and lets modules depend on only the slice
    they need (e.g. ``settings.db`` in repository tests).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnv = AppEnv.DEVELOPMENT
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.JSON
    app_release: str = "local"

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    db_pool: DatabasePoolSettings = Field(default_factory=DatabasePoolSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    rabbit: RabbitSettings = Field(default_factory=RabbitSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)  # type: ignore[arg-type]
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    http: HttpSettings = Field(default_factory=HttpSettings)
    marketplaces: MarketplaceSettings = Field(default_factory=MarketplaceSettings)
    admin_api: AdminApiSettings = Field(default_factory=AdminApiSettings)
    metrics: MetricsSettings = Field(default_factory=MetricsSettings)

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton settings instance.

    Importing ``Settings()`` directly would re-parse the environment on every
    call; using ``lru_cache`` makes the settings object effectively a
    process-wide singleton while keeping explicit, testable construction
    (tests can call ``get_settings.cache_clear()``).
    """

    return Settings()  # type: ignore[call-arg]
