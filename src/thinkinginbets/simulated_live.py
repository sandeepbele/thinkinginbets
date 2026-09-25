"""Synthetic live scenarios for strategy development."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from thinkinginbets.domain import MarketSnapshot, OutcomeQuote
from thinkinginbets.feeds.base import MatchState
from thinkinginbets.live_replay import ReplayTick


def draw_then_home_goal_scenario() -> list[ReplayTick]:
    """Scenario where draw looks attractive, then the home side scores."""

    event_time = datetime(2026, 6, 20, 19, 0, tzinfo=timezone.utc)
    observed = datetime(2026, 6, 20, 19, 5, tzinfo=timezone.utc)
    raw_ticks = [
        (12, 0, 0, 44, 26, 42, 51, 0, 0, 1, 1, "0-0 low event start"),
        (35, 0, 0, 42, 32, 40, 52, 1, 1, 2, 2, "0-0 draw pressure rising"),
        (56, 1, 0, 67, 20, 13, 61, 4, 1, 5, 2, "home goal and pressure"),
        (72, 1, 0, 74, 15, 11, 64, 6, 2, 7, 2, "home still dominant"),
    ]

    ticks: list[ReplayTick] = []
    for index, raw in enumerate(raw_ticks):
        (
            minute,
            home_goals,
            away_goals,
            home_ask,
            draw_ask,
            away_ask,
            home_possession,
            home_sot,
            away_sot,
            home_corners,
            away_corners,
            status,
        ) = raw
        state = MatchState(
            provider="synthetic",
            provider_match_id="draw-then-home-goal",
            home_team="Norway",
            away_team="Senegal",
            minute=minute,
            home_goals=home_goals,
            away_goals=away_goals,
            status=status,
            observed_at=observed + timedelta(minutes=minute),
            statistics={
                "home_possessionPct": float(home_possession),
                "away_possessionPct": float(100 - home_possession),
                "home_shotsOnTarget": float(home_sot),
                "away_shotsOnTarget": float(away_sot),
                "home_wonCorners": float(home_corners),
                "away_wonCorners": float(away_corners),
            },
        )
        market = MarketSnapshot(
            market_id="synthetic-norway-senegal",
            title="Synthetic Norway vs Senegal",
            event_time=event_time,
            observed_at=observed + timedelta(minutes=minute, seconds=index),
            quotes={
                "home": OutcomeQuote("home", bid_cents=home_ask - 2, ask_cents=home_ask),
                "draw": OutcomeQuote("draw", bid_cents=draw_ask - 2, ask_cents=draw_ask),
                "away": OutcomeQuote("away", bid_cents=away_ask - 2, ask_cents=away_ask),
            },
            fee_cents_per_contract=1,
        )
        ticks.append(ReplayTick(state=state, market=market))
    return ticks
