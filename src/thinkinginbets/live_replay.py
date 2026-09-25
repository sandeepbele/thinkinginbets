"""Replay in-play match scenarios through the paper trading engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from thinkinginbets.domain import MarketSnapshot, Order
from thinkinginbets.engine import TradingEngine
from thinkinginbets.feeds.base import MatchState
from thinkinginbets.models.base import MatchContext, MatchProbabilityModel


@dataclass(frozen=True)
class ReplayTick:
    state: MatchState
    market: MarketSnapshot


@dataclass
class ReplayTickResult:
    minute: int
    score: str
    filled_orders: list[Order] = field(default_factory=list)


@dataclass
class ReplayResult:
    ticks: list[ReplayTickResult] = field(default_factory=list)

    @property
    def fill_count(self) -> int:
        return sum(len(tick.filled_orders) for tick in self.ticks)


def replay_live_scenario(
    ticks: list[ReplayTick],
    *,
    model: MatchProbabilityModel,
    engine: TradingEngine,
) -> ReplayResult:
    result = ReplayResult()
    for tick in ticks:
        probabilities = model.predict(
            MatchContext(
                home_team=tick.state.home_team,
                away_team=tick.state.away_team,
                minute=tick.state.minute,
                home_goals=tick.state.home_goals,
                away_goals=tick.state.away_goals,
                features=tick.state.statistics,
            )
        )
        report = engine.on_tick(snapshot=tick.market, probabilities=probabilities)
        result.ticks.append(
            ReplayTickResult(
                minute=tick.state.minute,
                score=f"{tick.state.home_goals}-{tick.state.away_goals}",
                filled_orders=report.filled_orders,
            )
        )
    return result
