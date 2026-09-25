"""Trading strategies."""

from __future__ import annotations

from dataclasses import dataclass, field

from thinkinginbets.domain import MarketSnapshot, ModelProbability, OrderSide, Portfolio, TradeIntent


@dataclass(frozen=True)
class ValueStrategy:
    """Trades when model fair value clears the market by a minimum edge."""

    min_edge_cents: int = 4
    max_quantity: int = 5

    def propose(
        self,
        snapshot: MarketSnapshot,
        probabilities: list[ModelProbability],
        portfolio: Portfolio | None = None,
    ) -> list[TradeIntent]:
        intents: list[TradeIntent] = []

        for probability in probabilities:
            quote = snapshot.require_quote(probability.outcome_id)
            fair_cents = probability.fair_value_cents()
            total_cost_buffer = self.min_edge_cents + snapshot.fee_cents_per_contract

            if quote.ask_cents is not None and fair_cents - quote.ask_cents >= total_cost_buffer:
                intents.append(
                    TradeIntent(
                        market_id=snapshot.market_id,
                        outcome_id=probability.outcome_id,
                        side=OrderSide.BUY,
                        limit_price_cents=quote.ask_cents,
                        quantity=self.max_quantity,
                        reason=(
                            f"model fair value {fair_cents}c exceeds ask "
                            f"{quote.ask_cents}c; {probability.rationale}"
                        ),
                    )
                )

            if quote.bid_cents is not None and quote.bid_cents - fair_cents >= total_cost_buffer:
                intents.append(
                    TradeIntent(
                        market_id=snapshot.market_id,
                        outcome_id=probability.outcome_id,
                        side=OrderSide.SELL,
                        limit_price_cents=quote.bid_cents,
                        quantity=self.max_quantity,
                        reason=(
                            f"bid {quote.bid_cents}c exceeds model fair value "
                            f"{fair_cents}c; {probability.rationale}"
                        ),
                    )
                )

        return intents


@dataclass
class DisciplinedValueStrategy:
    """Position-targeted value strategy for bankroll-limited replay.

    The key behavior difference from `ValueStrategy`: repeated edge signals move
    toward a target position instead of repeatedly adding every tick.
    """

    min_edge_cents: int = 5
    edge_step_cents: int = 6
    order_quantity: int = 5
    max_outcome_position: int = 20
    max_draw_position: int = 25
    trim_quantity: int = 5
    take_profit_cents: int = 18
    max_draw_buy_minute: int = 45
    allow_draw_sells: bool = False
    min_seconds_between_same_outcome_buys: int = 600
    min_price_improvement_cents: int = 3
    last_buy_at: dict[tuple[str, str], float] = field(default_factory=dict)
    last_buy_price_cents: dict[tuple[str, str], int] = field(default_factory=dict)

    def propose(
        self,
        snapshot: MarketSnapshot,
        probabilities: list[ModelProbability],
        portfolio: Portfolio | None = None,
    ) -> list[TradeIntent]:
        if portfolio is None:
            return ValueStrategy(
                min_edge_cents=self.min_edge_cents,
                max_quantity=self.order_quantity,
            ).propose(snapshot, probabilities)

        intents: list[TradeIntent] = []
        minute = int(snapshot.metadata.get("minute", 0) or 0)
        home_goals = int(snapshot.metadata.get("home_goals", 0) or 0)
        away_goals = int(snapshot.metadata.get("away_goals", 0) or 0)
        is_tied = home_goals == away_goals
        observed_ts = snapshot.observed_at.timestamp()

        for probability in probabilities:
            quote = snapshot.require_quote(probability.outcome_id)
            fair_cents = probability.fair_value_cents()
            position = portfolio.get_position(snapshot.market_id, probability.outcome_id)

            if (
                quote.bid_cents is not None
                and position.quantity > 0
                and (probability.outcome_id != "draw" or self.allow_draw_sells)
            ):
                sell_reason = self._sell_reason(
                    outcome_id=probability.outcome_id,
                    bid_cents=quote.bid_cents,
                    fair_cents=fair_cents,
                    average_price_cents=position.average_price_cents,
                    minute=minute,
                    rationale=probability.rationale,
                )
                if sell_reason is not None:
                    intents.append(
                        TradeIntent(
                            market_id=snapshot.market_id,
                            outcome_id=probability.outcome_id,
                            side=OrderSide.SELL,
                            limit_price_cents=quote.bid_cents,
                            quantity=min(self.trim_quantity, position.quantity),
                            reason=sell_reason,
                        )
                    )
                    continue

            if quote.ask_cents is None:
                continue
            edge_cents = fair_cents - quote.ask_cents - snapshot.fee_cents_per_contract
            if edge_cents < self.min_edge_cents:
                continue
            if self._blocks_new_exposure(
                outcome_id=probability.outcome_id,
                minute=minute,
                is_tied=is_tied,
            ):
                continue

            target_quantity = self._target_quantity(probability.outcome_id, edge_cents)
            quantity_to_buy = min(
                self.order_quantity,
                max(target_quantity - position.quantity, 0),
            )
            if quantity_to_buy <= 0:
                continue

            key = (snapshot.market_id, probability.outcome_id)
            if self._is_redundant_buy(key, quote.ask_cents, observed_ts, position.quantity):
                continue

            self.last_buy_at[key] = observed_ts
            self.last_buy_price_cents[key] = quote.ask_cents
            intents.append(
                TradeIntent(
                    market_id=snapshot.market_id,
                    outcome_id=probability.outcome_id,
                    side=OrderSide.BUY,
                    limit_price_cents=quote.ask_cents,
                    quantity=quantity_to_buy,
                    reason=(
                        f"target position {target_quantity}; model fair value {fair_cents}c "
                        f"exceeds ask {quote.ask_cents}c by {edge_cents}c after buffer; "
                        f"{probability.rationale}"
                    ),
                )
            )

        return intents

    def _blocks_new_exposure(self, *, outcome_id: str, minute: int, is_tied: bool) -> bool:
        if outcome_id == "draw" and minute > self.max_draw_buy_minute:
            return True

        # In late tied soccer states, avoid chasing winner narratives. If a game is
        # 0-0 or 1-1 after 70', new exposure should be draw-focused or risk-reducing.
        return is_tied and minute >= 70 and outcome_id != "draw"

    def _target_quantity(self, outcome_id: str, edge_cents: int) -> int:
        max_position = self.max_draw_position if outcome_id == "draw" else self.max_outcome_position
        edge_units = max(1, edge_cents // self.edge_step_cents)
        return min(max_position, edge_units * self.order_quantity)

    def _is_redundant_buy(
        self,
        key: tuple[str, str],
        ask_cents: int,
        observed_ts: float,
        current_quantity: int,
    ) -> bool:
        last_ts = self.last_buy_at.get(key)
        last_price = self.last_buy_price_cents.get(key)
        if last_ts is None or last_price is None or current_quantity == 0:
            return False
        if ask_cents <= last_price - self.min_price_improvement_cents:
            return False
        return observed_ts - last_ts < self.min_seconds_between_same_outcome_buys

    def _sell_reason(
        self,
        *,
        outcome_id: str,
        bid_cents: int,
        fair_cents: int,
        average_price_cents: float,
        minute: int,
        rationale: str,
    ) -> str | None:
        if bid_cents - fair_cents >= self.min_edge_cents:
            return (
                f"trim: bid {bid_cents}c exceeds model fair value {fair_cents}c; "
                f"{rationale}"
            )

        profit_cents = bid_cents - average_price_cents
        late_draw_profit = outcome_id == "draw" and minute >= 75 and profit_cents >= self.take_profit_cents
        late_non_draw_profit = outcome_id != "draw" and minute >= 80 and profit_cents >= self.take_profit_cents
        if late_draw_profit or late_non_draw_profit:
            return (
                f"take profit: bid {bid_cents}c is {profit_cents:.1f}c above "
                f"average entry {average_price_cents:.1f}c"
            )

        return None
