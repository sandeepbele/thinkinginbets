# Data Feeds

## Decision

Use exchange feeds for market state and independent sports-data feeds for match state.

Kalshi and Polymarket tell us order books, trades, market status, fills, and our own orders.
They should not be the sole source of truth for goals, cards, substitutions, injuries, or
match momentum. Market feeds can lag, overreact, underreact, or be strategically noisy.

## MVP Feed Stack

1. `API-Football` as the primary official free-tier live soccer feed.
2. `ESPN public scoreboard` as a no-key fallback for paper trading and redundancy.
3. `football-data.org` for fixture/status polling where coverage is available.
2. `Kalshi` WebSocket for Kalshi order books, trades, market status, and fills.
3. `Polymarket US` WebSocket for order-book and trade data where compliant access is available.
4. `The Odds API` or a similar odds aggregator only if a free tier covers the needed markets.

## Production Feed Stack

For serious live execution, add a paid low-latency provider such as Sportradar or Opta/Stats Perform
and keep Sportmonks/API-Football as a fallback. Use two independent sports feeds during live trading
so the bot can pause when they disagree on high-impact events.

## Autonomous Safety Rules

- Stop opening new positions when the sports feed is stale.
- Stop opening new positions when exchange WebSockets disconnect.
- Require event confirmation for goals and red cards before increasing exposure.
- Allow position reduction during feed degradation, but block new exposure.
- Archive raw provider payloads next to normalized events for audit/debugging.
