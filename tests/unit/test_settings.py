"""Settings validation tests."""

from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

from helpers_core.config.settings import SecuritySettings, TelegramSettings


def test_fernet_keys_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    key_a = Fernet.generate_key().decode()
    key_b = Fernet.generate_key().decode()
    monkeypatch.setenv("FERNET_KEYS", f"{key_a}, {key_b}")
    settings = SecuritySettings()
    assert settings.keys == (key_a, key_b)


def test_fernet_keys_must_not_be_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FERNET_KEYS", "   ")
    with pytest.raises(ValueError, match="FERNET_KEYS"):
        SecuritySettings()


def test_admin_ids_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADMIN_TG_IDS", "1, 2, , not-an-int, 3")
    settings = TelegramSettings()
    assert settings.admin_ids == (1, 2, 3)
    # Keep env clean for other tests.
    os.environ.pop("ADMIN_TG_IDS", None)
