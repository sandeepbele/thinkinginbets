"""Paper bet journal and evaluation helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable, Optional

from thinkinginbets.feeds.base import MatchState
from thinkinginbets.models.base import MatchContext
from thinkinginbets.models.team_strength import TeamStrengthPriorModel


PENDING_STATUSES = {"scheduled", "pre-game", "pre game", "not started"}
FINAL_STATUSES = {"full time", "ft", "final", "final/ot", "full-time"}


@dataclass(frozen=True)
class PaperBet:
    bet_id: str
    provider: str
    provider_match_id: str
    placed_at: str
    home_team: str
    away_team: str
    predicted_outcome: str
    price_cents: int
    stake_cents: int
    model_probability: float
    rationale: str
    status: str = "pending"
    settled_at: Optional[str] = None
    realized_pnl_cents: Optional[int] = None
    final_score: Optional[str] = None


def propose_paper_bets(
    states: Iterable[MatchState],
    *,
    stake_cents: int,
    min_probability: float,
    max_bets: int,
    model: Optional[TeamStrengthPriorModel] = None,
) -> list[PaperBet]:
    predictor = model or TeamStrengthPriorModel()
    proposed: list[PaperBet] = []
    placed_at = datetime.now(timezone.utc).isoformat()

    for state in states:
        if _normalized_status(state.status) not in PENDING_STATUSES:
            continue

        probabilities = predictor.predict(
            MatchContext(home_team=state.home_team, away_team=state.away_team)
        )
        best = max(probabilities, key=lambda probability: probability.probability)
        if best.probability < min_probability:
            continue

        proposed.append(
            PaperBet(
                bet_id=f"{state.provider}:{state.provider_match_id}:{placed_at}",
                provider=state.provider,
                provider_match_id=state.provider_match_id,
                placed_at=placed_at,
                home_team=state.home_team,
                away_team=state.away_team,
                predicted_outcome=best.outcome_id,
                price_cents=best.fair_value_cents(),
                stake_cents=stake_cents,
                model_probability=round(best.probability, 4),
                rationale=best.rationale,
            )
        )

        if len(proposed) >= max_bets:
            break

    return proposed


def append_bets(path: Path, bets: Iterable[PaperBet]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for bet in bets:
            handle.write(json.dumps(asdict(bet), sort_keys=True) + "\n")


def read_bets(path: Path) -> list[PaperBet]:
    if not path.exists():
        return []
    bets: list[PaperBet] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                bets.append(PaperBet(**json.loads(line)))
    return bets


def evaluate_pending_bets(path: Path, states: Iterable[MatchState]) -> list[PaperBet]:
    states_by_id = {state.provider_match_id: state for state in states}
    evaluated: list[PaperBet] = []

    for bet in read_bets(path):
        if bet.status != "pending":
            evaluated.append(bet)
            continue

        state = states_by_id.get(bet.provider_match_id)
        if state is None or _normalized_status(state.status) not in FINAL_STATUSES:
            evaluated.append(bet)
            continue

        actual = _actual_outcome(state)
        won = actual == bet.predicted_outcome
        pnl = bet.stake_cents * (100 - bet.price_cents) // bet.price_cents if won else -bet.stake_cents
        evaluated.append(
            PaperBet(
                **{
                    **asdict(bet),
                    "status": "won" if won else "lost",
                    "settled_at": datetime.now(timezone.utc).isoformat(),
                    "realized_pnl_cents": pnl,
                    "final_score": f"{state.home_goals}-{state.away_goals}",
                }
            )
        )

    _rewrite_bets(path, evaluated)
    return evaluated


def _rewrite_bets(path: Path, bets: Iterable[PaperBet]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for bet in bets:
            handle.write(json.dumps(asdict(bet), sort_keys=True) + "\n")


def _actual_outcome(state: MatchState) -> str:
    if state.home_goals > state.away_goals:
        return "home"
    if state.away_goals > state.home_goals:
        return "away"
    return "draw"


def _normalized_status(status: str) -> str:
    return status.strip().lower()
