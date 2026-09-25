"""Sportmonks normalization helpers.

The live API client will be added once a token is available. Keeping the
normalizer separate makes fixture tests deterministic and lets us archive raw
provider payloads for auditability.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from thinkinginbets.feeds.base import MatchState


def normalize_sportmonks_livescore(payload: Mapping[str, Any]) -> MatchState:
    participant_names = _participant_names(payload)
    scores = _scoreline(payload)
    observed_at = _parse_observed_at(payload.get("updated_at"))

    return MatchState(
        provider="sportmonks",
        provider_match_id=str(payload.get("id", "")),
        home_team=participant_names.get("home", "home"),
        away_team=participant_names.get("away", "away"),
        minute=int(payload.get("minute") or payload.get("time", {}).get("minute") or 0),
        home_goals=scores["home"],
        away_goals=scores["away"],
        status=str(payload.get("state", {}).get("name") or payload.get("status") or "unknown"),
        observed_at=observed_at,
        statistics={},
    )


def _participant_names(payload: Mapping[str, Any]) -> dict[str, str]:
    names = {"home": "home", "away": "away"}
    for participant in payload.get("participants", []) or []:
        meta = participant.get("meta", {})
        location = meta.get("location")
        if location in names:
            names[location] = str(participant.get("name", names[location]))
    return names


def _scoreline(payload: Mapping[str, Any]) -> dict[str, int]:
    scores = {"home": 0, "away": 0}
    for score in payload.get("scores", []) or []:
        description = score.get("description")
        participant = score.get("score", {}).get("participant")
        goals = score.get("score", {}).get("goals")
        if description == "CURRENT" and participant in scores and goals is not None:
            scores[participant] = int(goals)
    return scores


def _parse_observed_at(value: object) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)
