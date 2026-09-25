import unittest

from thinkinginbets.backtest import run_backtest
from thinkinginbets.feeds.base import MatchState


class BacktestTest(unittest.TestCase):
    def test_backtests_only_final_matches(self) -> None:
        report = run_backtest(
            [
                MatchState(
                    provider="espn_public",
                    provider_match_id="final",
                    home_team="France",
                    away_team="Senegal",
                    minute=90,
                    home_goals=2,
                    away_goals=0,
                    status="Full Time",
                ),
                MatchState(
                    provider="espn_public",
                    provider_match_id="scheduled",
                    home_team="Argentina",
                    away_team="Algeria",
                    minute=0,
                    home_goals=0,
                    away_goals=0,
                    status="Scheduled",
                ),
            ],
            stake_cents=1_000,
            min_probability=0.55,
        )

        self.assertEqual(len(report.bets), 1)
        self.assertEqual(report.bets[0].provider_match_id, "final")
        self.assertEqual(report.bets[0].predicted_outcome, "home")
        self.assertEqual(report.bets[0].actual_outcome, "home")
        self.assertGreater(report.total_pnl_cents, 0)


if __name__ == "__main__":
    unittest.main()
