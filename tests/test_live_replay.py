import unittest

from thinkinginbets.domain import Portfolio
from thinkinginbets.engine import TradingEngine
from thinkinginbets.live_replay import replay_live_scenario
from thinkinginbets.models.in_play import InPlayHeuristicModel
from thinkinginbets.paper import PaperBroker
from thinkinginbets.risk import RiskLimits, RiskManager
from thinkinginbets.simulated_live import draw_then_home_goal_scenario
from thinkinginbets.strategy import ValueStrategy


class LiveReplayTest(unittest.TestCase):
    def test_replays_draw_then_home_goal_scenario(self) -> None:
        portfolio = Portfolio(cash_cents=25_000)
        engine = TradingEngine(
            strategy=ValueStrategy(min_edge_cents=4, max_quantity=5),
            risk_manager=RiskManager(RiskLimits()),
            broker=PaperBroker(portfolio),
        )

        result = replay_live_scenario(
            draw_then_home_goal_scenario(),
            model=InPlayHeuristicModel(),
            engine=engine,
        )

        self.assertGreater(result.fill_count, 0)
        self.assertLess(portfolio.cash_cents, 25_000)


if __name__ == "__main__":
    unittest.main()
