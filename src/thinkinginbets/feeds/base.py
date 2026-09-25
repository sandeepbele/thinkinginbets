"""Provider-neutral live match feed types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, Optional, Protocol


class MatchEventType(str, Enum):
    KICKOFF = "kickoff"
    GOAL = "goal"
    CARD = "card"
    SUBSTITUTION = "substitution"
    SHOT = "shot"
    STAT_UPDATE = "stat_update"
    PERIOD_END = "period_end"
    FULL_TIME = "full_time"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MatchEvent:
    provider: str
    provider_event_id: str
    event_type: MatchEventType
    minute: int
    team: Optional[str]
    player: Optional[str]
    description: str
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MatchState:
    provider: str
    provider_match_id: str
    home_team: str
    away_team: str
    minute: int
    home_goals: int
    away_goals: int
    status: str
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    statistics: Mapping[str, float] = field(default_factory=dict)

    def age_seconds(self, now: Optional[datetime] = None) -> float:
        clock = now or datetime.now(timezone.utc)
        return max((clock - self.observed_at).total_seconds(), 0.0)


@dataclass(frozen=True)
class FeedHealth:
    provider: str
    ok: bool
    message: str
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SportsFeedAdapter(Protocol):
    provider_name: str

    async def get_match_state(self, provider_match_id: str) -> MatchState:
        """Return the latest normalized match state."""

    async def health(self) -> FeedHealth:
        """Return a lightweight feed health signal."""
