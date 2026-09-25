from datetime import datetime, timezone
import unittest

from thinkinginbets.feeds.api_football import normalize_api_football_fixture
from thinkinginbets.feeds.espn import normalize_espn_scoreboard_event
from thinkinginbets.feeds.scrape import find_stat_triplets, visible_text_from_html
from thinkinginbets.feeds.sportmonks import normalize_sportmonks_livescore


class SportmonksNormalizerTest(unittest.TestCase):
    def test_normalizes_livescore_payload(self) -> None:
        state = normalize_sportmonks_livescore(
            {
                "id": 123,
                "minute": 71,
                "updated_at": "2026-06-16T20:10:00Z",
                "state": {"name": "2nd Half"},
                "participants": [
                    {"name": "Argentina", "meta": {"location": "home"}},
                    {"name": "France", "meta": {"location": "away"}},
                ],
                "scores": [
                    {"description": "CURRENT", "score": {"participant": "home", "goals": 2}},
                    {"description": "CURRENT", "score": {"participant": "away", "goals": 1}},
                ],
            }
        )

        self.assertEqual(state.provider_match_id, "123")
        self.assertEqual(state.home_team, "Argentina")
        self.assertEqual(state.away_team, "France")
        self.assertEqual(state.minute, 71)
        self.assertEqual(state.home_goals, 2)
        self.assertEqual(state.away_goals, 1)
        self.assertEqual(state.observed_at, datetime(2026, 6, 16, 20, 10, tzinfo=timezone.utc))


class ApiFootballNormalizerTest(unittest.TestCase):
    def test_normalizes_fixture_payload(self) -> None:
        state = normalize_api_football_fixture(
            {
                "fixture": {"id": 456, "status": {"elapsed": 39, "long": "First Half"}},
                "teams": {
                    "home": {"name": "Brazil"},
                    "away": {"name": "Germany"},
                },
                "goals": {"home": 1, "away": 0},
            }
        )

        self.assertEqual(state.provider, "api_football")
        self.assertEqual(state.provider_match_id, "456")
        self.assertEqual(state.home_team, "Brazil")
        self.assertEqual(state.away_team, "Germany")
        self.assertEqual(state.minute, 39)
        self.assertEqual(state.home_goals, 1)
        self.assertEqual(state.away_goals, 0)


class EspnNormalizerTest(unittest.TestCase):
    def test_normalizes_scoreboard_event(self) -> None:
        state = normalize_espn_scoreboard_event(
            {
                "id": "789",
                "status": {"displayClock": "67'", "type": {"description": "In Progress"}},
                "competitions": [
                    {
                        "competitors": [
                            {
                                "homeAway": "home",
                                "score": "2",
                                "team": {"displayName": "Spain"},
                                "statistics": [
                                    {"name": "wonCorners", "displayValue": "8"},
                                    {"name": "possessionPct", "displayValue": "62.3"},
                                    {"name": "shotsOnTarget", "displayValue": "5"},
                                ],
                            },
                            {
                                "homeAway": "away",
                                "score": "2",
                                "team": {"displayName": "Japan"},
                                "statistics": [
                                    {"name": "wonCorners", "displayValue": "2"},
                                    {"name": "possessionPct", "displayValue": "37.7"},
                                    {"name": "shotsOnTarget", "displayValue": "3"},
                                ],
                            },
                        ]
                    }
                ],
            }
        )

        self.assertEqual(state.provider, "espn_public")
        self.assertEqual(state.provider_match_id, "789")
        self.assertEqual(state.home_team, "Spain")
        self.assertEqual(state.away_team, "Japan")
        self.assertEqual(state.minute, 67)
        self.assertEqual(state.home_goals, 2)
        self.assertEqual(state.away_goals, 2)
        self.assertEqual(state.statistics["home_wonCorners"], 8)
        self.assertEqual(state.statistics["away_wonCorners"], 2)
        self.assertEqual(state.statistics["home_possessionPct"], 62.3)
        self.assertEqual(state.statistics["away_shotsOnTarget"], 3)


class ScrapeFallbackTest(unittest.TestCase):
    def test_extracts_visible_text(self) -> None:
        self.assertEqual(visible_text_from_html("<main><b>58</b> Possession 42</main>"), "58 Possession 42")

    def test_finds_simple_stat_triplets(self) -> None:
        stats = find_stat_triplets(["58", "Possession", "42", "7", "Corners", "1"])

        self.assertEqual(stats[0].name, "possession")
        self.assertEqual(stats[0].home_value, 58)
        self.assertEqual(stats[0].away_value, 42)
        self.assertEqual(stats[1].name, "corners")


if __name__ == "__main__":
    unittest.main()
