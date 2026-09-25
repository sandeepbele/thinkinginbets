# Roadmap

## Phase 1: Paper Loop

- Deterministic paper broker.
- Strategy/risk split.
- Unit tests for accounting, risk, and edge logic.
- CLI smoke test.

## Phase 2: Data

- Kalshi market-data adapter.
- Polymarket US market-data adapter.
- Live sports feed adapter for score, clock, cards, substitutions, and event stats.
- Durable tick/trade journal.

## Phase 3: Models

- Pre-match priors from public odds and team ratings.
- `penaltyblog` baseline model for home/draw/away pricing.
- In-play probability updates.
- LLM commentary parser that emits structured match-state observations.
- Calibration reports and closing-line-value tracking.

## Phase 4: Execution

- Manual approval mode.
- Limit-order execution.
- Order cancel/replace policy.
- Kill switch and exposure dashboard.

## Phase 5: Live Mode

- Tiny size only.
- Per-market allowlist.
- Exchange-specific compliance checks.
- Full audit log of every model signal, risk decision, order, and fill.
