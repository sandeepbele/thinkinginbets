"""Base exchange adapter protocols."""

from __future__ import annotations

from typing import Protocol

from thinkinginbets.domain import MarketSnapshot, Order


class MarketDataAdapter(Protocol):
    async def watch_market(self, market_id: str) -> MarketSnapshot:
        """Return the next market snapshot for a market."""


class ExecutionAdapter(Protocol):
    async def submit_order(self, order: Order) -> str:
        """Submit an accepted order and return the exchange order id."""
