# Current Scorecard

> Historical research snapshot from June 2026. These replay results come from a small selected match sample and paper-fill assumptions; they are not prospective trading results. The replay aligns ESPN play timestamps with Kalshi candles without measuring when ESPN updates became available, so delayed reporting could make some simulated decisions look earlier than they were possible live.

Baseline command:

```bash
PYTHONPATH=src python3 -m thinkinginbets.cli public-replay-dates \
  --dates 20260611-20260620 \
  --max-matches 10 \
  --cash-cents 10000 \
  --shared-bankroll
```

As of June 16, 2026, public ESPN plus Kalshi discovery finds 8 completed World Cup matches in this
date range with replayable ESPN event timelines and Kalshi 1-minute candles.

## Baseline Result

- Starting bankroll: 10000c
- Ending bankroll: 13662c
- Total PnL: 3662c
- ROI: 36.62%
- Max drawdown: 311c
- Fills: 34
- Fees: 198c
- PnL per match: 457.8c
- PnL per fill: 107.7c

Default replay strategy:

- Do not sell/trim draw positions before settlement.
- Do not open new draw exposure after minute 45.
- Keep the existing order, edge, bankroll, fee, and exposure limits.

## Match Diagnostics

| Match | Actual | Fills | Fees | PnL |
|---|---:|---:|---:|---:|
| Mexico vs South Africa | home | 2 | 11c | -176c |
| Qatar vs Switzerland | draw | 9 | 22c | 2173c |
| Brazil vs Morocco | draw | 8 | 65c | -250c |
| Netherlands vs Japan | draw | 2 | 17c | 88c |
| Ivory Coast vs Ecuador | home | 1 | 8c | 347c |
| Spain vs Cape Verde | draw | 4 | 14c | 1791c |
| Belgium vs Egypt | draw | 5 | 35c | -205c |
| Saudi Arabia vs Uruguay | draw | 3 | 26c | -106c |

## Outcome Buckets

| Actual outcome | Matches | Fills | Fees | PnL | PnL/match | PnL/fill |
|---|---:|---:|---:|---:|---:|---:|
| draw | 6 | 31 | 179c | 3491c | 581.8c | 112.6c |
| home | 2 | 3 | 19c | 171c | 85.5c | 57.0c |

## Fill Buckets

| Minute band | Fills | Avg entry | Fees | PnL | PnL/contract |
|---|---:|---:|---:|---:|---:|
| 00-15 | 14 | 18.6c | 69c | 2131c | 30.4c |
| 16-30 | 12 | 22.8c | 69c | 906c | 15.1c |
| 31-45 | 8 | 31.1c | 60c | 625c | 15.6c |

| Price band | Fills | Avg entry | Fees | PnL | PnL/contract |
|---|---:|---:|---:|---:|---:|
| 00-24c | 19 | 11.2c | 71c | 4294c | 45.2c |
| 25-49c | 13 | 36.1c | 109c | -114c | -1.8c |
| 50-74c | 2 | 50.0c | 18c | -518c | -51.8c |

| Side/outcome/minute | Fills | Avg entry | Fees | PnL | PnL/contract |
|---|---:|---:|---:|---:|---:|
| buy draw 00-15 | 7 | 13.6c | 31c | 2494c | 71.3c |
| buy draw 16-30 | 4 | 12.5c | 16c | 1734c | 86.7c |
| buy draw 31-45 | 3 | 25.7c | 20c | 1095c | 73.0c |
| buy away 16-30 | 5 | 36.8c | 42c | -962c | -38.5c |
| buy home 31-45 | 3 | 43.0c | 27c | -672c | -44.8c |

## Strategy Comparison

| Strategy | Ending bankroll | PnL | ROI | Max drawdown | Fills | Fees |
|---|---:|---:|---:|---:|---:|---:|
| Hold draw, no new draw buys after 45' | 13662c | 3662c | 36.62% | 311c | 34 | 198c |
| Original draw sells allowed, draw buys allowed to 90' | 11037c | 1037c | 10.37% | 1255c | 47 | 298c |

## Late Underdog Hypothesis

Command:

```bash
PYTHONPATH=src python3 -m thinkinginbets.cli late-underdog \
  --dates 20260611-20260620 \
  --max-matches 10 \
  --quantity 5
```

Test definition: classify the underdog from the first replay tick's home/away ask prices, then buy
5 underdog contracts once at the first available tick in each late band.

| Band | Fills | Avg entry | Fees | PnL | PnL/contract |
|---|---:|---:|---:|---:|---:|
| 46-60 | 8 | 20.0c | 43c | -343c | -8.6c |
| 61-75 | 8 | 21.5c | 41c | -401c | -10.0c |
| 76-90 | 7 | 16.4c | 28c | -103c | -2.9c |

Total: 23 hypothetical bets, -847c.

Current read: late underdog is not a blanket edge in this replay set. The sample is draw-heavy, and
"underdog not losing" has mostly paid as draw, not underdog win. A better hypothesis would be
underdog-plus-draw synthetic exposure when the combined price is under fair value, or underdog-only
after a concrete state shock such as red card, injury, or sustained pressure that has not repriced.

## Underdog Plus Draw Hypothesis

Command:

```bash
PYTHONPATH=src python3 -m thinkinginbets.cli double-chance \
  --dates 20260611-20260620 \
  --max-matches 10 \
  --quantity 5
```

Test definition: classify the underdog from the first replay tick's home/away ask prices, then buy
5 underdog contracts and 5 draw contracts once at the first available tick in each late band.

| Band | Fills | Avg combined price | Cost | Fees | PnL | ROI on cost |
|---|---:|---:|---:|---:|---:|---:|
| 46-60 | 8 | 47.4c | 1992c | 97c | 1508c | 75.70% |
| 61-75 | 8 | 52.5c | 2197c | 97c | 1303c | 59.31% |
| 76-90 | 7 | 55.6c | 2025c | 80c | 1475c | 72.84% |

Total: 23 hypothetical baskets, 6214c cost, 4286c PnL.

Current read: underdog plus draw works very well on this sample because it expresses the actual
World Cup state better than underdog-only: "favorite may fail to win" rather than "underdog wins."
It is still exposed to favorite wins, so it should not be a blind late-game rule. It needs a maximum
combined price, game-state filters, and favorite-pressure checks.

Selective variants:

| Filters | Bets | Cost | PnL | ROI on cost |
|---|---:|---:|---:|---:|
| No filters | 23 | 6214c | 4286c | 68.98% |
| Favorite not leading | 21 | 6445c | 4055c | 62.92% |
| Favorite not leading, combo <= 80c | 18 | 4899c | 4101c | 83.71% |
| Favorite not leading, combo <= 70c | 14 | 3301c | 3699c | 112.06% |
| Favorite not leading, combo <= 60c | 8 | 1235c | 2765c | 223.89% |
| Favorite not leading, combo <= 50c | 6 | 632c | 2368c | 374.68% |

Current selection rule candidate: do not bet every match. Prefer underdog+draw only when the favorite
is not leading and the combined underdog+draw ask is below a hard cap. The exact cap should be tuned
with more completed matches; this sample favors very selective caps, but it is too draw-heavy to
trust as a final production threshold.

## Favorite-Wins Stress

Command:

```bash
PYTHONPATH=src python3 -m thinkinginbets.cli favorite-stress \
  --dates 20260611-20260620 \
  --max-matches 10
```

Test definition: run the default replay strategy, then resettle the same fills as if each match's
first-tick favorite won.

| Scenario | PnL |
|---|---:|
| Actual replay outcomes | 3662c |
| Counterfactual favorite wins | -2338c |
| Stress delta | -6000c |

Current read: the draw-focused strategy has real regime risk. If favorites start winning instead of
settling draw, the current default flips from +3662c to -2338c on the same entries. This is the
strongest evidence so far that we need a draw-regime detector and draw exposure cap, not just a
profitable default on a draw-heavy sample.

## League And Qualifier Odds Validation

Command:

```bash
PYTHONPATH=src python3 -m thinkinginbets.cli odds-double-chance \
  --league eng.1 \
  --dates 20260501-20260531 \
  --limit 100
```

This uses ESPN/DraftKings moneylines as a price proxy. It is not Kalshi execution, but it validates
the underdog+draw thesis against a broader soccer sample.

| League/date sample | Filter | Bets | Cost | PnL | ROI on cost |
|---|---|---:|---:|---:|---:|
| EPL, May 2026 | none | 41 | 2005.5c | 294.5c | 14.68% |
| EPL, May 2026 | combo <= 50c | 18 | 670.3c | 129.7c | 19.34% |
| World Cup, completed through Jun 16 | combo <= 70c | 16 | 685.2c | 314.8c | 45.95% |
| UEFA WCQ, Mar 2026 | none | 12 | 552.0c | -52.0c | -9.42% |
| UEFA WCQ, Mar 2026 | combo <= 50c | 6 | 205.8c | -5.8c | -2.80% |

Current read: the approach is not universally good. EPL and this World Cup sample support it;
UEFA qualifiers do not. That means "underdog+draw" is a regime strategy, not a magic ticket. The
bot needs to recognize when favorites are converting and sit out instead of forcing action.

## Read

The current money is coming from early draw exposure, not from a generic strong-team narrative.
The first scorecard made "late draw is bad" look plausible, but side-specific diagnostics showed the
real leak: selling draw positions in matches that later settled draw. Promoting "hold draw exposure"
and capping new draw buys after 45' improved the benchmark from 1037c to 3662c.

The biggest remaining problem is non-draw buying. Away buys from 16-30' and home buys from 31-45'
are both clearly negative in this sample. The next tuning pass should add outcome-specific entry
gates for non-draw buys, then rerun this same scorecard before changing defaults.
