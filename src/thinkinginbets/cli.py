"""Command-line entry points."""

from __future__ import annotations

import argparse
from pathlib import Path

from thinkinginbets.engine import TradingEngine
from thinkinginbets.backtest import run_backtest, run_no_market_price_audit
from thinkinginbets.feeds.espn import fetch_espn_scoreboard
from thinkinginbets.kalshi_espn_replay import (
    PublicReplayConfig,
    ReplaySettings,
    discover_public_replay_configs,
    run_public_kalshi_espn_replay,
)
from thinkinginbets.hypotheses import (
    analyze_double_chance,
    analyze_favorite_stress,
    analyze_late_underdog,
    analyze_odds_double_chance,
)
from thinkinginbets.live_replay import replay_live_scenario
from thinkinginbets.models.in_play import InPlayHeuristicModel
from thinkinginbets.paper import PaperBroker
from thinkinginbets.paper_bets import append_bets, evaluate_pending_bets, propose_paper_bets, read_bets
from thinkinginbets.risk import RiskLimits, RiskManager
from thinkinginbets.scorecard import build_replay_scorecard
from thinkinginbets.simulated import iter_world_cup_snapshots
from thinkinginbets.simulated_live import draw_then_home_goal_scenario
from thinkinginbets.strategy import ValueStrategy
from thinkinginbets.domain import Portfolio
from thinkinginbets.data_sources import data_source_statuses


def run_paper(args: argparse.Namespace) -> int:
    portfolio = Portfolio(cash_cents=args.cash_cents)
    engine = TradingEngine(
        strategy=ValueStrategy(min_edge_cents=args.min_edge_cents, max_quantity=args.quantity),
        risk_manager=RiskManager(
            RiskLimits(
                max_order_notional_cents=args.max_order_notional_cents,
                max_market_exposure_cents=args.max_market_exposure_cents,
                max_session_loss_cents=args.max_session_loss_cents,
            )
        ),
        broker=PaperBroker(portfolio),
    )

    for index, (snapshot, probabilities) in enumerate(iter_world_cup_snapshots(), start=1):
        if index > args.ticks:
            break
        report = engine.on_tick(snapshot, probabilities)
        print(
            f"tick={index} observed_at={snapshot.observed_at.isoformat()} "
            f"accepted={len(report.accepted_orders)} rejected={len(report.rejected_intents)} "
            f"filled={len(report.filled_orders)} cash_cents={portfolio.cash_cents} "
            f"realized_pnl_cents={portfolio.realized_pnl_cents}"
        )
        for order in report.filled_orders:
            intent = order.intent
            print(
                f"  fill {intent.side.value} {intent.quantity} {intent.outcome_id} "
                f"@ {intent.limit_price_cents}c: {intent.reason}"
            )
        for rejected in report.rejected_intents:
            print(f"  reject {rejected.intent.outcome_id}: {rejected.reason}")

    return 0


def run_espn_scoreboard(args: argparse.Namespace) -> int:
    states = fetch_espn_scoreboard(league=args.league, dates=args.dates, limit=args.limit)
    for state in states:
        home_corners = state.statistics.get("home_wonCorners")
        away_corners = state.statistics.get("away_wonCorners")
        home_possession = state.statistics.get("home_possessionPct")
        away_possession = state.statistics.get("away_possessionPct")
        print(
            f"{state.provider_match_id} {state.status} {state.minute}' "
            f"{state.home_team} {state.home_goals}-{state.away_goals} {state.away_team} "
            f"possession={home_possession}/{away_possession} corners={home_corners}/{away_corners}"
        )
    return 0


def run_place_paper_bet(args: argparse.Namespace) -> int:
    states = fetch_espn_scoreboard(league=args.league, dates=args.dates, limit=args.limit)
    bets = propose_paper_bets(
        states,
        stake_cents=args.stake_cents,
        min_probability=args.min_probability,
        max_bets=args.max_bets,
    )
    append_bets(Path(args.journal), bets)
    if not bets:
        print("no eligible upcoming matches cleared the paper-bet threshold")
        return 0
    for bet in bets:
        print(
            f"placed {bet.predicted_outcome} {bet.home_team} vs {bet.away_team} "
            f"price={bet.price_cents}c stake={bet.stake_cents}c "
            f"p={bet.model_probability}"
        )
    return 0


def run_evaluate_paper_bets(args: argparse.Namespace) -> int:
    states = fetch_espn_scoreboard(league=args.league, dates=args.dates, limit=args.limit)
    evaluated = evaluate_pending_bets(Path(args.journal), states)
    if not evaluated:
        print("no paper bets found")
        return 0
    for bet in evaluated:
        print(
            f"{bet.status} {bet.predicted_outcome} {bet.home_team} vs {bet.away_team} "
            f"final={bet.final_score} pnl_cents={bet.realized_pnl_cents}"
        )
    return 0


def run_backtest_command(args: argparse.Namespace) -> int:
    states = fetch_espn_scoreboard(league=args.league, dates=args.dates, limit=args.limit)
    if args.audit_no_market_price:
        findings = run_no_market_price_audit(states, min_probability=args.min_probability)
        if not findings:
            print("no completed matches cleared the audit threshold")
            return 0
        for finding in findings:
            print(finding)
        print("audit: no trades should be placed without executable historical prices")
        return 0

    report = run_backtest(
        states,
        stake_cents=args.stake_cents,
        min_probability=args.min_probability,
    )
    if not report.bets:
        print("no completed matches cleared the backtest threshold")
        return 0

    for bet in report.bets:
        result = "WIN" if bet.won else "LOSS"
        print(
            f"{result} {bet.home_team} {bet.final_score} {bet.away_team} "
            f"pick={bet.predicted_outcome} actual={bet.actual_outcome} "
            f"price={bet.price_cents}c stake={bet.stake_cents}c "
            f"pnl={bet.realized_pnl_cents}c"
        )
    print(
        f"summary bets={len(report.bets)} wins={report.wins} "
        f"staked={report.total_staked_cents}c pnl={report.total_pnl_cents}c "
        f"roi={report.roi:.2%}"
    )
    return 0


def run_live_scenario(args: argparse.Namespace) -> int:
    portfolio = Portfolio(cash_cents=args.cash_cents)
    engine = TradingEngine(
        strategy=ValueStrategy(min_edge_cents=args.min_edge_cents, max_quantity=args.quantity),
        risk_manager=RiskManager(
            RiskLimits(
                max_order_notional_cents=args.max_order_notional_cents,
                max_market_exposure_cents=args.max_market_exposure_cents,
                max_session_loss_cents=args.max_session_loss_cents,
            )
        ),
        broker=PaperBroker(portfolio),
    )
    result = replay_live_scenario(
        draw_then_home_goal_scenario(),
        model=InPlayHeuristicModel(),
        engine=engine,
    )
    for tick in result.ticks:
        print(f"minute={tick.minute} score={tick.score} fills={len(tick.filled_orders)}")
        for order in tick.filled_orders:
            intent = order.intent
            print(
                f"  {intent.side.value} {intent.quantity} {intent.outcome_id} "
                f"@ {intent.limit_price_cents}c: {intent.reason}"
            )
    print(
        f"summary fills={result.fill_count} cash_cents={portfolio.cash_cents} "
        f"realized_pnl_cents={portfolio.realized_pnl_cents}"
    )
    return 0


def run_data_doctor(_args: argparse.Namespace) -> int:
    for status in data_source_statuses():
        required = ",".join(status.credential_env_vars) if status.credential_env_vars else "-"
        print(
            f"{status.name}: creds={status.credential_status} "
            f"env={required} live={status.supports_live} "
            f"historical_replay={status.supports_historical_replay}"
        )
        print(f"  {status.notes}")
    return 0


def run_public_replay(args: argparse.Namespace) -> int:
    report = run_public_kalshi_espn_replay(
        PublicReplayConfig(
            espn_event_id=args.espn_event_id,
            kalshi_event_ticker=args.kalshi_event_ticker,
            start_ts=args.start_ts,
            end_ts=args.end_ts,
            home_ticker=args.home_ticker,
            away_ticker=args.away_ticker,
            draw_ticker=args.draw_ticker,
            home_team=args.home_team,
            away_team=args.away_team,
        ),
        settings=_replay_settings_from_args(args),
    )
    for line in report.lines:
        print(line)
    print(
        f"summary ticks={report.ticks} fills={report.fills} "
        f"actual={report.actual_outcome} cash_cents={report.cash_cents} "
        f"realized_pnl_cents={report.realized_pnl_cents} "
        f"fees_cents={report.total_fee_cents} "
        f"settled_cash_cents={report.settled_cash_cents} "
        f"total_pnl_cents={report.total_pnl_cents}"
    )
    return 0


def run_public_replay_dates(args: argparse.Namespace) -> int:
    configs = discover_public_replay_configs(dates=args.dates, limit=args.limit)
    if not configs:
        print("no ESPN fixtures with matching public Kalshi markets were discovered")
        return 0
    total_pnl = 0
    completed = 0
    current_cash_cents = args.cash_cents
    reports = []
    equity_curve = []
    for config in configs[: args.max_matches]:
        if args.shared_bankroll and current_cash_cents <= 0:
            print("bankroll depleted; stopping replay")
            break
        try:
            report = run_public_kalshi_espn_replay(
                config,
                settings=_replay_settings_from_args(
                    args,
                    cash_cents=current_cash_cents if args.shared_bankroll else None,
                ),
            )
        except Exception as exc:
            print(f"{config.home_team} vs {config.away_team}: skipped replay ({exc})")
            continue
        completed += 1
        reports.append(report)
        total_pnl += report.total_pnl_cents
        if args.shared_bankroll:
            current_cash_cents = report.settled_cash_cents
            equity_curve.append(current_cash_cents)
        print(
            f"{report.label}: ticks={report.ticks} fills={report.fills} "
            f"actual={report.actual_outcome} settled_cash={report.settled_cash_cents}c "
            f"fees={report.total_fee_cents}c pnl={report.total_pnl_cents}c"
        )
    if args.shared_bankroll:
        scorecard = build_replay_scorecard(
            reports,
            starting_cash_cents=args.cash_cents,
            ending_cash_cents=current_cash_cents,
            equity_curve_cents=equity_curve,
        )
        print(
            f"summary matches={completed} starting_cash_cents={args.cash_cents} "
            f"ending_cash_cents={current_cash_cents} total_pnl_cents={current_cash_cents - args.cash_cents}"
        )
        _print_scorecard(scorecard)
    else:
        print(f"summary matches={completed} total_pnl_cents={total_pnl}")
    return 0


def run_late_underdog(args: argparse.Namespace) -> int:
    configs = discover_public_replay_configs(dates=args.dates, limit=args.limit)
    if not configs:
        print("no ESPN fixtures with matching public Kalshi markets were discovered")
        return 0

    report = analyze_late_underdog(configs[: args.max_matches], quantity=args.quantity)
    for bet in report.bets:
        print(
            f"{bet.match_label} band={bet.band} minute={bet.minute} score={bet.score} "
            f"underdog={bet.underdog} actual={bet.actual_outcome} "
            f"ask={bet.ask_cents}c fee={bet.fee_cents}c pnl={bet.pnl_cents}c"
        )
    for bucket in report.buckets:
        print(
            f"band {bucket.band}: fills={bucket.fills} contracts={bucket.contracts} "
            f"avg_entry_cents={bucket.average_entry_cents:.1f} fees_cents={bucket.fees_cents} "
            f"pnl_cents={bucket.pnl_cents} pnl_per_contract_cents={bucket.pnl_per_contract_cents:.1f}"
        )
    print(f"summary bets={len(report.bets)} total_pnl_cents={report.total_pnl_cents}")
    return 0


def run_double_chance(args: argparse.Namespace) -> int:
    configs = discover_public_replay_configs(dates=args.dates, limit=args.limit)
    if not configs:
        print("no ESPN fixtures with matching public Kalshi markets were discovered")
        return 0

    report = analyze_double_chance(
        configs[: args.max_matches],
        quantity=args.quantity,
        max_combo_price_cents=args.max_combo_price_cents,
        require_favorite_not_leading=args.require_favorite_not_leading,
    )
    for bet in report.bets:
        print(
            f"{bet.match_label} band={bet.band} minute={bet.minute} score={bet.score} "
            f"underdog={bet.underdog} favorite={bet.favorite} actual={bet.actual_outcome} "
            f"underdog_ask={bet.underdog_ask_cents}c draw_ask={bet.draw_ask_cents}c "
            f"cost={bet.cost_cents}c fee={bet.fee_cents}c pnl={bet.pnl_cents}c"
        )
    for bucket in report.buckets:
        print(
            f"band {bucket.band}: fills={bucket.fills} contracts={bucket.contracts} "
            f"avg_combo_price_cents={bucket.average_combo_price_cents:.1f} "
            f"cost_cents={bucket.cost_cents} fees_cents={bucket.fees_cents} "
            f"pnl_cents={bucket.pnl_cents} roi_on_cost={bucket.roi_on_cost:.2%}"
        )
    print(
        f"summary bets={len(report.bets)} total_cost_cents={report.total_cost_cents} "
        f"total_pnl_cents={report.total_pnl_cents}"
    )
    return 0


def run_favorite_stress(args: argparse.Namespace) -> int:
    configs = discover_public_replay_configs(dates=args.dates, limit=args.limit)
    if not configs:
        print("no ESPN fixtures with matching public Kalshi markets were discovered")
        return 0

    report = analyze_favorite_stress(configs[: args.max_matches])
    for row in report.rows:
        print(
            f"{row.match_label}: actual={row.actual_outcome} favorite={row.favorite} "
            f"base_pnl={row.base_pnl_cents}c favorite_win_pnl={row.favorite_win_pnl_cents}c "
            f"delta={row.stress_delta_cents}c"
        )
    print(
        f"summary matches={len(report.rows)} base_total_pnl_cents={report.base_total_pnl_cents} "
        f"favorite_win_total_pnl_cents={report.favorite_win_total_pnl_cents} "
        f"stress_delta_cents={report.stress_delta_cents}"
    )
    return 0


def run_odds_double_chance(args: argparse.Namespace) -> int:
    report = analyze_odds_double_chance(
        league=args.league,
        dates=args.dates,
        limit=args.limit,
        max_combo_price_cents=args.max_combo_price_cents,
    )
    for bet in report.bets:
        print(
            f"{bet.match_label}: underdog={bet.underdog} favorite={bet.favorite} "
            f"actual={bet.actual_outcome} underdog_price={bet.underdog_price_cents:.1f}c "
            f"draw_price={bet.draw_price_cents:.1f}c combo={bet.combo_price_cents:.1f}c "
            f"pnl={bet.pnl_cents:.1f}c"
        )
    print(
        f"summary league={args.league} events_seen={report.events_seen} "
        f"events_with_odds={report.events_with_odds} events_qualified={report.events_qualified} "
        f"bets={len(report.bets)} cost_cents={report.total_cost_cents:.1f} "
        f"pnl_cents={report.total_pnl_cents:.1f} roi_on_cost={report.roi_on_cost:.2%}"
    )
    return 0


def _print_scorecard(scorecard) -> None:
    print(
        f"scorecard roi={scorecard.roi:.2%} max_drawdown_cents={scorecard.max_drawdown_cents} "
        f"fills={scorecard.total_fills} fees_cents={scorecard.total_fees_cents} "
        f"pnl_per_match_cents={scorecard.pnl_per_match_cents:.1f} "
        f"pnl_per_fill_cents={scorecard.pnl_per_fill_cents:.1f}"
    )
    if scorecard.best_match is not None:
        print(
            f"best_match {scorecard.best_match.label} "
            f"pnl_cents={scorecard.best_match.total_pnl_cents} "
            f"fills={scorecard.best_match.fills} fees_cents={scorecard.best_match.total_fee_cents}"
        )
    if scorecard.worst_match is not None:
        print(
            f"worst_match {scorecard.worst_match.label} "
            f"pnl_cents={scorecard.worst_match.total_pnl_cents} "
            f"fills={scorecard.worst_match.fills} fees_cents={scorecard.worst_match.total_fee_cents}"
        )
    for outcome, bucket in sorted(scorecard.by_outcome.items()):
        print(
            f"outcome {outcome}: matches={bucket.matches} pnl_cents={bucket.pnl_cents} "
            f"fills={bucket.fills} fees_cents={bucket.fees_cents} "
            f"pnl_per_match_cents={bucket.pnl_per_match_cents:.1f} "
            f"pnl_per_fill_cents={bucket.pnl_per_fill_cents:.1f}"
        )
    for band, bucket in sorted(scorecard.by_minute_band.items()):
        print(
            f"minute_band {band}: fills={bucket.fills} contracts={bucket.contracts} "
            f"avg_entry_cents={bucket.average_entry_price_cents:.1f} "
            f"fees_cents={bucket.fees_cents} pnl_cents={bucket.pnl_cents} "
            f"pnl_per_contract_cents={bucket.pnl_per_contract_cents:.1f}"
        )
    for band, bucket in sorted(scorecard.by_price_band.items()):
        print(
            f"price_band {band}: fills={bucket.fills} contracts={bucket.contracts} "
            f"avg_entry_cents={bucket.average_entry_price_cents:.1f} "
            f"fees_cents={bucket.fees_cents} pnl_cents={bucket.pnl_cents} "
            f"pnl_per_contract_cents={bucket.pnl_per_contract_cents:.1f}"
        )
    for key, bucket in sorted(scorecard.by_outcome_minute_band.items()):
        print(
            f"outcome_minute {key}: fills={bucket.fills} contracts={bucket.contracts} "
            f"avg_entry_cents={bucket.average_entry_price_cents:.1f} "
            f"fees_cents={bucket.fees_cents} pnl_cents={bucket.pnl_cents} "
            f"pnl_per_contract_cents={bucket.pnl_per_contract_cents:.1f}"
        )
    for key, bucket in sorted(scorecard.by_side_outcome_minute_band.items()):
        print(
            f"side_outcome_minute {key}: fills={bucket.fills} contracts={bucket.contracts} "
            f"avg_entry_cents={bucket.average_entry_price_cents:.1f} "
            f"fees_cents={bucket.fees_cents} pnl_cents={bucket.pnl_cents} "
            f"pnl_per_contract_cents={bucket.pnl_per_contract_cents:.1f}"
        )


def _replay_settings_from_args(
    args: argparse.Namespace,
    *,
    cash_cents: int | None = None,
) -> ReplaySettings:
    return ReplaySettings(
        initial_cash_cents=args.cash_cents if cash_cents is None else cash_cents,
        max_order_notional_cents=args.max_order_notional_cents,
        max_market_exposure_cents=args.max_market_exposure_cents,
        max_session_loss_cents=args.max_session_loss_cents,
        quantity=args.quantity,
        min_edge_cents=args.min_edge_cents,
        max_draw_buy_minute=args.max_draw_buy_minute,
        allow_draw_sells=args.allow_draw_sells,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thinkinginbets")
    subparsers = parser.add_subparsers(dest="command", required=True)

    paper = subparsers.add_parser("paper", help="run the deterministic paper-trading demo")
    paper.add_argument("--ticks", type=int, default=4)
    paper.add_argument("--cash-cents", type=int, default=25_000)
    paper.add_argument("--quantity", type=int, default=5)
    paper.add_argument("--min-edge-cents", type=int, default=4)
    paper.add_argument("--max-order-notional-cents", type=int, default=1_000)
    paper.add_argument("--max-market-exposure-cents", type=int, default=5_000)
    paper.add_argument("--max-session-loss-cents", type=int, default=2_500)
    paper.set_defaults(func=run_paper)

    espn = subparsers.add_parser("espn-scoreboard", help="fetch ESPN public soccer scoreboard")
    espn.add_argument("--league", default="fifa.world")
    espn.add_argument("--dates", default=None)
    espn.add_argument("--limit", type=int, default=10)
    espn.set_defaults(func=run_espn_scoreboard)

    place = subparsers.add_parser("place-paper-bet", help="place paper bets on upcoming ESPN fixtures")
    place.add_argument("--league", default="fifa.world")
    place.add_argument("--dates", default=None)
    place.add_argument("--limit", type=int, default=20)
    place.add_argument("--journal", default="data/paper_bets.jsonl")
    place.add_argument("--stake-cents", type=int, default=1_000)
    place.add_argument("--min-probability", type=float, default=0.55)
    place.add_argument("--max-bets", type=int, default=1)
    place.set_defaults(func=run_place_paper_bet)

    evaluate = subparsers.add_parser("evaluate-paper-bets", help="settle final paper bets")
    evaluate.add_argument("--league", default="fifa.world")
    evaluate.add_argument("--dates", default=None)
    evaluate.add_argument("--limit", type=int, default=100)
    evaluate.add_argument("--journal", default="data/paper_bets.jsonl")
    evaluate.set_defaults(func=run_evaluate_paper_bets)

    backtest = subparsers.add_parser("backtest", help="backtest static priors on completed ESPN fixtures")
    backtest.add_argument("--league", default="fifa.world")
    backtest.add_argument("--dates", required=True)
    backtest.add_argument("--limit", type=int, default=100)
    backtest.add_argument("--stake-cents", type=int, default=1_000)
    backtest.add_argument("--min-probability", type=float, default=0.55)
    backtest.add_argument("--audit-no-market-price", action="store_true")
    backtest.set_defaults(func=run_backtest_command)

    live = subparsers.add_parser("live-scenario", help="replay a synthetic in-play trading scenario")
    live.add_argument("--cash-cents", type=int, default=25_000)
    live.add_argument("--quantity", type=int, default=5)
    live.add_argument("--min-edge-cents", type=int, default=4)
    live.add_argument("--max-order-notional-cents", type=int, default=1_000)
    live.add_argument("--max-market-exposure-cents", type=int, default=5_000)
    live.add_argument("--max-session-loss-cents", type=int, default=2_500)
    live.set_defaults(func=run_live_scenario)

    doctor = subparsers.add_parser("data-doctor", help="show data-source credential/capability status")
    doctor.set_defaults(func=run_data_doctor)

    replay = subparsers.add_parser("public-replay", help="replay public ESPN events against Kalshi candles")
    replay.add_argument("--espn-event-id", default="760428")
    replay.add_argument("--kalshi-event-ticker", default="KXWCGAME-26JUN15ESPCPV")
    replay.add_argument("--home-ticker", default="KXWCGAME-26JUN15ESPCPV-ESP")
    replay.add_argument("--away-ticker", default="KXWCGAME-26JUN15ESPCPV-CPV")
    replay.add_argument("--draw-ticker", default="KXWCGAME-26JUN15ESPCPV-TIE")
    replay.add_argument("--home-team", default="Spain")
    replay.add_argument("--away-team", default="Cape Verde")
    replay.add_argument("--start-ts", type=int, default=1781538900)
    replay.add_argument("--end-ts", type=int, default=1781546160)
    replay.add_argument("--cash-cents", type=int, default=10_000)
    replay.add_argument("--quantity", type=int, default=5)
    replay.add_argument("--min-edge-cents", type=int, default=4)
    replay.add_argument("--max-order-notional-cents", type=int, default=250)
    replay.add_argument("--max-market-exposure-cents", type=int, default=750)
    replay.add_argument("--max-session-loss-cents", type=int, default=600)
    replay.add_argument("--max-draw-buy-minute", type=int, default=45)
    replay.add_argument("--allow-draw-sells", action="store_true")
    replay.set_defaults(func=run_public_replay)

    replay_dates = subparsers.add_parser(
        "public-replay-dates",
        help="discover ESPN fixtures and replay matching Kalshi public markets",
    )
    replay_dates.add_argument("--dates", required=True)
    replay_dates.add_argument("--limit", type=int, default=50)
    replay_dates.add_argument("--max-matches", type=int, default=5)
    replay_dates.add_argument("--cash-cents", type=int, default=10_000)
    replay_dates.add_argument("--quantity", type=int, default=5)
    replay_dates.add_argument("--min-edge-cents", type=int, default=4)
    replay_dates.add_argument("--max-order-notional-cents", type=int, default=250)
    replay_dates.add_argument("--max-market-exposure-cents", type=int, default=750)
    replay_dates.add_argument("--max-session-loss-cents", type=int, default=600)
    replay_dates.add_argument("--max-draw-buy-minute", type=int, default=45)
    replay_dates.add_argument("--allow-draw-sells", action="store_true")
    replay_dates.add_argument("--shared-bankroll", action="store_true")
    replay_dates.set_defaults(func=run_public_replay_dates)

    late_underdog = subparsers.add_parser(
        "late-underdog",
        help="test one late underdog buy per match/minute band against public replay data",
    )
    late_underdog.add_argument("--dates", required=True)
    late_underdog.add_argument("--limit", type=int, default=50)
    late_underdog.add_argument("--max-matches", type=int, default=10)
    late_underdog.add_argument("--quantity", type=int, default=5)
    late_underdog.set_defaults(func=run_late_underdog)

    double_chance = subparsers.add_parser(
        "double-chance",
        help="test underdog plus draw baskets once per match/minute band",
    )
    double_chance.add_argument("--dates", required=True)
    double_chance.add_argument("--limit", type=int, default=50)
    double_chance.add_argument("--max-matches", type=int, default=10)
    double_chance.add_argument("--quantity", type=int, default=5)
    double_chance.add_argument("--max-combo-price-cents", type=int, default=None)
    double_chance.add_argument("--require-favorite-not-leading", action="store_true")
    double_chance.set_defaults(func=run_double_chance)

    favorite_stress = subparsers.add_parser(
        "favorite-stress",
        help="resettle default replay fills as if each first-tick favorite won",
    )
    favorite_stress.add_argument("--dates", required=True)
    favorite_stress.add_argument("--limit", type=int, default=50)
    favorite_stress.add_argument("--max-matches", type=int, default=10)
    favorite_stress.set_defaults(func=run_favorite_stress)

    odds_double_chance = subparsers.add_parser(
        "odds-double-chance",
        help="test underdog plus draw using ESPN/DraftKings odds across any ESPN soccer league",
    )
    odds_double_chance.add_argument("--league", required=True)
    odds_double_chance.add_argument("--dates", required=True)
    odds_double_chance.add_argument("--limit", type=int, default=100)
    odds_double_chance.add_argument("--max-combo-price-cents", type=float, default=None)
    odds_double_chance.set_defaults(func=run_odds_double_chance)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
