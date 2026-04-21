"""Shared pytest fixtures.

The fixtures in this module are process-scoped where possible: building
Fernet ciphers and parsing settings is cheap but not free. Tests that need
different config should clear the ``lru_cache`` via the provided fixture.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from cryptography.fernet import Fernet

from helpers_core.config import get_settings


@pytest.fixture(autouse=True, scope="session")
def _set_fernet_key_env() -> Iterator[None]:
    """Ensure FERNET_KEYS is set for every test session.

    CI already provides one via `.gitlab-ci.yml`; locally, generating a key
    here makes pytest just work without any manual setup.
    """
    if not os.environ.get("FERNET_KEYS"):
        os.environ["FERNET_KEYS"] = Fernet.generate_key().decode()
    yield


@pytest.fixture
def settings_reset() -> Iterator[None]:
    """Clear the cached :func:`get_settings` between tests if they mutate env."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
