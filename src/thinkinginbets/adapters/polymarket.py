"""Polymarket adapter placeholder.

Use the compliant US API surface when operating from the United States.
"""

from __future__ import annotations


class PolymarketAdapter:
    def __init__(self, *, api_key: str, api_secret: str, api_passphrase: str) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase

    async def submit_order(self, _order: object) -> str:
        raise NotImplementedError("Polymarket live execution is intentionally disabled")
