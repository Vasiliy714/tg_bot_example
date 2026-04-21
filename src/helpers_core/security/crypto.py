"""Fernet-based symmetric encryption with zero-downtime key rotation.

This module wraps :class:`cryptography.fernet.MultiFernet` — the primitive
recommended by the :mod:`cryptography` library for operating multiple
keys simultaneously:

* the first key in the rotation is always used for encryption;
* every key is tried on decryption;
* rotating keys is a config change (prepend the new key) — no downtime.

Keys are supplied via the ``FERNET_KEYS`` environment variable
(comma-separated). Tokens stored in the database are re-encrypted to
the primary key on update, so rotation converges naturally without a
dedicated backfill job.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from helpers_core.config import Settings, get_settings


class CryptoError(RuntimeError):
    """Raised when a ciphertext cannot be decrypted with any known key."""


class FernetCipher:
    """Thin wrapper around :class:`cryptography.fernet.MultiFernet`.

    The wrapper adds:

    * ergonomic ``str``-in / ``str``-out API (the underlying Fernet operates
      on raw bytes), which matches how tokens are stored in Postgres;
    * a targeted :class:`CryptoError` instead of the library's
      :class:`InvalidToken`, so callers don't have to import
      :mod:`cryptography` directly;
    * a convenience :meth:`needs_reencryption` to detect values still
      encrypted with a non-primary key — used during read-repair.
    """

    __slots__ = ("_primary_fernet", "_multi")

    def __init__(self, keys: tuple[str, ...]) -> None:
        if not keys:
            msg = "FernetCipher requires at least one key."
            raise ValueError(msg)
        fernets = [Fernet(key.encode() if isinstance(key, str) else key) for key in keys]
        self._primary_fernet: Fernet = fernets[0]
        self._multi = MultiFernet(fernets)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt with the primary key."""
        return self._primary_fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt, trying each configured key in order."""
        try:
            return self._multi.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            msg = "Token cannot be decrypted with any configured Fernet key."
            raise CryptoError(msg) from exc

    def rotate(self, ciphertext: str) -> str:
        """Re-encrypt ``ciphertext`` with the primary key (used by tools/jobs)."""
        try:
            return self._multi.rotate(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            msg = "Cannot rotate: source token is not valid under any key."
            raise CryptoError(msg) from exc

    def needs_reencryption(self, ciphertext: str) -> bool:
        """``True`` if ``ciphertext`` was encrypted with a non-primary key.

        Useful for background re-encryption jobs: stream all rows, call this,
        and :meth:`rotate` only those that need it.
        """
        try:
            self._primary_fernet.decrypt(ciphertext.encode("utf-8"))
        except InvalidToken:
            return True
        return False


@lru_cache(maxsize=1)
def _cached_cipher(key_tuple: tuple[str, ...]) -> FernetCipher:
    return FernetCipher(key_tuple)


def get_cipher(settings: Settings | None = None) -> FernetCipher:
    """Return the process-wide cipher, constructed from settings."""
    settings = settings or get_settings()
    return _cached_cipher(settings.security.keys)
