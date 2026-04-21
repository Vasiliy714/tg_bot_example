"""Generate a new Fernet key and print it to stdout.

Usage:
    python scripts/generate_fernet_key.py
    # copy the output into FERNET_KEYS in your .env

For rotation: prepend the new key to the existing comma-separated list,
deploy, re-encrypt stored values (they re-encrypt naturally on next update),
then drop the old key.
"""

from __future__ import annotations

from cryptography.fernet import Fernet


def main() -> None:
    print(Fernet.generate_key().decode())


if __name__ == "__main__":
    main()
