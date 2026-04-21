"""Typed marketplace API clients.

Each marketplace exposes its own client — Wildberries has several API hosts
(suppliers, statistics, feedbacks, content, advert), while Ozon splits into
the seller and performance APIs. The clients share the same :class:`HttpClient`
primitive and are therefore instrumented uniformly.
"""

from helpers_core.marketplaces.base import MarketplaceClient
from helpers_core.marketplaces.ozon.client import OzonClient
from helpers_core.marketplaces.wildberries.client import WildberriesClient

__all__ = ["MarketplaceClient", "OzonClient", "WildberriesClient"]
