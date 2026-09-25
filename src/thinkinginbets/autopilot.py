"""Autonomous paper-trading orchestration.

This is the control-plane shape for unattended operation. It intentionally
starts with paper execution and hard feed freshness checks.
"""

from __future__ import annotations

from dataclasses import dataclass

from thinkinginbets.engine import TradingEngine, TickReport
from thinkinginbets.feeds.base import MatchState
from thinkinginbets.feeds.staleness import FeedFreshnessPolicy
from thinkinginbets.models.base import MatchContext, MatchProbabilityModel
from thinkinginbets.domain import MarketSnapshot


@dataclass
class AutonomousMatchTrader:
    model: MatchProbabilityModel
    engine: TradingEngine
    freshness_policy: FeedFreshnessPolicy

    def on_state_and_market(self, state: MatchState, snapshot: MarketSnapshot) -> TickReport:
        self.freshness_policy.validate(state)
        context = MatchContext(
            home_team=state.home_team,
            away_team=state.away_team,
            minute=state.minute,
            home_goals=state.home_goals,
            away_goals=state.away_goals,
            features=state.statistics,
        )
        probabilities = self.model.predict(context)
        return self.engine.on_tick(snapshot=snapshot, probabilities=probabilities)
