from datetime import datetime, timezone
import unittest

from thinkinginbets.domain import MarketSnapshot, Order, OrderSide, OrderStatus, OutcomeQuote, Portfolio, TradeIntent
from thinkinginbets.paper import PaperBroker


class PaperBrokerTest(unittest.TestCase):
    def test_buy_and_sell_updates_cash_position_and_realized_pnl(self) -> None:
        snapshot = MarketSnapshot(
            market_id="m1",
            title="Test",
            event_time=datetime.now(timezone.utc),
            observed_at=datetime.now(timezone.utc),
            quotes={"home": OutcomeQuote("home", bid_cents=48, ask_cents=50)},
        )
        portfolio = Portfolio(cash_cents=10_000)
        broker = PaperBroker(portfolio)

        buy = Order(
            intent=TradeIntent("m1", "home", OrderSide.BUY, limit_price_cents=50, quantity=2, reason="test"),
            status=OrderStatus.ACCEPTED,
        )
        broker.submit(buy, snapshot)

        self.assertEqual(portfolio.cash_cents, 9_900)
        self.assertEqual(portfolio.get_position("m1", "home").quantity, 2)
        self.assertEqual(portfolio.get_position("m1", "home").average_price_cents, 50)

        sell = Order(
            intent=TradeIntent("m1", "home", OrderSide.SELL, limit_price_cents=48, quantity=1, reason="test"),
            status=OrderStatus.ACCEPTED,
        )
        broker.submit(sell, snapshot)

        self.assertEqual(portfolio.cash_cents, 9_948)
        self.assertEqual(portfolio.get_position("m1", "home").quantity, 1)
        self.assertEqual(portfolio.realized_pnl_cents, -2)


if __name__ == "__main__":
    unittest.main()
