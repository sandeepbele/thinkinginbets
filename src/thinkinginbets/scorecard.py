"""Backtest scorecard diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from thinkinginbets.kalshi_espn_replay import PublicReplayReport


@dataclass(frozen=True)
class OutcomeBucket:
    matches: int = 0
    pnl_cents: int = 0
    fills: int = 0
    fees_cents: int = 0

    @property
    def pnl_per_match_cents(self) -> float:
        if self.matches == 0:
            return 0.0
        return self.pnl_cents / self.matches

    @property
    def pnl_per_fill_cents(self) -> float:
        if self.fills == 0:
            return 0.0
        return self.pnl_cents / self.fills


@dataclass(frozen=True)
class FillBucket:
    fills: int = 0
    contracts: int = 0
    entry_notional_cents: int = 0
    pnl_cents: int = 0
    fees_cents: int = 0

    @property
    def average_entry_price_cents(self) -> float:
        if self.contracts == 0:
            return 0.0
        return self.entry_notional_cents / self.contracts

    @property
    def pnl_per_fill_cents(self) -> float:
        if self.fills == 0:
            return 0.0
        return self.pnl_cents / self.fills

    @property
    def pnl_per_contract_cents(self) -> float:
        if self.contracts == 0:
            return 0.0
        return self.pnl_cents / self.contracts


@dataclass(frozen=True)
class ReplayScorecard:
    reports: list[PublicReplayReport]
    starting_cash_cents: int
    ending_cash_cents: int
    equity_curve_cents: list[int]
    by_outcome: dict[str, OutcomeBucket] = field(default_factory=dict)
    by_minute_band: dict[str, FillBucket] = field(default_factory=dict)
    by_price_band: dict[str, FillBucket] = field(default_factory=dict)
    by_outcome_minute_band: dict[str, FillBucket] = field(default_factory=dict)
    by_side_outcome_minute_band: dict[str, FillBucket] = field(default_factory=dict)

    @property
    def matches(self) -> int:
        return len(self.reports)

    @property
    def total_pnl_cents(self) -> int:
        return self.ending_cash_cents - self.starting_cash_cents

    @property
    def total_fees_cents(self) -> int:
        return sum(report.total_fee_cents for report in self.reports)

    @property
    def total_fills(self) -> int:
        return sum(report.fills for report in self.reports)

    @property
    def pnl_per_match_cents(self) -> float:
        if self.matches == 0:
            return 0.0
        return self.total_pnl_cents / self.matches

    @property
    def pnl_per_fill_cents(self) -> float:
        if self.total_fills == 0:
            return 0.0
        return self.total_pnl_cents / self.total_fills

    @property
    def roi(self) -> float:
        if self.starting_cash_cents == 0:
            return 0.0
        return self.total_pnl_cents / self.starting_cash_cents

    @property
    def max_drawdown_cents(self) -> int:
        peak = self.starting_cash_cents
        max_drawdown = 0
        for equity in self.equity_curve_cents:
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)
        return max_drawdown

    @property
    def best_match(self) -> PublicReplayReport | None:
        if not self.reports:
            return None
        return max(self.reports, key=lambda report: report.total_pnl_cents)

    @property
    def worst_match(self) -> PublicReplayReport | None:
        if not self.reports:
            return None
        return min(self.reports, key=lambda report: report.total_pnl_cents)


def build_replay_scorecard(
    reports: Iterable[PublicReplayReport],
    *,
    starting_cash_cents: int,
    ending_cash_cents: int,
    equity_curve_cents: list[int],
) -> ReplayScorecard:
    report_list = list(reports)
    buckets: dict[str, OutcomeBucket] = {}
    minute_buckets: dict[str, FillBucket] = {}
    price_buckets: dict[str, FillBucket] = {}
    outcome_minute_buckets: dict[str, FillBucket] = {}
    side_outcome_minute_buckets: dict[str, FillBucket] = {}
    for report in report_list:
        previous = buckets.get(report.actual_outcome, OutcomeBucket())
        buckets[report.actual_outcome] = OutcomeBucket(
            matches=previous.matches + 1,
            pnl_cents=previous.pnl_cents + report.total_pnl_cents,
            fills=previous.fills + report.fills,
            fees_cents=previous.fees_cents + report.total_fee_cents,
        )
        for fill in report.fill_diagnostics:
            minute_band = _minute_band(fill.minute)
            price_band = _price_band(fill.price_cents)
            outcome_minute_band = f"{fill.outcome_id} {minute_band}"
            side_outcome_minute_band = f"{fill.side} {fill.outcome_id} {minute_band}"
            minute_buckets[minute_band] = _add_fill(minute_buckets.get(minute_band, FillBucket()), fill)
            price_buckets[price_band] = _add_fill(price_buckets.get(price_band, FillBucket()), fill)
            outcome_minute_buckets[outcome_minute_band] = _add_fill(
                outcome_minute_buckets.get(outcome_minute_band, FillBucket()),
                fill,
            )
            side_outcome_minute_buckets[side_outcome_minute_band] = _add_fill(
                side_outcome_minute_buckets.get(side_outcome_minute_band, FillBucket()),
                fill,
            )
    return ReplayScorecard(
        reports=report_list,
        starting_cash_cents=starting_cash_cents,
        ending_cash_cents=ending_cash_cents,
        equity_curve_cents=equity_curve_cents,
        by_outcome=buckets,
        by_minute_band=minute_buckets,
        by_price_band=price_buckets,
        by_outcome_minute_band=outcome_minute_buckets,
        by_side_outcome_minute_band=side_outcome_minute_buckets,
    )


def _add_fill(bucket: FillBucket, fill) -> FillBucket:
    return FillBucket(
        fills=bucket.fills + 1,
        contracts=bucket.contracts + fill.quantity,
        entry_notional_cents=bucket.entry_notional_cents + fill.price_cents * fill.quantity,
        pnl_cents=bucket.pnl_cents + fill.terminal_pnl_cents,
        fees_cents=bucket.fees_cents + fill.fee_cents,
    )


def _minute_band(minute: int) -> str:
    if minute <= 15:
        return "00-15"
    if minute <= 30:
        return "16-30"
    if minute <= 45:
        return "31-45"
    if minute <= 60:
        return "46-60"
    if minute <= 75:
        return "61-75"
    return "76-90"


def _price_band(price_cents: int) -> str:
    if price_cents <= 24:
        return "00-24c"
    if price_cents <= 49:
        return "25-49c"
    if price_cents <= 74:
        return "50-74c"
    return "75-100c"
