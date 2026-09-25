# Thinking in Bets

> **Archived project.** This is an older fun project around soccer prediction markets and paper trading. It is not maintained, and the external data integrations have not been recently revalidated.

**Model soccer outcomes, compare them with prediction-market prices, and simulate bets as a match unfolds.**

I built this during recent soccer World Cup. A match prediction by itself does not tell you whether a bet is worthwhile. The interesting question is whether the estimated probability of an outcome differs enough from the probability implied by the market price.

Thinking in Bets explores that problem for soccer prediction markets.

The system estimates probabilities for **home win, draw, and away win**, compares them with market quotes, applies basic risk limits, and records hypothetical trades through a paper broker.

During a match, probabilities can be recalculated as new information arrives—such as the current score, match minute, and available match statistics.

## How it works

At each evaluation point, the pipeline:

1. reads the latest match state
2. estimates probabilities for home, draw, and away outcomes
3. reads the corresponding prediction-market prices
4. compares model probabilities with market-implied probabilities
5. checks whether the difference is large enough after fees and configured thresholds
6. applies risk limits
7. records a simulated trade when the criteria are met

The in-play model updates its prediction from the latest match state. It does **not** retrain during the match; the underlying pre-match team-strength ratings remain fixed.

There is also an optional adapter for a separately trained [`penaltyblog`](https://github.com/martineastwood/penaltyblog) model.

## Historical replay

The repository includes experiments that replay historical matches using public ESPN match data together with Kalshi market data.

The replay aligns match events with one-minute market candles and repeatedly evaluates what the strategy would have seen as the game progressed.

This makes it possible to inspect questions such as:

- how model probabilities moved after goals or other changes in match state
- how those probabilities compared with prediction-market prices
- when the strategy would have identified an apparent pricing difference
- what hypothetical paper trades would have resulted

The replay has an important limitation: historical match feeds tell us when an event occurred, but not necessarily when that information became available to a real-time observer.

For example, if a goal occurred at 65:10 but the data provider published the update several seconds later, a historical replay can accidentally give the model information earlier than it would have received it live.

The replay results should therefore be treated as exploratory rather than as a rigorous backtest of executable trading performance.

## Paper trading

The project contains a paper broker for simulating orders, fills, and accounting.

It does **not** place live bets.

The Kalshi and Polymarket order adapters are placeholders and raise `NotImplementedError`. Replay scorecards under `docs/` are snapshots of small historical experiments rather than evidence of a persistent trading edge.

## Try it locally

From the repository root:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m thinkinginbets.cli paper --ticks 4
PYTHONPATH=src python3 -m thinkinginbets.cli live-scenario
```

The paper simulation uses built-in example market ticks and does not require an account or API key.

Commands that fetch fixtures or historical market data depend on external services. Run:

```bash
PYTHONPATH=src python3 -m thinkinginbets.cli --help
```

to see the available experiments.

## Project layout

```text
src/thinkinginbets/
├── models/                 Match-outcome probability models
├── feeds/                  Match-data ingestion and normalization
├── strategy.py             Model probability vs. market price
├── risk.py                 Risk limits for paper orders
├── paper.py                Simulated fills and accounting
└── kalshi_espn_replay.py   Historical match/market replay

docs/                       Strategy notes, feed research, and replay results
```

## Project status

Thinking in Bets is an archived research and paper-trading project.

The repository contains working simulations and historical replay experiments, but it should not be treated as a live trading system or as evidence of a profitable betting strategy. External APIs, market formats, and dependencies may also have changed since the project was developed.
