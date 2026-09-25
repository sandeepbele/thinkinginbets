"""Interfaces for soccer probability models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from thinkinginbets.domain import ModelProbability


@dataclass(frozen=True)
class MatchContext:
    """Structured match state used by pre-match and in-play models."""

    home_team: str
    away_team: str
    minute: int = 0
    home_goals: int = 0
    away_goals: int = 0
    red_cards_home: int = 0
    red_cards_away: int = 0
    features: Mapping[str, float | str] = field(default_factory=dict)


class MatchProbabilityModel(Protocol):
    def predict(self, context: MatchContext) -> list[ModelProbability]:
        """Return probabilities for home/draw/away outcomes."""
