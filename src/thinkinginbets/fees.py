"""Exchange fee models."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING


@dataclass(frozen=True)
class KalshiFeeModel:
    """Conservative Kalshi general taker fee model.

    Official general formula: fee = 0.07 * contracts * price * (1 - price).
    We round up to the nearest cent for paper accounting. This is intentionally
    conservative for tiny paper quantities.
    """

    def taker_fee_cents(self, *, price_cents: int, quantity: int) -> int:
        price = Decimal(price_cents) / Decimal(100)
        quantity_decimal = Decimal(quantity)
        fee_dollars = Decimal("0.07") * quantity_decimal * price * (Decimal(1) - price)
        return int((fee_dollars * Decimal(100)).to_integral_value(rounding=ROUND_CEILING))
