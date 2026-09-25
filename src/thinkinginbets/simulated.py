"""Small deterministic feed for local smoke tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterator

from thinkinginbets.domain import MarketSnapshot, ModelProbability, OutcomeQuote


def iter_world_cup_snapshots() -> Iterator[tuple[MarketSnapshot, list[ModelProbability]]]:
    event_time = datetime(2026, 6, 20, 19, 0, tzinfo=timezone.utc)
    base_observed_at = datetime(2026, 6, 20, 18, 0, tzinfo=timezone.utc)

    ticks = [
        (42, 28, 30, 0.51, 0.25, 0.24, "pre-match prior likes Team A"),
        (46, 27, 27, 0.55, 0.23, 0.22, "Team A pressure is rising"),
        (57, 23, 20, 0.63, 0.19, 0.18, "Team A scored first"),
        (48, 29, 23, 0.49, 0.30, 0.21, "Team B equalized; draw risk increased"),
    ]

    for index, (home, draw, away, p_home, p_draw, p_away, note) in enumerate(ticks):
        snapshot = MarketSnapshot(
            market_id="wc-2026-team-a-v-team-b",
            title="World Cup 2026: Team A vs Team B winner",
            event_time=event_time,
            observed_at=base_observed_at + timedelta(minutes=15 * index),
            quotes={
                "home": OutcomeQuote("home", bid_cents=max(home - 2, 1), ask_cents=home),
                "draw": OutcomeQuote("draw", bid_cents=max(draw - 2, 1), ask_cents=draw),
                "away": OutcomeQuote("away", bid_cents=max(away - 2, 1), ask_cents=away),
            },
            fee_cents_per_contract=1,
        )
        probabilities = [
            ModelProbability("home", p_home, note),
            ModelProbability("draw", p_draw, note),
            ModelProbability("away", p_away, note),
        ]
        yield snapshot, probabilities
