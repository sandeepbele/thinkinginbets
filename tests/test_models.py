import unittest

from thinkinginbets.models.base import MatchContext
from thinkinginbets.models.penaltyblog_model import PenaltyblogModelAdapter


class FakePenaltyblogModel:
    def predict(self, home_team: str, away_team: str) -> dict[str, float]:
        if (home_team, away_team) != ("Argentina", "France"):
            raise AssertionError("unexpected teams")
        return {"home_win": 0.43, "draw": 0.29, "away_win": 0.28}


class PenaltyblogModelAdapterTest(unittest.TestCase):
    def test_normalizes_trained_model_prediction(self) -> None:
        adapter = PenaltyblogModelAdapter(
            trained_model=FakePenaltyblogModel(),
            rationale="test penaltyblog model",
        )

        probabilities = adapter.predict(MatchContext(home_team="Argentina", away_team="France"))

        self.assertEqual([p.outcome_id for p in probabilities], ["home", "draw", "away"])
        self.assertEqual([p.probability for p in probabilities], [0.43, 0.29, 0.28])


if __name__ == "__main__":
    unittest.main()
