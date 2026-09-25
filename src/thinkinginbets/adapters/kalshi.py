"""Kalshi adapter placeholder.

Live trading intentionally starts unimplemented. The paper engine should prove
itself against real-time market data before this submits orders.
"""

from __future__ import annotations


class KalshiAdapter:
    def __init__(self, *, api_key_id: str, private_key_path: str) -> None:
        self.api_key_id = api_key_id
        self.private_key_path = private_key_path

    async def submit_order(self, _order: object) -> str:
        raise NotImplementedError("Kalshi live execution is intentionally disabled")
