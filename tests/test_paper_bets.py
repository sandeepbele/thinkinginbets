from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from thinkinginbets.feeds.base import MatchState
from thinkinginbets.paper_bets import append_bets, evaluate_pending_bets, propose_paper_bets, read_bets


class PaperBetJournalTest(unittest.TestCase):
    def test_proposes_only_upcoming_matches(self) -> None:
        bets = propose_paper_bets(
            [
                MatchState(
                    provider="espn_public",
                    provider_match_id="scheduled",
                    home_team="France",
                    away_team="Senegal",
                    minute=0,
                    home_goals=0,
                    away_goals=0,
                    status="Scheduled",
                ),
                MatchState(
                    provider="espn_public",
                    provider_match_id="finished",
                    home_team="Spain",
                    away_team="Cape Verde",
                    minute=90,
                    home_goals=0,
                    away_goals=0,
                    status="Full Time",
                ),
            ],
            stake_cents=1_000,
            min_probability=0.55,
            max_bets=5,
        )

        self.assertEqual(len(bets), 1)
        self.assertEqual(bets[0].provider_match_id, "scheduled")

    def test_evaluator_waits_until_final(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "paper_bets.jsonl"
            bet = propose_paper_bets(
                [
                    MatchState(
                        provider="espn_public",
                        provider_match_id="m1",
                        home_team="France",
                        away_team="Senegal",
                        minute=0,
                        home_goals=0,
                        away_goals=0,
                        status="Scheduled",
                    )
                ],
                stake_cents=1_000,
                min_probability=0.55,
                max_bets=1,
            )[0]
            append_bets(path, [bet])

            evaluate_pending_bets(
                path,
                [
                    MatchState(
                        provider="espn_public",
                        provider_match_id="m1",
                        home_team="France",
                        away_team="Senegal",
                        minute=45,
                        home_goals=0,
                        away_goals=0,
                        status="In Progress",
                    )
                ],
            )

            self.assertEqual(read_bets(path)[0].status, "pending")

    def test_evaluator_settles_final_match(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "paper_bets.jsonl"
            bet = propose_paper_bets(
                [
                    MatchState(
                        provider="espn_public",
                        provider_match_id="m1",
                        home_team="France",
                        away_team="Senegal",
                        minute=0,
                        home_goals=0,
                        away_goals=0,
                        status="Scheduled",
                    )
                ],
                stake_cents=1_000,
                min_probability=0.55,
                max_bets=1,
            )[0]
            append_bets(path, [bet])

            evaluate_pending_bets(
                path,
                [
                    MatchState(
                        provider="espn_public",
                        provider_match_id="m1",
                        home_team="France",
                        away_team="Senegal",
                        minute=90,
                        home_goals=2,
                        away_goals=1,
                        status="Full Time",
                    )
                ],
            )

            settled = read_bets(path)[0]
            self.assertEqual(settled.status, "won")
            self.assertEqual(settled.final_score, "2-1")
            self.assertIsNotNone(settled.realized_pnl_cents)


if __name__ == "__main__":
    unittest.main()
