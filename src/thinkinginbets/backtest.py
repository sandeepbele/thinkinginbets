"""Historical paper-bet backtests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from thinkinginbets.feeds.base import MatchState
from thinkinginbets.models.base import MatchContext
from thinkinginbets.models.team_strength import TeamStrengthPriorModel
from thinkinginbets.paper_bets import FINAL_STATUSES


@dataclass(frozen=True)
class BacktestBet:
    provider_match_id: str
    home_team: str
    away_team: str
    predicted_outcome: str
    actual_outcome: str
    model_probability: float
    price_cents: int
    stake_cents: int
    realized_pnl_cents: int
    final_score: str
    rationale: str

    @property
    def won(self) -> bool:
        return self.predicted_outcome == self.actual_outcome


@dataclass(frozen=True)
class BacktestReport:
    bets: list[BacktestBet]

    @property
    def total_staked_cents(self) -> int:
        return sum(bet.stake_cents for bet in self.bets)

    @property
    def total_pnl_cents(self) -> int:
        return sum(bet.realized_pnl_cents for bet in self.bets)

    @property
    def wins(self) -> int:
        return sum(1 for bet in self.bets if bet.won)

    @property
    def roi(self) -> float:
        if self.total_staked_cents == 0:
            return 0.0
        return self.total_pnl_cents / self.total_staked_cents


def run_backtest(
    states: Iterable[MatchState],
    *,
    stake_cents: int,
    min_probability: float,
    model: TeamStrengthPriorModel | None = None,
) -> BacktestReport:
    predictor = model or TeamStrengthPriorModel()
    bets: list[BacktestBet] = []

    for state in states:
        if state.status.strip().lower() not in FINAL_STATUSES:
            continue

        probabilities = predictor.predict(
            MatchContext(home_team=state.home_team, away_team=state.away_team)
        )
        best = max(probabilities, key=lambda probability: probability.probability)
        if best.probability < min_probability:
            continue

        actual = _actual_outcome(state)
        price_cents = best.fair_value_cents()
        won = best.outcome_id == actual
        pnl = stake_cents * (100 - price_cents) // price_cents if won else -stake_cents
        bets.append(
            BacktestBet(
                provider_match_id=state.provider_match_id,
                home_team=state.home_team,
                away_team=state.away_team,
                predicted_outcome=best.outcome_id,
                actual_outcome=actual,
                model_probability=round(best.probability, 4),
                price_cents=price_cents,
                stake_cents=stake_cents,
                realized_pnl_cents=pnl,
                final_score=f"{state.home_goals}-{state.away_goals}",
                rationale=best.rationale,
            )
        )

    return BacktestReport(bets=bets)


def run_no_market_price_audit(
    states: Iterable[MatchState],
    *,
    min_probability: float,
    model: TeamStrengthPriorModel | None = None,
) -> list[str]:
    """Explain which winner picks are forecasts, not valid trades."""

    predictor = model or TeamStrengthPriorModel()
    findings: list[str] = []
    for state in states:
        if state.status.strip().lower() not in FINAL_STATUSES:
            continue

        probabilities = predictor.predict(
            MatchContext(home_team=state.home_team, away_team=state.away_team)
        )
        best = max(probabilities, key=lambda probability: probability.probability)
        if best.probability < min_probability:
            continue

        findings.append(
            f"{state.home_team} vs {state.away_team}: model likes {best.outcome_id} "
            f"at {best.fair_value_cents()}c, but no historical market price was supplied; "
            "this is a forecast, not an edge-qualified trade"
        )
    return findings


def _actual_outcome(state: MatchState) -> str:
    if state.home_goals > state.away_goals:
        return "home"
    if state.away_goals > state.home_goals:
        return "away"
    return "draw"
