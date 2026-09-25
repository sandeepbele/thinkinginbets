"""Lightweight in-play soccer probability model.

This is a test harness model, not a production edge model. It exists so we can
replay live scenarios and verify position-management behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import exp

from thinkinginbets.domain import ModelProbability
from thinkinginbets.models.base import MatchContext
from thinkinginbets.models.team_strength import DEFAULT_TEAM_RATINGS


@dataclass(frozen=True)
class InPlayHeuristicModel:
    ratings: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_TEAM_RATINGS))
    default_rating: int = 72

    def predict(self, context: MatchContext) -> list[ModelProbability]:
        rating_diff = self.ratings.get(context.home_team, self.default_rating) - self.ratings.get(
            context.away_team, self.default_rating
        )
        dominance = _dominance_signal(context)
        minute = max(0, min(context.minute, 90))

        if context.home_goals == context.away_goals:
            draw = min(0.72, 0.26 + minute * 0.004 - abs(dominance) * 0.08)
            non_draw = 1.0 - draw
            home_share = _logistic((rating_diff / 10.0) + dominance)
            home = non_draw * home_share
            away = non_draw * (1.0 - home_share)
            rationale = "in-play tie state: draw probability rises with time and low pressure"
            return _probabilities(home, draw, away, rationale)

        goal_diff = context.home_goals - context.away_goals
        home_leads = goal_diff > 0
        lead_strength = min(abs(goal_diff), 3)
        time_factor = minute / 90.0
        lead_win = min(0.94, 0.48 + 0.26 * lead_strength + 0.20 * time_factor)
        comeback = max(0.03, 0.26 - 0.16 * lead_strength - 0.10 * time_factor)
        draw = max(0.03, 1.0 - lead_win - comeback)

        if home_leads:
            home = min(0.96, lead_win + max(dominance, 0.0) * 0.06)
            away = max(0.02, 1.0 - home - draw)
        else:
            away = min(0.96, lead_win + max(-dominance, 0.0) * 0.06)
            home = max(0.02, 1.0 - away - draw)

        total = home + draw + away
        rationale = "in-play score state: leader probability rises with time, goals, and pressure"
        return _probabilities(home / total, draw / total, away / total, rationale)


def _dominance_signal(context: MatchContext) -> float:
    home_shots = float(context.features.get("home_shotsOnTarget", 0) or 0)
    away_shots = float(context.features.get("away_shotsOnTarget", 0) or 0)
    home_corners = float(context.features.get("home_wonCorners", 0) or 0)
    away_corners = float(context.features.get("away_wonCorners", 0) or 0)
    home_possession = float(context.features.get("home_possessionPct", 50) or 50)
    possession_edge = (home_possession - 50.0) / 50.0
    pressure_edge = (home_shots - away_shots) * 0.12 + (home_corners - away_corners) * 0.04
    return max(-1.5, min(1.5, possession_edge + pressure_edge))


def _logistic(value: float) -> float:
    return 1.0 / (1.0 + exp(-value))


def _probabilities(home: float, draw: float, away: float, rationale: str) -> list[ModelProbability]:
    return [
        ModelProbability("home", home, rationale),
        ModelProbability("draw", draw, rationale),
        ModelProbability("away", away, rationale),
    ]
