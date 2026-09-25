# Trading Strategy

## Principle

Do not trade narratives. Trade price errors.

A strong-team prior is useful only as a baseline forecast. It is not edge by itself because the
same information is public, repeated by media, reflected in bookmaker odds, and usually reflected
in Kalshi/Polymarket prices.

## What Counts As A Trade

The bot should open exposure only when all are true:

1. We have a current market ask/bid.
2. Our fair probability differs from the executable price after fees and spread.
3. The difference is explained by a non-obvious signal or market-structure condition.
4. Feed freshness and risk gates pass.
5. Liquidity is enough that the quoted price is real, not decorative.

Examples of acceptable edge hypotheses:

- `stale_in_play`: the market has not fully reacted to a confirmed goal, card, substitution, or injury.
- `draw_underpriced`: game state supports draw risk more than the market, especially low-event matches.
- `overbought_favorite`: public favorite has moved beyond model/bookmaker consensus without new information.
- `cross_market_arb`: mutually exclusive outcome prices sum to a risk-controlled arbitrage after fees.
- `related_market_mismatch`: winner/qualification/exact-score markets imply inconsistent probabilities.

Examples of rejected hypotheses:

- Team A is famous.
- Team A is ranked higher.
- News articles say Team A should win.
- The LLM feels momentum.
- The model picks the favorite but we do not know the market price.

## World Cup Starting Strategy

1. Pre-match: mostly observe. Bet only cross-market/cross-exchange arbitrage or clear market-vs-consensus gaps.
2. Early in-play: avoid adding exposure unless a price is stale after a confirmed event.
3. Mid/late match: focus on draw and hedge opportunities, because favorite narratives often overpay for certainty.
4. After goals/cards: compare market move against expected move from the in-play model; trade only the gap.
5. Always prefer reducing risk over increasing risk when feeds disagree or go stale.

## Dynamic Position Management

Adjusting during the match is possible because prediction-market contracts can usually be bought
and sold before settlement. The bot should think in portfolio states:

- `open`: enter when fair value exceeds executable price by the required edge.
- `add`: increase only when the new price still has edge and exposure limits allow it.
- `trim`: sell part of a position when the edge has collapsed.
- `hedge`: buy another outcome when it reduces downside more than it sacrifices upside.
- `flip`: switch sides only when the old position is no longer +EV and the new side is +EV after costs.

Starting with draw and switching after a goal can work in some scenarios, but only if the prices are
wrong. In a low-event 0-0 match, draw can become underpriced if the public keeps paying for a favorite.
After a goal, the market often reprices violently; buying the scoring side after the move may be the
worst price in the match. The correct action may be to sell draw, hedge, or wait.

Backtest live scenarios with event timelines:

1. historical match-state ticks: minute, score, cards, shots, possession, corners;
2. historical market ticks: bid/ask/order-book snapshots;
3. replay loop: model -> strategy -> risk -> paper fills;
4. evaluation: realized PnL, drawdown, slippage, closing-line value, rejected trades.

## Model Stack

- `market_price`: executable Kalshi/Polymarket price. This is the baseline to beat.
- `consensus_price`: bookmaker/prediction-market aggregate when available.
- `pre_match_model`: `penaltyblog` or team-strength priors.
- `in_play_model`: score, minute, red cards, possession, corners, shots, shots on target.
- `llm_observer`: converts commentary/news into structured flags; never submits orders directly.

## Backtest Rules

- A winner-pick backtest is not a trading backtest.
- A valid trading backtest needs historical executable prices or a conservative proxy.
- Report closing-line value, realized PnL, max drawdown, and number of rejected trades.
