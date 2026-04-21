"""Tests for :mod:`helpers_core.security.crypto`."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from helpers_core.security.crypto import CryptoError, FernetCipher


def test_roundtrip_preserves_value() -> None:
    key = Fernet.generate_key().decode()
    cipher = FernetCipher(keys=(key,))
    assert cipher.decrypt(cipher.encrypt("secret")) == "secret"


def test_rotation_allows_decrypting_old_values() -> None:
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()

    old_cipher = FernetCipher(keys=(old_key,))
    token = old_cipher.encrypt("classified")

    rotated = FernetCipher(keys=(new_key, old_key))
    assert rotated.decrypt(token) == "classified"

    rotated_token = rotated.rotate(token)
    assert rotated_token != token
    # Now only new key is needed.
    new_only = FernetCipher(keys=(new_key,))
    assert new_only.decrypt(rotated_token) == "classified"


def test_needs_reencryption_detects_old_key() -> None:
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    with_old_primary = FernetCipher(keys=(old_key,))
    token = with_old_primary.encrypt("value")

    mixed = FernetCipher(keys=(new_key, old_key))
    assert mixed.needs_reencryption(token) is True
    assert mixed.needs_reencryption(mixed.rotate(token)) is False


def test_invalid_token_raises_crypto_error() -> None:
    key = Fernet.generate_key().decode()
    cipher = FernetCipher(keys=(key,))
    with pytest.raises(CryptoError):
        cipher.decrypt("not-a-real-token")


def test_empty_keys_rejected() -> None:
    with pytest.raises(ValueError, match="at least one key"):
        FernetCipher(keys=())
