"""Adapter for trained penaltyblog football models.

This module keeps penaltyblog optional. Install with:

    pip install -e ".[models]"

The adapter accepts a trained penaltyblog model object and normalizes its
prediction output into the home/draw/away probabilities used by the trading
engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Mapping

from thinkinginbets.domain import ModelProbability
from thinkinginbets.models.base import MatchContext


def ensure_penaltyblog_available() -> None:
    try:
        import_module("penaltyblog")
    except ImportError as exc:
        raise RuntimeError('install model extras with: pip install -e ".[models]"') from exc


@dataclass(frozen=True)
class PenaltyblogModelAdapter:
    """Wrap a trained penaltyblog model with our project model interface."""

    trained_model: Any
    rationale: str = "penaltyblog model"

    def predict(self, context: MatchContext) -> list[ModelProbability]:
        raw_prediction = self.trained_model.predict(context.home_team, context.away_team)
        home, draw, away = _extract_home_draw_away(raw_prediction)
        return [
            ModelProbability("home", home, self.rationale),
            ModelProbability("draw", draw, self.rationale),
            ModelProbability("away", away, self.rationale),
        ]


def _extract_home_draw_away(raw_prediction: Any) -> tuple[float, float, float]:
    """Normalize the common penaltyblog prediction shapes without binding tightly."""

    if isinstance(raw_prediction, Mapping):
        return (
            _probability_from_mapping(raw_prediction, "home_win", "home"),
            _probability_from_mapping(raw_prediction, "draw"),
            _probability_from_mapping(raw_prediction, "away_win", "away"),
        )

    return (
        float(getattr(raw_prediction, "home_win")),
        float(getattr(raw_prediction, "draw")),
        float(getattr(raw_prediction, "away_win")),
    )


def _probability_from_mapping(values: Mapping[str, Any], *keys: str) -> float:
    for key in keys:
        if key in values:
            return float(values[key])
    expected = ", ".join(keys)
    raise ValueError(f"prediction mapping is missing one of: {expected}")
