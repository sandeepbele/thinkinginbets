# Thinking in Bets

I built this as a World Cup side project to explore soccer bets on prediction markets. Picking a match winner is only part of the problem: a bet makes sense only when the estimated chance of an outcome is better than the price being offered, after fees and other costs. I wanted to see how that calculation would change as a match unfolded.

The project models home, draw, and away outcomes, compares those probabilities with market quotes, checks risk limits, and records hypothetical trades through a paper broker. It includes synthetic match scenarios and historical replay experiments using public ESPN match data and Kalshi market data. I also explored simple team-strength priors, in-play updates, and an optional adapter for a trained `penaltyblog` model.

This is a research and paper-trading project. The Kalshi and Polymarket order adapters are placeholders that raise `NotImplementedError`; the code does not place live bets. The replay scorecards in `docs/` are snapshots of small historical experiments, not evidence of a reliable trading edge.

## Try it locally

From the repository root, run the tests and a self-contained paper simulation:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m thinkinginbets.cli paper --ticks 4
PYTHONPATH=src python3 -m thinkinginbets.cli live-scenario
```

The paper simulation uses built-in example market ticks and does not need an account or API key. Commands that fetch fixtures or replay public market data depend on external services; see `PYTHONPATH=src python3 -m thinkinginbets.cli --help` for the available experiments.

## Project layout

- `src/thinkinginbets/models/` estimates match-outcome probabilities.
- `src/thinkinginbets/feeds/` reads and normalizes match data.
- `src/thinkinginbets/strategy.py` compares model value with market prices.
- `src/thinkinginbets/risk.py` applies limits before a paper order.
- `src/thinkinginbets/paper.py` simulates fills and accounting.
- `src/thinkinginbets/kalshi_espn_replay.py` replays public match and market data.
- `docs/` contains the original strategy notes, feed research, and replay scorecards.

The local paper-bet journal and cached API responses are intentionally excluded from this repository. The source folder had no commits, so this public repository begins with a new Git history.
