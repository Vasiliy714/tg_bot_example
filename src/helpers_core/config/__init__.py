"""Configuration subpackage.

All runtime configuration comes from environment variables and is validated
with Pydantic. No business module is allowed to call ``os.getenv`` directly;
instead it depends on :class:`Settings` (via :func:`get_settings`), which
makes wiring explicit, testable and type-safe.
"""

from helpers_core.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
