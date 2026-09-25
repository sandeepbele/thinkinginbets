"""ESPN public scoreboard normalization helpers.

ESPN's soccer endpoints are useful as a no-key backup, but they are not an
officially supported API contract. Use them as fallback/paper inputs, not as
the sole source for live capital allocation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Any, Iterable, Mapping

from thinkinginbets.feeds.base import MatchState


def normalize_espn_scoreboard_event(payload: Mapping[str, Any]) -> MatchState:
    competition = (payload.get("competitions") or [{}])[0]
    competitors = competition.get("competitors") or []
    by_home_away = {
        competitor.get("homeAway"): competitor for competitor in competitors if competitor.get("homeAway")
    }
    home = by_home_away.get("home", {})
    away = by_home_away.get("away", {})
    status = payload.get("status", {}).get("type", {})

    return MatchState(
        provider="espn_public",
        provider_match_id=str(payload.get("id", "")),
        home_team=str(home.get("team", {}).get("displayName", "home")),
        away_team=str(away.get("team", {}).get("displayName", "away")),
        minute=_minute_from_status(payload.get("status", {})),
        home_goals=_score(home),
        away_goals=_score(away),
        status=str(status.get("description") or status.get("name") or "unknown"),
        observed_at=datetime.now(timezone.utc),
        statistics=_team_statistics(home, away),
    )


def fetch_espn_scoreboard(
    *,
    league: str = "fifa.world",
    dates: str | None = None,
    limit: int = 50,
    timeout_seconds: int = 10,
) -> list[MatchState]:
    """Fetch and normalize ESPN's public soccer scoreboard endpoint.

    This endpoint is public and no-key, but undocumented. The caller should
    cache responses and poll politely.
    """

    query: dict[str, str | int] = {"limit": limit}
    if dates:
        query["dates"] = dates
    url = (
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?"
        f"{urlencode(query)}"
    )
    request = Request(url, headers={"User-Agent": "thinkinginbets/0.1"})
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return [normalize_espn_scoreboard_event(event) for event in payload.get("events", [])]


def _score(competitor: Mapping[str, Any]) -> int:
    try:
        return int(competitor.get("score") or 0)
    except (TypeError, ValueError):
        return 0


def _minute_from_status(status: Mapping[str, Any]) -> int:
    display_clock = str(status.get("displayClock") or "")
    if "'" in display_clock:
        display_clock = display_clock.split("'", 1)[0]
    if ":" in display_clock:
        display_clock = display_clock.split(":", 1)[0]
    try:
        return int(float(display_clock))
    except ValueError:
        return 0


def _team_statistics(home: Mapping[str, Any], away: Mapping[str, Any]) -> dict[str, float]:
    return {
        **_prefixed_statistics("home", home.get("statistics") or []),
        **_prefixed_statistics("away", away.get("statistics") or []),
    }


def _prefixed_statistics(prefix: str, stats: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for stat in stats:
        name = stat.get("name")
        if not isinstance(name, str):
            continue
        value = _float_or_none(stat.get("displayValue"))
        if value is not None:
            normalized[f"{prefix}_{name}"] = value
    return normalized


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip().replace("%", ""))
    except ValueError:
        return None
