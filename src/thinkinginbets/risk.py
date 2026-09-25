"""Risk checks that run before any order reaches a broker or exchange."""

from __future__ import annotations

from dataclasses import dataclass

from thinkinginbets.domain import OrderSide, Portfolio, RejectedIntent, TradeIntent


@dataclass(frozen=True)
class RiskLimits:
    max_order_notional_cents: int = 1_000
    max_market_exposure_cents: int = 5_000
    max_session_loss_cents: int = 2_500


@dataclass
class RiskManager:
    limits: RiskLimits

    def review(self, portfolio: Portfolio, intent: TradeIntent) -> RejectedIntent | None:
        if intent.quantity <= 0:
            return RejectedIntent(intent=intent, reason="quantity must be positive")

        if not 1 <= intent.limit_price_cents <= 99:
            return RejectedIntent(intent=intent, reason="limit price must be between 1c and 99c")

        if intent.notional_cents > self.limits.max_order_notional_cents:
            return RejectedIntent(intent=intent, reason="order notional exceeds max order limit")

        if portfolio.realized_pnl_cents <= -self.limits.max_session_loss_cents:
            return RejectedIntent(intent=intent, reason="session loss limit reached")

        if intent.side is OrderSide.BUY:
            projected_exposure = (
                portfolio.market_exposure_cents(intent.market_id) + intent.notional_cents
            )
            if projected_exposure > self.limits.max_market_exposure_cents:
                return RejectedIntent(intent=intent, reason="market exposure limit exceeded")
            if intent.notional_cents > portfolio.cash_cents:
                return RejectedIntent(intent=intent, reason="insufficient paper cash")

        if intent.side is OrderSide.SELL:
            position = portfolio.get_position(intent.market_id, intent.outcome_id)
            if intent.quantity > position.quantity:
                return RejectedIntent(intent=intent, reason="cannot sell more than held")

        return None
