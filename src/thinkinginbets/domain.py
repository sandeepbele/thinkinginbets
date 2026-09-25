"""Core domain objects for prediction-market trading."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FILLED = "filled"


@dataclass(frozen=True)
class OutcomeQuote:
    """Best bid/ask quote for one mutually exclusive outcome."""

    outcome_id: str
    bid_cents: int | None
    ask_cents: int | None

    def mid_cents(self) -> float | None:
        if self.bid_cents is None or self.ask_cents is None:
            return None
        return (self.bid_cents + self.ask_cents) / 2


@dataclass(frozen=True)
class MarketSnapshot:
    """Point-in-time market data for one prediction market."""

    market_id: str
    title: str
    event_time: datetime
    observed_at: datetime
    quotes: Mapping[str, OutcomeQuote]
    fee_cents_per_contract: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)

    def require_quote(self, outcome_id: str) -> OutcomeQuote:
        try:
            return self.quotes[outcome_id]
        except KeyError as exc:
            raise ValueError(f"missing quote for outcome {outcome_id!r}") from exc


@dataclass(frozen=True)
class ModelProbability:
    """Model probability for one outcome, expressed from 0.0 to 1.0."""

    outcome_id: str
    probability: float
    rationale: str

    def fair_value_cents(self) -> int:
        return round(self.probability * 100)


@dataclass(frozen=True)
class TradeIntent:
    """A strategy proposal before risk checks."""

    market_id: str
    outcome_id: str
    side: OrderSide
    limit_price_cents: int
    quantity: int
    reason: str

    @property
    def notional_cents(self) -> int:
        return self.limit_price_cents * self.quantity


@dataclass(frozen=True)
class RejectedIntent:
    intent: TradeIntent
    reason: str


@dataclass
class Order:
    """Order after risk review."""

    intent: TradeIntent
    status: OrderStatus
    status_reason: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Fill:
    market_id: str
    outcome_id: str
    side: OrderSide
    price_cents: int
    quantity: int
    fee_cents: int = 0
    metadata: Mapping[str, object] = field(default_factory=dict)
    filled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def notional_cents(self) -> int:
        return self.price_cents * self.quantity


@dataclass
class Position:
    market_id: str
    outcome_id: str
    quantity: int = 0
    average_price_cents: float = 0.0

    @property
    def cost_basis_cents(self) -> float:
        return self.quantity * self.average_price_cents

    def apply_fill(self, fill: Fill) -> None:
        if fill.side is OrderSide.BUY:
            total_cost = self.cost_basis_cents + fill.notional_cents
            self.quantity += fill.quantity
            self.average_price_cents = total_cost / self.quantity if self.quantity else 0.0
            return

        if fill.quantity > self.quantity:
            raise ValueError("cannot sell more contracts than the current paper position")

        self.quantity -= fill.quantity
        if self.quantity == 0:
            self.average_price_cents = 0.0


@dataclass
class Portfolio:
    cash_cents: int
    realized_pnl_cents: int = 0
    positions: dict[tuple[str, str], Position] = field(default_factory=dict)

    def get_position(self, market_id: str, outcome_id: str) -> Position:
        key = (market_id, outcome_id)
        if key not in self.positions:
            self.positions[key] = Position(market_id=market_id, outcome_id=outcome_id)
        return self.positions[key]

    def market_exposure_cents(self, market_id: str) -> float:
        return sum(
            position.cost_basis_cents
            for (position_market_id, _), position in self.positions.items()
            if position_market_id == market_id
        )
