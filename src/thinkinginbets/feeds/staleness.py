"""Feed freshness checks used by autonomous mode."""

from __future__ import annotations

from dataclasses import dataclass

from thinkinginbets.feeds.base import MatchState


@dataclass(frozen=True)
class FeedFreshnessPolicy:
    max_staleness_seconds: int = 20

    def validate(self, state: MatchState) -> None:
        age = state.age_seconds()
        if age > self.max_staleness_seconds:
            raise RuntimeError(
                f"{state.provider} match feed is stale: {age:.1f}s "
                f"> {self.max_staleness_seconds}s"
            )
