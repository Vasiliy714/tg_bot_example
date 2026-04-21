"""Block until PostgreSQL accepts connections.

Useful inside container init scripts when depends_on health-checks are not
available (e.g. some orchestrators) or when running migrations before the
main service boots.
"""

from __future__ import annotations

import asyncio
import sys
import time

import asyncpg

from helpers_core.config import get_settings


async def _probe(dsn: str) -> bool:
    try:
        connection = await asyncpg.connect(dsn=dsn)
    except (OSError, asyncpg.PostgresError):
        return False
    try:
        await connection.execute("SELECT 1")
    finally:
        await connection.close()
    return True


async def _wait(timeout_seconds: int) -> None:
    settings = get_settings()
    # asyncpg doesn't understand the 'postgresql+asyncpg' dialect prefix
    dsn = settings.db.dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if await _probe(dsn):
            return
        await asyncio.sleep(1)
    raise SystemExit(f"PostgreSQL was not ready within {timeout_seconds}s")


def main() -> None:
    timeout = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    asyncio.run(_wait(timeout))


if __name__ == "__main__":
    main()
