"""WB bot handlers package.

All handler routers must follow the canonical wiring pattern enforced
here:

* every feature area lives in its own submodule and exposes a
  :class:`aiogram.Router` named ``router``;
* routers are registered exactly once, via :func:`register_handlers`,
  called from :mod:`wb_bot.__main__` during startup;
* handlers receive the SQLAlchemy session injected by the shared
  :class:`DbSessionMiddleware` under ``data["session"]`` — no session
  is created inside a handler;
* data access goes through repositories from :mod:`helpers_core.domain`,
  never ad-hoc SQL;
* marketplace I/O is delegated to :class:`WildberriesClient` from
  :mod:`helpers_core.marketplaces`.

Planned feature routers (one submodule per area): ``profile``,
``registration``, ``settings``, ``reviews``, ``reports``, ``tasks``,
``admin``.
"""

from aiogram import Dispatcher

from wb_bot.handlers.start import router as start_router


def register_handlers(dp: Dispatcher) -> None:
    """Single place where every router is included into the dispatcher."""
    dp.include_router(start_router)


__all__ = ["register_handlers"]
