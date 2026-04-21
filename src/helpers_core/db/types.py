"""Custom SQLAlchemy types.

:class:`EncryptedString` wraps a regular string column with transparent
Fernet encryption and decryption. Callers read and write plain Python
strings; the database never sees the plaintext. Centralising encryption
at the ORM boundary makes it impossible to accidentally forget to
encrypt a value, and keeps crypto logic out of individual repositories.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Dialect, String
from sqlalchemy.types import TypeDecorator

from helpers_core.security import get_cipher


class EncryptedString(TypeDecorator[str]):
    """Transparent Fernet-encrypted string column.

    Notes:
        * Underlying column is ``VARCHAR`` because Fernet ciphertexts are
          ASCII (base64-urlsafe). Length defaults to ``1024``, which is far
          beyond the size of any marketplace API token we store.
        * :attr:`cache_ok` is ``True`` — the type is pure and produces the
          same bind expression for identical inputs, so SQLAlchemy's
          compiled-statement cache is safe to use.
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int = 1024, **kwargs: Any) -> None:
        super().__init__(length=length, **kwargs)

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return get_cipher().encrypt(value)

    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return get_cipher().decrypt(value)
