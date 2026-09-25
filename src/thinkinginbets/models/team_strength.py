"""Simple pre-match priors that do not depend on current World Cup results."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp

from thinkinginbets.domain import ModelProbability
from thinkinginbets.models.base import MatchContext


DEFAULT_TEAM_RATINGS = {
    "Argentina": 92,
    "France": 92,
    "Spain": 90,
    "Brazil": 90,
    "England": 88,
    "Portugal": 87,
    "Netherlands": 86,
    "Germany": 85,
    "Belgium": 84,
    "Uruguay": 83,
    "Croatia": 82,
    "Senegal": 78,
    "Norway": 77,
    "Egypt": 76,
    "Japan": 76,
    "Iran": 74,
    "Algeria": 74,
    "New Zealand": 68,
    "Iraq": 67,
    "Cape Verde": 66,
}


@dataclass(frozen=True)
class TeamStrengthPriorModel:
    """Convert rough team-strength ratings into home/draw/away probabilities."""

    ratings: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_TEAM_RATINGS))
    default_rating: int = 72
    draw_base: float = 0.24

    def predict(self, context: MatchContext) -> list[ModelProbability]:
        home_rating = self.ratings.get(context.home_team, self.default_rating)
        away_rating = self.ratings.get(context.away_team, self.default_rating)
        diff = home_rating - away_rating

        # Rating gap controls non-draw mass. Larger mismatch lowers draw probability.
        draw = max(0.16, min(0.30, self.draw_base - abs(diff) * 0.004))
        non_draw = 1.0 - draw
        home_share = 1.0 / (1.0 + exp(-diff / 10.0))
        home = non_draw * home_share
        away = non_draw * (1.0 - home_share)

        rationale = (
            f"static team-strength prior: {context.home_team}={home_rating}, "
            f"{context.away_team}={away_rating}; excludes current World Cup results"
        )
        return [
            ModelProbability("home", home, rationale),
            ModelProbability("draw", draw, rationale),
            ModelProbability("away", away, rationale),
        ]
