"""API-Football normalization helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from thinkinginbets.feeds.base import MatchState


def normalize_api_football_fixture(payload: Mapping[str, Any]) -> MatchState:
    fixture = payload.get("fixture", {})
    teams = payload.get("teams", {})
    goals = payload.get("goals", {})
    status = fixture.get("status", {})

    return MatchState(
        provider="api_football",
        provider_match_id=str(fixture.get("id", "")),
        home_team=str(teams.get("home", {}).get("name", "home")),
        away_team=str(teams.get("away", {}).get("name", "away")),
        minute=int(status.get("elapsed") or 0),
        home_goals=int(goals.get("home") or 0),
        away_goals=int(goals.get("away") or 0),
        status=str(status.get("long") or status.get("short") or "unknown"),
        observed_at=datetime.now(timezone.utc),
        statistics={},
    )
