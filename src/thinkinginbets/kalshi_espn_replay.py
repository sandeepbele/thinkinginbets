"""Replay public ESPN match events against public Kalshi market candles."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from thinkinginbets.domain import Fill, MarketSnapshot, OrderSide, OutcomeQuote, Portfolio
from thinkinginbets.engine import TradingEngine
from thinkinginbets.fees import KalshiFeeModel
from thinkinginbets.feeds.base import MatchState
from thinkinginbets.live_replay import ReplayTick, replay_live_scenario
from thinkinginbets.models.in_play import InPlayHeuristicModel
from thinkinginbets.paper import PaperBroker
from thinkinginbets.risk import RiskLimits, RiskManager
from thinkinginbets.strategy import DisciplinedValueStrategy


ESPN_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={event_id}"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?{query}"
KALSHI_EVENT_URL = "https://api.elections.kalshi.com/trade-api/v2/events/{event_ticker}"
KALSHI_CANDLES_URL = (
    "https://api.elections.kalshi.com/trade-api/v2/series/{series}/markets/{ticker}/candlesticks"
    "?start_ts={start_ts}&end_ts={end_ts}&period_interval=1&include_latest_before_start=true"
)
CACHE_DIR = Path("data/cache/http")


@dataclass(frozen=True)
class PublicReplayConfig:
    espn_event_id: str
    kalshi_event_ticker: str
    start_ts: int
    end_ts: int
    home_ticker: str
    away_ticker: str
    draw_ticker: str
    home_team: str
    away_team: str


@dataclass(frozen=True)
class ReplaySettings:
    initial_cash_cents: int = 10_000
    max_order_notional_cents: int = 250
    max_market_exposure_cents: int = 750
    max_session_loss_cents: int = 600
    quantity: int = 5
    min_edge_cents: int = 4
    max_draw_buy_minute: int = 45
    allow_draw_sells: bool = False


@dataclass(frozen=True)
class FillDiagnostic:
    outcome_id: str
    side: str
    minute: int
    score: str
    price_cents: int
    quantity: int
    fee_cents: int
    terminal_pnl_cents: int


@dataclass(frozen=True)
class PublicReplayReport:
    label: str
    ticks: int
    fills: int
    cash_cents: int
    realized_pnl_cents: int
    settled_cash_cents: int
    total_pnl_cents: int
    total_fee_cents: int
    actual_outcome: str
    lines: list[str]
    fill_diagnostics: list[FillDiagnostic] = field(default_factory=list)


def run_public_kalshi_espn_replay(
    config: PublicReplayConfig,
    settings: ReplaySettings | None = None,
) -> PublicReplayReport:
    replay_settings = settings or ReplaySettings()
    summary = _fetch_json(ESPN_SUMMARY_URL.format(event_id=config.espn_event_id))
    state_by_ts = _build_match_states(summary, config)
    candles = {
        "home": _fetch_candles(config.kalshi_event_ticker, config.home_ticker, config.start_ts, config.end_ts),
        "away": _fetch_candles(config.kalshi_event_ticker, config.away_ticker, config.start_ts, config.end_ts),
        "draw": _fetch_candles(config.kalshi_event_ticker, config.draw_ticker, config.start_ts, config.end_ts),
    }
    ticks = _build_replay_ticks(config, state_by_ts, candles)

    portfolio = Portfolio(cash_cents=replay_settings.initial_cash_cents)
    broker = PaperBroker(portfolio, fee_model=KalshiFeeModel())
    engine = TradingEngine(
        strategy=DisciplinedValueStrategy(
            min_edge_cents=replay_settings.min_edge_cents,
            order_quantity=replay_settings.quantity,
            max_draw_buy_minute=replay_settings.max_draw_buy_minute,
            allow_draw_sells=replay_settings.allow_draw_sells,
        ),
        risk_manager=RiskManager(
            RiskLimits(
                max_order_notional_cents=replay_settings.max_order_notional_cents,
                max_market_exposure_cents=replay_settings.max_market_exposure_cents,
                max_session_loss_cents=replay_settings.max_session_loss_cents,
            )
        ),
        broker=broker,
    )
    replay = replay_live_scenario(ticks, model=InPlayHeuristicModel(), engine=engine)

    lines: list[str] = []
    for tick in replay.ticks:
        if not tick.filled_orders:
            continue
        for order in tick.filled_orders:
            intent = order.intent
            lines.append(
                f"minute={tick.minute} score={tick.score} "
                f"{intent.side.value} {intent.quantity} {intent.outcome_id} "
                f"@ {intent.limit_price_cents}c"
            )

    actual_outcome = _summary_actual_outcome(summary) or (_actual_outcome(ticks[-1].state) if ticks else "unknown")
    fill_diagnostics = [_fill_diagnostic(fill, actual_outcome) for fill in broker.fills]
    settled_cash = _settled_cash(portfolio, actual_outcome)
    return PublicReplayReport(
        label=f"{config.home_team} vs {config.away_team}",
        ticks=len(ticks),
        fills=replay.fill_count,
        cash_cents=portfolio.cash_cents,
        realized_pnl_cents=portfolio.realized_pnl_cents,
        settled_cash_cents=settled_cash,
        total_pnl_cents=settled_cash - replay_settings.initial_cash_cents,
        total_fee_cents=broker.total_fee_cents,
        actual_outcome=actual_outcome,
        lines=lines,
        fill_diagnostics=fill_diagnostics,
    )


def discover_public_replay_configs(*, dates: str, limit: int = 50) -> list[PublicReplayConfig]:
    scoreboard = _fetch_json(ESPN_SCOREBOARD_URL.format(query=urlencode({"dates": dates, "limit": limit})))
    configs: list[PublicReplayConfig] = []
    for event in scoreboard.get("events", []):
        competition = (event.get("competitions") or [{}])[0]
        status = competition.get("status", {}).get("type", {})
        if not status.get("completed"):
            continue

        competitors = competition.get("competitors") or []
        home = _competitor_by_home_away(competitors, "home")
        away = _competitor_by_home_away(competitors, "away")
        if home is None or away is None:
            continue

        event_date = datetime.fromisoformat(str(event["date"]).replace("Z", "+00:00"))
        event_prefix = f"KXWCGAME-{event_date:%y%b%d}".upper()
        kalshi_event_ticker = f"{event_prefix}{_team_abbreviation(home)}{_team_abbreviation(away)}"
        kalshi_event = _fetch_json_or_none(KALSHI_EVENT_URL.format(event_ticker=kalshi_event_ticker))
        if kalshi_event is None:
            continue

        summary = _fetch_json(ESPN_SUMMARY_URL.format(event_id=event["id"]))
        start_ts, end_ts = _summary_time_bounds(summary, event_date)
        market_tickers = _market_tickers_from_kalshi_event(kalshi_event, home, away)
        if market_tickers is None:
            continue

        configs.append(
            PublicReplayConfig(
                espn_event_id=str(event["id"]),
                kalshi_event_ticker=kalshi_event_ticker,
                start_ts=start_ts,
                end_ts=end_ts,
                home_ticker=market_tickers["home"],
                away_ticker=market_tickers["away"],
                draw_ticker=market_tickers["draw"],
                home_team=str(home.get("team", {}).get("displayName")),
                away_team=str(away.get("team", {}).get("displayName")),
            )
        )
    return configs


def _fetch_json(url: str) -> Mapping[str, Any]:
    cached = _read_cached_json(url)
    if cached is not None:
        return cached
    request = Request(url, headers={"User-Agent": "thinkinginbets/0.1"})
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    _write_cached_json(url, payload)
    return payload


def _fetch_json_or_none(url: str) -> Mapping[str, Any] | None:
    try:
        return _fetch_json(url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return None


def _read_cached_json(url: str) -> Mapping[str, Any] | None:
    path = _cache_path(url)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_cached_json(url: str, payload: Mapping[str, Any]) -> None:
    path = _cache_path(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True)


def _cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def _fetch_candles(series: str, ticker: str, start_ts: int, end_ts: int) -> list[Mapping[str, Any]]:
    url = KALSHI_CANDLES_URL.format(
        series=series,
        ticker=ticker,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    return list(_fetch_json(url).get("candlesticks", []))


def _summary_plays(summary: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if summary.get("plays"):
        return list(summary.get("plays", []))
    return list(summary.get("commentary", []))


def _competitor_by_home_away(
    competitors: list[Mapping[str, Any]],
    home_away: str,
) -> Mapping[str, Any] | None:
    for competitor in competitors:
        if competitor.get("homeAway") == home_away:
            return competitor
    return None


def _team_abbreviation(competitor: Mapping[str, Any]) -> str:
    team = competitor.get("team", {})
    return str(team.get("abbreviation") or "").upper().replace(" ", "")


def _summary_time_bounds(summary: Mapping[str, Any], event_date: datetime) -> tuple[int, int]:
    meta = summary.get("meta", {})
    first = _parse_datetime(meta.get("firstPlayWallClock"))
    last = _parse_datetime(meta.get("lastPlayWallClock"))
    if first is None:
        first = event_date
    if last is None:
        last = event_date
    return int(first.timestamp()) - 360, int(last.timestamp())


def _market_tickers_from_kalshi_event(
    kalshi_event: Mapping[str, Any],
    home: Mapping[str, Any],
    away: Mapping[str, Any],
) -> dict[str, str] | None:
    home_name = str(home.get("team", {}).get("displayName"))
    away_name = str(away.get("team", {}).get("displayName"))
    mapped: dict[str, str] = {}
    for market in kalshi_event.get("markets", []):
        label = str(market.get("yes_sub_title") or market.get("subtitle") or market.get("no_sub_title"))
        ticker = str(market.get("ticker"))
        if label == home_name:
            mapped["home"] = ticker
        elif label == away_name:
            mapped["away"] = ticker
        elif label == "Tie":
            mapped["draw"] = ticker
    if {"home", "away", "draw"} <= set(mapped):
        return mapped
    return None


def _build_match_states(
    summary: Mapping[str, Any],
    config: PublicReplayConfig,
) -> dict[int, MatchState]:
    plays = sorted(_summary_plays(summary), key=_play_sort_key)
    seen_play_ids: set[str] = set()
    home_goals = 0
    away_goals = 0
    home_corners = 0
    away_corners = 0
    home_sot = 0
    away_sot = 0
    home_shots = 0
    away_shots = 0
    states: dict[int, MatchState] = {}

    for play in plays:
        wallclock = _play_wallclock(play)
        if wallclock is None:
            continue
        play_id = str(play.get("play", {}).get("id") or play.get("sequence") or "")
        if play_id in seen_play_ids:
            continue
        seen_play_ids.add(play_id)
        play_type = str(play.get("play", {}).get("type", {}).get("type") or "")
        team = str(play.get("play", {}).get("team", {}).get("displayName") or "")

        if "goal" in play_type:
            if team == config.home_team:
                home_goals += 1
            elif team == config.away_team:
                away_goals += 1
        if "corner" in play_type:
            if team == config.home_team:
                home_corners += 1
            elif team == config.away_team:
                away_corners += 1
        if "shot" in play_type or "goal" in play_type:
            if team == config.home_team:
                home_shots += 1
            elif team == config.away_team:
                away_shots += 1
        if "shot-on-target" in play_type or "goal" in play_type:
            if team == config.home_team:
                home_sot += 1
            elif team == config.away_team:
                away_sot += 1

        minute = _minute(play)
        states[int(wallclock.timestamp())] = MatchState(
            provider="espn_public_replay",
            provider_match_id=config.espn_event_id,
            home_team=config.home_team,
            away_team=config.away_team,
            minute=minute,
            home_goals=home_goals,
            away_goals=away_goals,
            status="replay",
            observed_at=wallclock,
            statistics={
                "home_wonCorners": float(home_corners),
                "away_wonCorners": float(away_corners),
                "home_shotsOnTarget": float(home_sot),
                "away_shotsOnTarget": float(away_sot),
                "home_totalShots": float(home_shots),
                "away_totalShots": float(away_shots),
            },
        )

    return states


def _build_replay_ticks(
    config: PublicReplayConfig,
    state_by_ts: dict[int, MatchState],
    candles: Mapping[str, list[Mapping[str, Any]]],
) -> list[ReplayTick]:
    candle_by_ts = {
        outcome: {int(candle["end_period_ts"]): candle for candle in outcome_candles}
        for outcome, outcome_candles in candles.items()
    }
    all_candle_ts = sorted(set(candle_by_ts["home"]) & set(candle_by_ts["away"]) & set(candle_by_ts["draw"]))
    state_ts = sorted(state_by_ts)
    ticks: list[ReplayTick] = []

    for candle_ts in all_candle_ts:
        if candle_ts < config.start_ts or candle_ts > config.end_ts:
            continue
        latest_state_ts = max((ts for ts in state_ts if ts <= candle_ts), default=None)
        if latest_state_ts is None:
            continue
        state = state_by_ts[latest_state_ts]
        quotes = {
            "home": _quote("home", candle_by_ts["home"][candle_ts]),
            "away": _quote("away", candle_by_ts["away"][candle_ts]),
            "draw": _quote("draw", candle_by_ts["draw"][candle_ts]),
        }
        if any(quote.ask_cents in (None, 0, 100) for quote in quotes.values()):
            continue
        ticks.append(
            ReplayTick(
                state=state,
                market=MarketSnapshot(
                    market_id=config.kalshi_event_ticker,
                    title=f"{config.home_team} vs {config.away_team}",
                    event_time=datetime.fromtimestamp(config.start_ts, timezone.utc),
                    observed_at=datetime.fromtimestamp(candle_ts, timezone.utc),
                    quotes=quotes,
                    fee_cents_per_contract=1,
                    metadata={
                        "minute": state.minute,
                        "home_goals": state.home_goals,
                        "away_goals": state.away_goals,
                    },
                ),
            )
        )

    return ticks


def _actual_outcome(state: MatchState) -> str:
    if state.home_goals > state.away_goals:
        return "home"
    if state.away_goals > state.home_goals:
        return "away"
    return "draw"


def _summary_actual_outcome(summary: Mapping[str, Any]) -> str | None:
    competitors = summary.get("header", {}).get("competitions", [{}])[0].get("competitors", [])
    home = _competitor_by_home_away(competitors, "home")
    away = _competitor_by_home_away(competitors, "away")
    if home is None or away is None:
        return None
    try:
        home_score = int(home.get("score") or 0)
        away_score = int(away.get("score") or 0)
    except (TypeError, ValueError):
        return None
    if home_score > away_score:
        return "home"
    if away_score > home_score:
        return "away"
    return "draw"


def _settled_cash(portfolio: Portfolio, actual_outcome: str) -> int:
    settled_cash = portfolio.cash_cents
    for (_, outcome_id), position in portfolio.positions.items():
        if outcome_id == actual_outcome:
            settled_cash += position.quantity * 100
    return settled_cash


def _fill_diagnostic(fill: Fill, actual_outcome: str) -> FillDiagnostic:
    settlement_price_cents = 100 if fill.outcome_id == actual_outcome else 0
    if fill.side is OrderSide.BUY:
        terminal_pnl_cents = (settlement_price_cents - fill.price_cents) * fill.quantity - fill.fee_cents
    else:
        terminal_pnl_cents = (fill.price_cents - settlement_price_cents) * fill.quantity - fill.fee_cents

    minute = int(fill.metadata.get("minute", 0) or 0)
    home_goals = int(fill.metadata.get("home_goals", 0) or 0)
    away_goals = int(fill.metadata.get("away_goals", 0) or 0)
    return FillDiagnostic(
        outcome_id=fill.outcome_id,
        side=fill.side.value,
        minute=minute,
        score=f"{home_goals}-{away_goals}",
        price_cents=fill.price_cents,
        quantity=fill.quantity,
        fee_cents=fill.fee_cents,
        terminal_pnl_cents=terminal_pnl_cents,
    )


def _quote(outcome_id: str, candle: Mapping[str, Any]) -> OutcomeQuote:
    bid = _dollars_to_cents(candle.get("yes_bid", {}).get("close_dollars"))
    ask = _dollars_to_cents(candle.get("yes_ask", {}).get("close_dollars"))
    return OutcomeQuote(outcome_id=outcome_id, bid_cents=bid, ask_cents=ask)


def _dollars_to_cents(value: object) -> int | None:
    if value is None:
        return None
    return round(float(value) * 100)


def _play_wallclock(play: Mapping[str, Any]) -> datetime | None:
    value = play.get("play", {}).get("wallclock")
    if not isinstance(value, str):
        return None
    return _parse_datetime(value)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _play_sort_key(play: Mapping[str, Any]) -> float:
    wallclock = _play_wallclock(play)
    if wallclock is None:
        return float("inf")
    return wallclock.timestamp()


def _minute(play: Mapping[str, Any]) -> int:
    value = play.get("time", {}).get("value") or play.get("play", {}).get("clock", {}).get("value") or 0
    return min(90, int(float(value) // 60))
