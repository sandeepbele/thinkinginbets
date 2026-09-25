import unittest

from thinkinginbets.kalshi_espn_replay import FillDiagnostic, PublicReplayReport
from thinkinginbets.scorecard import build_replay_scorecard


class ScorecardTest(unittest.TestCase):
    def test_computes_drawdown_and_buckets(self) -> None:
        reports = [
            PublicReplayReport(
                "A",
                10,
                2,
                0,
                0,
                11_000,
                1_000,
                10,
                "draw",
                [],
                [
                    FillDiagnostic("draw", "buy", 70, "0-0", 50, 2, 10, 90),
                    FillDiagnostic("home", "sell", 80, "0-0", 20, 1, 1, 19),
                ],
            ),
            PublicReplayReport(
                "B",
                10,
                2,
                0,
                0,
                9_000,
                -2_000,
                20,
                "home",
                [],
                [
                    FillDiagnostic("away", "buy", 20, "0-0", 30, 3, 3, -93),
                    FillDiagnostic("home", "buy", 35, "1-0", 80, 1, 4, 16),
                ],
            ),
        ]

        scorecard = build_replay_scorecard(
            reports,
            starting_cash_cents=10_000,
            ending_cash_cents=9_000,
            equity_curve_cents=[11_000, 9_000],
        )

        self.assertEqual(scorecard.total_pnl_cents, -1_000)
        self.assertEqual(scorecard.max_drawdown_cents, 2_000)
        self.assertEqual(scorecard.pnl_per_match_cents, -500)
        self.assertEqual(scorecard.pnl_per_fill_cents, -250)
        self.assertEqual(scorecard.by_outcome["draw"].pnl_cents, 1_000)
        self.assertEqual(scorecard.by_outcome["draw"].pnl_per_fill_cents, 500)
        self.assertEqual(scorecard.by_minute_band["61-75"].pnl_cents, 90)
        self.assertEqual(scorecard.by_price_band["25-49c"].average_entry_price_cents, 30)
        self.assertEqual(scorecard.by_outcome_minute_band["draw 61-75"].contracts, 2)
        self.assertEqual(scorecard.by_side_outcome_minute_band["buy draw 61-75"].pnl_cents, 90)
        self.assertEqual(scorecard.worst_match.label, "B")


if __name__ == "__main__":
    unittest.main()
