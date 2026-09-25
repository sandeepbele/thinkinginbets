"""Deterministic paper broker for testing strategy and risk accounting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from thinkinginbets.domain import Fill, MarketSnapshot, Order, OrderSide, OrderStatus, Portfolio


class FeeModel(Protocol):
    def taker_fee_cents(self, *, price_cents: int, quantity: int) -> int:
        """Return fee in cents for an immediately filled paper order."""


@dataclass
class PaperBroker:
    portfolio: Portfolio
    fee_model: FeeModel | None = None
    total_fee_cents: int = 0
    fills: list[Fill] = field(default_factory=list)

    def submit(self, order: Order, snapshot: MarketSnapshot) -> Fill | None:
        if order.status is not OrderStatus.ACCEPTED:
            return None

        intent = order.intent
        quote = snapshot.require_quote(intent.outcome_id)

        if intent.side is OrderSide.BUY:
            if quote.ask_cents is None or intent.limit_price_cents < quote.ask_cents:
                return None
            fill_price = quote.ask_cents
            fee_cents = self._fee_cents(fill_price, intent.quantity)
            self.portfolio.cash_cents -= fill_price * intent.quantity + fee_cents

        else:
            if quote.bid_cents is None or intent.limit_price_cents > quote.bid_cents:
                return None
            fill_price = quote.bid_cents
            fee_cents = self._fee_cents(fill_price, intent.quantity)
            position = self.portfolio.get_position(intent.market_id, intent.outcome_id)
            self.portfolio.realized_pnl_cents += round(
                (fill_price - position.average_price_cents) * intent.quantity
            ) - fee_cents
            self.portfolio.cash_cents += fill_price * intent.quantity - fee_cents

        fill = Fill(
            market_id=intent.market_id,
            outcome_id=intent.outcome_id,
            side=intent.side,
            price_cents=fill_price,
            quantity=intent.quantity,
            fee_cents=fee_cents,
            metadata={
                **snapshot.metadata,
                "observed_at": snapshot.observed_at.isoformat(),
            },
        )
        self.portfolio.get_position(intent.market_id, intent.outcome_id).apply_fill(fill)
        self.fills.append(fill)
        order.status = OrderStatus.FILLED
        order.status_reason = "paper fill"
        return fill

    def _fee_cents(self, price_cents: int, quantity: int) -> int:
        if self.fee_model is None:
            return 0
        fee_cents = self.fee_model.taker_fee_cents(price_cents=price_cents, quantity=quantity)
        self.total_fee_cents += fee_cents
        return fee_cents
