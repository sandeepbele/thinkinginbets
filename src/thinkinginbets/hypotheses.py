"""Repeatable replay hypothesis checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlencode

from thinkinginbets.fees import KalshiFeeModel
from thinkinginbets.kalshi_espn_replay import (
    ESPN_SUMMARY_URL,
    PublicReplayConfig,
    _build_match_states,
    _build_replay_ticks,
    _competitor_by_home_away,
    _fetch_candles,
    _fetch_json,
    _summary_actual_outcome,
    run_public_kalshi_espn_replay,
)


@dataclass(frozen=True)
class LateUnderdogBet:
    match_label: str
    band: str
    underdog: str
    actual_outcome: str
    minute: int
    score: str
    ask_cents: int
    quantity: int
    fee_cents: int
    pnl_cents: int


@dataclass(frozen=True)
class LateUnderdogBucket:
    band: str
    fills: int = 0
    contracts: int = 0
    entry_notional_cents: int = 0
    fees_cents: int = 0
    pnl_cents: int = 0

    @property
    def average_entry_cents(self) -> float:
        if self.contracts == 0:
            return 0.0
        return self.entry_notional_cents / self.contracts

    @property
    def pnl_per_contract_cents(self) -> float:
        if self.contracts == 0:
            return 0.0
        return self.pnl_cents / self.contracts


@dataclass(frozen=True)
class LateUnderdogReport:
    bets: list[LateUnderdogBet]
    buckets: list[LateUnderdogBucket]

    @property
    def total_pnl_cents(self) -> int:
        return sum(bet.pnl_cents for bet in self.bets)


@dataclass(frozen=True)
class DoubleChanceBet:
    match_label: str
    band: str
    underdog: str
    favorite: str
    actual_outcome: str
    minute: int
    score: str
    underdog_ask_cents: int
    draw_ask_cents: int
    quantity: int
    fee_cents: int
    cost_cents: int
    pnl_cents: int


@dataclass(frozen=True)
class DoubleChanceBucket:
    band: str
    fills: int = 0
    contracts: int = 0
    cost_cents: int = 0
    combo_price_cents: int = 0
    fees_cents: int = 0
    pnl_cents: int = 0

    @property
    def average_combo_price_cents(self) -> float:
        if self.fills == 0:
            return 0.0
        return self.combo_price_cents / self.fills

    @property
    def roi_on_cost(self) -> float:
        if self.cost_cents == 0:
            return 0.0
        return self.pnl_cents / self.cost_cents


@dataclass(frozen=True)
class DoubleChanceReport:
    bets: list[DoubleChanceBet]
    buckets: list[DoubleChanceBucket]

    @property
    def total_pnl_cents(self) -> int:
        return sum(bet.pnl_cents for bet in self.bets)

    @property
    def total_cost_cents(self) -> int:
        return sum(bet.cost_cents for bet in self.bets)


@dataclass(frozen=True)
class FavoriteStressRow:
    match_label: str
    actual_outcome: str
    favorite: str
    base_pnl_cents: int
    favorite_win_pnl_cents: int

    @property
    def stress_delta_cents(self) -> int:
        return self.favorite_win_pnl_cents - self.base_pnl_cents


@dataclass(frozen=True)
class FavoriteStressReport:
    rows: list[FavoriteStressRow]

    @property
    def base_total_pnl_cents(self) -> int:
        return sum(row.base_pnl_cents for row in self.rows)

    @property
    def favorite_win_total_pnl_cents(self) -> int:
        return sum(row.favorite_win_pnl_cents for row in self.rows)

    @property
    def stress_delta_cents(self) -> int:
        return self.favorite_win_total_pnl_cents - self.base_total_pnl_cents


@dataclass(frozen=True)
class OddsDoubleChanceBet:
    league: str
    event_id: str
    match_label: str
    underdog: str
    favorite: str
    actual_outcome: str
    underdog_price_cents: float
    draw_price_cents: float
    combo_price_cents: float
    pnl_cents: float


@dataclass(frozen=True)
class OddsDoubleChanceReport:
    bets: list[OddsDoubleChanceBet]
    events_seen: int
    events_with_odds: int
    events_qualified: int

    @property
    def total_pnl_cents(self) -> float:
        return sum(bet.pnl_cents for bet in self.bets)

    @property
    def total_cost_cents(self) -> float:
        return sum(bet.combo_price_cents for bet in self.bets)

    @property
    def roi_on_cost(self) -> float:
        if self.total_cost_cents == 0:
            return 0.0
        return self.total_pnl_cents / self.total_cost_cents


def analyze_late_underdog(
    configs: list[PublicReplayConfig],
    *,
    quantity: int = 5,
) -> LateUnderdogReport:
    """Buy the pre-match underdog once per late minute band and settle it."""

    fee_model = KalshiFeeModel()
    bets: list[LateUnderdogBet] = []
    for config in configs:
        summary = _fetch_json(ESPN_SUMMARY_URL.format(event_id=config.espn_event_id))
        actual_outcome = _completed_summary_actual_outcome(summary)
        if actual_outcome is None:
            continue

        ticks = _build_replay_ticks(
            config,
            _build_match_states(summary, config),
            {
                "home": _fetch_candles(
                    config.kalshi_event_ticker,
                    config.home_ticker,
                    config.start_ts,
                    config.end_ts,
                ),
                "away": _fetch_candles(
                    config.kalshi_event_ticker,
                    config.away_ticker,
                    config.start_ts,
                    config.end_ts,
                ),
                "draw": _fetch_candles(
                    config.kalshi_event_ticker,
                    config.draw_ticker,
                    config.start_ts,
                    config.end_ts,
                ),
            },
        )
        if not ticks:
            continue

        underdog = _underdog_from_first_tick(ticks[0].market.quotes)
        seen_bands: set[str] = set()
        for tick in ticks:
            band = _late_band(tick.state.minute)
            if band is None or band in seen_bands:
                continue
            quote = tick.market.quotes[underdog]
            if quote.ask_cents is None:
                continue

            fee_cents = fee_model.taker_fee_cents(price_cents=quote.ask_cents, quantity=quantity)
            settlement_cents = 100 if actual_outcome == underdog else 0
            pnl_cents = (settlement_cents - quote.ask_cents) * quantity - fee_cents
            bets.append(
                LateUnderdogBet(
                    match_label=f"{config.home_team} vs {config.away_team}",
                    band=band,
                    underdog=underdog,
                    actual_outcome=actual_outcome,
                    minute=tick.state.minute,
                    score=f"{tick.state.home_goals}-{tick.state.away_goals}",
                    ask_cents=quote.ask_cents,
                    quantity=quantity,
                    fee_cents=fee_cents,
                    pnl_cents=pnl_cents,
                )
            )
            seen_bands.add(band)

    return LateUnderdogReport(bets=bets, buckets=_bucket_late_underdog_bets(bets))


def analyze_double_chance(
    configs: list[PublicReplayConfig],
    *,
    quantity: int = 5,
    max_combo_price_cents: int | None = None,
    require_favorite_not_leading: bool = False,
) -> DoubleChanceReport:
    """Buy underdog plus draw once per late minute band and settle the basket."""

    fee_model = KalshiFeeModel()
    bets: list[DoubleChanceBet] = []
    for config in configs:
        summary = _fetch_json(ESPN_SUMMARY_URL.format(event_id=config.espn_event_id))
        actual_outcome = _completed_summary_actual_outcome(summary)
        if actual_outcome is None:
            continue

        ticks = _ticks_for_config(config, summary)
        if not ticks:
            continue

        underdog = _underdog_from_first_tick(ticks[0].market.quotes)
        favorite = "away" if underdog == "home" else "home"
        seen_bands: set[str] = set()
        for tick in ticks:
            band = _late_band(tick.state.minute)
            if band is None or band in seen_bands:
                continue
            underdog_ask = tick.market.quotes[underdog].ask_cents
            draw_ask = tick.market.quotes["draw"].ask_cents
            if underdog_ask is None or draw_ask is None:
                continue
            combo_price_cents = underdog_ask + draw_ask
            if max_combo_price_cents is not None and combo_price_cents > max_combo_price_cents:
                continue
            if require_favorite_not_leading and _favorite_is_leading(
                favorite=favorite,
                home_goals=tick.state.home_goals,
                away_goals=tick.state.away_goals,
            ):
                continue

            underdog_fee = fee_model.taker_fee_cents(price_cents=underdog_ask, quantity=quantity)
            draw_fee = fee_model.taker_fee_cents(price_cents=draw_ask, quantity=quantity)
            fee_cents = underdog_fee + draw_fee
            cost_cents = (underdog_ask + draw_ask) * quantity + fee_cents
            underdog_pnl = ((100 if actual_outcome == underdog else 0) - underdog_ask) * quantity
            draw_pnl = ((100 if actual_outcome == "draw" else 0) - draw_ask) * quantity
            pnl_cents = underdog_pnl + draw_pnl - fee_cents
            bets.append(
                DoubleChanceBet(
                    match_label=f"{config.home_team} vs {config.away_team}",
                    band=band,
                    underdog=underdog,
                    favorite=favorite,
                    actual_outcome=actual_outcome,
                    minute=tick.state.minute,
                    score=f"{tick.state.home_goals}-{tick.state.away_goals}",
                    underdog_ask_cents=underdog_ask,
                    draw_ask_cents=draw_ask,
                    quantity=quantity,
                    fee_cents=fee_cents,
                    cost_cents=cost_cents,
                    pnl_cents=pnl_cents,
                )
            )
            seen_bands.add(band)

    return DoubleChanceReport(bets=bets, buckets=_bucket_double_chance_bets(bets))


def _favorite_is_leading(*, favorite: str, home_goals: int, away_goals: int) -> bool:
    if favorite == "home":
        return home_goals > away_goals
    return away_goals > home_goals


def analyze_favorite_stress(configs: list[PublicReplayConfig]) -> FavoriteStressReport:
    """Resettle the default strategy fills as if each first-tick favorite won."""

    rows: list[FavoriteStressRow] = []
    for config in configs:
        summary = _fetch_json(ESPN_SUMMARY_URL.format(event_id=config.espn_event_id))
        ticks = _ticks_for_config(config, summary)
        if not ticks:
            continue
        underdog = _underdog_from_first_tick(ticks[0].market.quotes)
        favorite = "away" if underdog == "home" else "home"

        report = run_public_kalshi_espn_replay(config)
        favorite_win_pnl_cents = sum(
            _terminal_pnl_cents(
                outcome_id=fill.outcome_id,
                side=fill.side,
                price_cents=fill.price_cents,
                quantity=fill.quantity,
                fee_cents=fill.fee_cents,
                settlement_outcome=favorite,
            )
            for fill in report.fill_diagnostics
        )
        rows.append(
            FavoriteStressRow(
                match_label=report.label,
                actual_outcome=report.actual_outcome,
                favorite=favorite,
                base_pnl_cents=report.total_pnl_cents,
                favorite_win_pnl_cents=favorite_win_pnl_cents,
            )
        )
    return FavoriteStressReport(rows=rows)


def analyze_odds_double_chance(
    *,
    league: str,
    dates: str,
    limit: int = 100,
    max_combo_price_cents: float | None = None,
) -> OddsDoubleChanceReport:
    """Test underdog plus draw using ESPN/DraftKings moneylines as prices."""

    scoreboard_url = (
        f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?"
        f"{urlencode({'dates': dates, 'limit': limit})}"
    )
    scoreboard = _fetch_json(scoreboard_url)
    bets: list[OddsDoubleChanceBet] = []
    events_seen = 0
    events_with_odds = 0
    events_qualified = 0

    for event in scoreboard.get("events", []):
        events_seen += 1
        summary_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/summary?event={event['id']}"
        summary = _fetch_json(summary_url)
        odds = _draftkings_odds(summary)
        actual_outcome = _completed_summary_actual_outcome(summary)
        teams = _summary_team_labels(summary)
        if odds is None or actual_outcome is None or teams is None:
            continue
        events_with_odds += 1

        home_price = _moneyline_to_price_cents(odds["home_moneyline"])
        away_price = _moneyline_to_price_cents(odds["away_moneyline"])
        draw_price = _moneyline_to_price_cents(odds["draw_moneyline"])
        if home_price is None or away_price is None or draw_price is None:
            continue

        if home_price < away_price:
            underdog = "home"
            favorite = "away"
            underdog_price = home_price
        else:
            underdog = "away"
            favorite = "home"
            underdog_price = away_price

        combo_price = underdog_price + draw_price
        if max_combo_price_cents is not None and combo_price > max_combo_price_cents:
            continue
        events_qualified += 1

        payout = 100.0 if actual_outcome in {underdog, "draw"} else 0.0
        bets.append(
            OddsDoubleChanceBet(
                league=league,
                event_id=str(event["id"]),
                match_label=f"{teams['home']} vs {teams['away']}",
                underdog=underdog,
                favorite=favorite,
                actual_outcome=actual_outcome,
                underdog_price_cents=underdog_price,
                draw_price_cents=draw_price,
                combo_price_cents=combo_price,
                pnl_cents=payout - combo_price,
            )
        )

    return OddsDoubleChanceReport(
        bets=bets,
        events_seen=events_seen,
        events_with_odds=events_with_odds,
        events_qualified=events_qualified,
    )


def _ticks_for_config(config: PublicReplayConfig, summary):
    return _build_replay_ticks(
        config,
        _build_match_states(summary, config),
        {
            "home": _fetch_candles(
                config.kalshi_event_ticker,
                config.home_ticker,
                config.start_ts,
                config.end_ts,
            ),
            "away": _fetch_candles(
                config.kalshi_event_ticker,
                config.away_ticker,
                config.start_ts,
                config.end_ts,
            ),
            "draw": _fetch_candles(
                config.kalshi_event_ticker,
                config.draw_ticker,
                config.start_ts,
                config.end_ts,
            ),
        },
    )


def _terminal_pnl_cents(
    *,
    outcome_id: str,
    side: str,
    price_cents: int,
    quantity: int,
    fee_cents: int,
    settlement_outcome: str,
) -> int:
    settlement_cents = 100 if outcome_id == settlement_outcome else 0
    if side == "buy":
        return (settlement_cents - price_cents) * quantity - fee_cents
    return (price_cents - settlement_cents) * quantity - fee_cents


def _draftkings_odds(summary: Mapping[str, Any]) -> dict[str, float] | None:
    for odds in summary.get("odds", []):
        provider = odds.get("provider", {})
        if provider.get("name") != "DraftKings":
            continue
        home = odds.get("homeTeamOdds", {})
        away = odds.get("awayTeamOdds", {})
        draw = odds.get("drawOdds", {})
        if "moneyLine" not in home or "moneyLine" not in away or "moneyLine" not in draw:
            return None
        return {
            "home_moneyline": float(home["moneyLine"]),
            "away_moneyline": float(away["moneyLine"]),
            "draw_moneyline": float(draw["moneyLine"]),
        }
    return None


def _summary_team_labels(summary: Mapping[str, Any]) -> dict[str, str] | None:
    competitors = summary.get("header", {}).get("competitions", [{}])[0].get("competitors", [])
    home = _competitor_by_home_away(competitors, "home")
    away = _competitor_by_home_away(competitors, "away")
    if home is None or away is None:
        return None
    return {
        "home": str(home.get("team", {}).get("displayName")),
        "away": str(away.get("team", {}).get("displayName")),
    }


def _completed_summary_actual_outcome(summary: Mapping[str, Any]) -> str | None:
    competition = summary.get("header", {}).get("competitions", [{}])[0]
    status = competition.get("status", {}).get("type", {})
    if not status.get("completed"):
        return None
    return _summary_actual_outcome(summary)


def _moneyline_to_price_cents(moneyline: float) -> float | None:
    if moneyline > 0:
        return 100.0 * (100.0 / (moneyline + 100.0))
    if moneyline < 0:
        return 100.0 * ((-moneyline) / ((-moneyline) + 100.0))
    return None


def _underdog_from_first_tick(quotes) -> str:
    home_ask = quotes["home"].ask_cents
    away_ask = quotes["away"].ask_cents
    if home_ask is None or away_ask is None:
        raise ValueError("missing home/away ask for underdog classification")
    return "home" if home_ask < away_ask else "away"


def _late_band(minute: int) -> str | None:
    if 46 <= minute <= 60:
        return "46-60"
    if 61 <= minute <= 75:
        return "61-75"
    if 76 <= minute <= 90:
        return "76-90"
    return None


def _bucket_late_underdog_bets(bets: list[LateUnderdogBet]) -> list[LateUnderdogBucket]:
    buckets: dict[str, LateUnderdogBucket] = {}
    for bet in bets:
        previous = buckets.get(bet.band, LateUnderdogBucket(band=bet.band))
        buckets[bet.band] = LateUnderdogBucket(
            band=bet.band,
            fills=previous.fills + 1,
            contracts=previous.contracts + bet.quantity,
            entry_notional_cents=previous.entry_notional_cents + bet.ask_cents * bet.quantity,
            fees_cents=previous.fees_cents + bet.fee_cents,
            pnl_cents=previous.pnl_cents + bet.pnl_cents,
        )
    return [buckets[band] for band in sorted(buckets)]


def _bucket_double_chance_bets(bets: list[DoubleChanceBet]) -> list[DoubleChanceBucket]:
    buckets: dict[str, DoubleChanceBucket] = {}
    for bet in bets:
        previous = buckets.get(bet.band, DoubleChanceBucket(band=bet.band))
        buckets[bet.band] = DoubleChanceBucket(
            band=bet.band,
            fills=previous.fills + 1,
            contracts=previous.contracts + bet.quantity * 2,
            cost_cents=previous.cost_cents + bet.cost_cents,
            combo_price_cents=previous.combo_price_cents
            + bet.underdog_ask_cents
            + bet.draw_ask_cents,
            fees_cents=previous.fees_cents + bet.fee_cents,
            pnl_cents=previous.pnl_cents + bet.pnl_cents,
        )
    return [buckets[band] for band in sorted(buckets)]
