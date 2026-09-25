# Live Backtesting Data

## Verdict

There is no obvious free, ready-made dataset that already pairs:

1. live soccer match-state ticks,
2. historical Kalshi/Polymarket executable bid/ask/order-book ticks,
3. timestamp alignment,
4. final settlement labels.

We can still build real live backtests by combining free/public sources and recording our own data
going forward.

## Match-State Data

### Best Free Historical Event Data

- `Wyscout public soccer match event dataset`: free event streams for top European leagues, Euro 2016,
  and FIFA World Cup 2018. This is useful for replaying score/cards/shots/corners-like event timelines.
- `StatsBomb Open Data`: free JSON event/lineup data for selected competitions and matches. Good for
  model training and event replay, but coverage is selective.
- `ESPN public scoreboard`: useful for current/recent World Cup match score, clock, goals/cards/details,
  and team stats such as possession, corners, shots, and shots on target. It is undocumented, so we should
  archive responses ourselves.

### Important Limitation

Most free historical event datasets provide event timelines, not every public live-stat snapshot as it
appeared during the match. We can reconstruct cumulative shots/cards/goals/corners from events, but
minute-by-minute possession is usually harder unless the source archived repeated live snapshots.

## Market Data

### Kalshi

- Official Kalshi historical endpoints provide historical markets, trades, and candlesticks.
- Kalshi candlesticks include yes bid/ask OHLC, price OHLC, volume, and open interest at 1-minute,
  1-hour, or 1-day intervals.
- For full historical order-book snapshots, use our own recorder or evaluate a third-party source.

### Polymarket

- Official Polymarket CLOB endpoints expose public orderbook/pricing and price history.
- Price history supports time windows and minute-level fidelity.
- Polymarket on-chain trades/activity can be queried via public analytics providers such as Dune/Goldsky,
  but on-chain data is not the same as historical executable order-book depth.

### Third-Party Free Historical Orderbooks

- Predexon documents free/unlimited historical orderbook snapshot endpoints for:
  - Kalshi, starting January 7, 2026;
  - Polymarket, starting January 1, 2026.
- It requires an API key. Treat this as a useful external dependency, not canonical exchange truth, until
  we validate timestamp coverage, missing data behavior, and schema stability.

## Practical Backtest Plan

### Path A: Real 2026 Backtests

1. Discover sports markets on Kalshi/Polymarket.
2. Map each market outcome to ESPN match/team identifiers.
3. Pull historical market candles/prices/trades from official APIs.
4. Pull historical order-book snapshots from Predexon where available.
5. Pull ESPN match details/final stats and use our live recorder for future snapshot history.
6. Replay by timestamp: market tick + latest known match state -> model -> strategy -> risk -> paper fill.

This is the closest path to a real backtest without paying for data.

### Path B: Model-Only Historical Replay

1. Use Wyscout/StatsBomb event streams.
2. Reconstruct match states minute by minute.
3. Use synthetic or bookmaker-proxy prices.
4. Evaluate model behavior, but label results clearly as `forecast_backtest`, not `trading_backtest`.

This is useful for model development, not proof of trading edge.

### Path C: Our Own Recorder

Start recording now:

- ESPN scoreboard snapshots every 10-30 seconds during relevant matches.
- Kalshi WebSocket order-book/trade events.
- Polymarket WebSocket order-book/trade events.
- Periodic REST snapshots as reconciliation checkpoints.

This gives us the highest-quality free dataset for future live backtests.

## Storage Shape

Use append-only JSONL or SQLite first:

- `match_snapshots`: provider, match id, observed_at, score, clock, cards, corners, shots, possession.
- `market_snapshots`: exchange, market id, outcome id, observed_at, bid, ask, depth, volume, open interest.
- `market_trades`: exchange, market id, outcome id, traded_at, price, size, side.
- `replay_decisions`: model inputs, fair probabilities, proposed orders, risk result, simulated fill.

## Data Quality Rules

- Never use a market tick whose timestamp is after the decision timestamp.
- Never use final stats during an in-play replay tick.
- Keep raw payloads for audit.
- Mark third-party orderbooks as `external_unverified` until reconciled with exchange candles/trades.
- Report backtest class explicitly: `forecast`, `price_history`, `candlestick`, or `orderbook_replay`.
