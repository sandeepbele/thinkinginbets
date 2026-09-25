from datetime import datetime, timezone
import unittest

from thinkinginbets.domain import MarketSnapshot, ModelProbability, OrderSide, OutcomeQuote
from thinkinginbets.strategy import ValueStrategy


class ValueStrategyTest(unittest.TestCase):
    def test_proposes_buy_when_fair_value_clears_ask(self) -> None:
        snapshot = MarketSnapshot(
            market_id="m1",
            title="Test",
            event_time=datetime.now(timezone.utc),
            observed_at=datetime.now(timezone.utc),
            quotes={"home": OutcomeQuote("home", bid_cents=40, ask_cents=42)},
            fee_cents_per_contract=1,
        )

        intents = ValueStrategy(min_edge_cents=4, max_quantity=3).propose(
            snapshot,
            [ModelProbability("home", 0.50, "test edge")],
        )

        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0].side, OrderSide.BUY)
        self.assertEqual(intents[0].limit_price_cents, 42)
        self.assertEqual(intents[0].quantity, 3)

    def test_ignores_small_edge_after_fee(self) -> None:
        snapshot = MarketSnapshot(
            market_id="m1",
            title="Test",
            event_time=datetime.now(timezone.utc),
            observed_at=datetime.now(timezone.utc),
            quotes={"home": OutcomeQuote("home", bid_cents=45, ask_cents=46)},
            fee_cents_per_contract=1,
        )

        intents = ValueStrategy(min_edge_cents=4).propose(
            snapshot,
            [ModelProbability("home", 0.50, "edge too small")],
        )

        self.assertEqual(intents, [])


if __name__ == "__main__":
    unittest.main()
