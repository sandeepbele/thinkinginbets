"""Static model useful for tests and early simulations."""

from __future__ import annotations

from dataclasses import dataclass

from thinkinginbets.domain import ModelProbability
from thinkinginbets.models.base import MatchContext


@dataclass(frozen=True)
class StaticMatchProbabilityModel:
    home: float
    draw: float
    away: float
    rationale: str = "static probability fixture"

    def predict(self, _context: MatchContext) -> list[ModelProbability]:
        return [
            ModelProbability("home", self.home, self.rationale),
            ModelProbability("draw", self.draw, self.rationale),
            ModelProbability("away", self.away, self.rationale),
        ]
