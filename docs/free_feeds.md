# Free And Free-Tier Feeds

## Recommended Free-First Stack

1. ESPN public scoreboard endpoints as the first no-key live score/stat collector.
2. API-Football / API-Sports only for occasional confirmation because the free tier is too small.
3. football-data.org for fixtures, scores, and lower-frequency polling.
4. Kalshi and Polymarket WebSockets for market/order-book data.
5. Respectful page scraping only when a source exposes useful public HTML/embedded JSON and no API.

## Why Not Only Kalshi Or Polymarket?

Exchange feeds are free to use once you have exchange access, and they are required for:

- order books,
- price changes,
- trades,
- fills,
- market status.

They are not enough for autonomous match trading because they do not give an independent source
of goals, cards, substitutions, injuries, or match statistics. The bot needs both market state
and match state.

## Free Feed Notes

### ESPN Public Endpoints

ESPN exposes public JSON endpoints used by its site/app, including:

`https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard`

For World Cup matches, the scoreboard payload includes score, clock/status, event details, and
team statistics such as `possessionPct`, `wonCorners`, `shotsOnTarget`, and `totalShots`.

This is our best no-key starting point. It is still undocumented and can change without notice,
so cache responses, monitor schema drift, and do not rely on it as the only live signal.

### API-Football / API-Sports

API-Sports says its free plan is free forever and includes 100 requests per day for each API.
It also says football livescore data is real-time and updated every 15 seconds, and API-Football's
World Cup 2026 guide says the competition is available with `league=1` and `season=2026`.

100 requests/day is not enough for live trading. Use it for pre-match setup and sparse confirmation.

### football-data.org

football-data.org has a free registered tier at 10 requests/minute and supports match status
filters such as `LIVE`, `IN_PLAY`, and `FINISHED`. It is useful for fixture/status polling, but
the free tier should be treated as slower and less event-rich than dedicated live feeds.

### Sportmonks

Sportmonks has a free plan, but its free football plan is limited to Danish Superliga and Scottish
Premiership. It is good for integration testing, not World Cup coverage unless their current World
Cup trial/free terms give explicit access.

### TheSportsDB

TheSportsDB offers a free JSON sports API. Its page says 2-minute livescores are part of the
premium API, so this is not the primary free live source for autonomous in-play trading.

### Scraping Web Pages

Scraping can help when no free API is available, but it is operationally fragile and may be
restricted by site terms. Use this hierarchy:

1. Public JSON endpoint used by the page.
2. Embedded JSON in the HTML.
3. Static HTML parsing.
4. Browser rendering only when the data is client-side rendered.

Poll slowly, identify the client with a reasonable user agent, cache responses, and stop if blocked.
Scraped data should be marked `free_untrusted` in decision logs.

## Autonomous Policy

On free feeds, do not trade as if the data is low latency.

- Allow pre-match and slow in-play paper decisions.
- Use ESPN stats for score, minute, possession, corners, shots, and shots on target.
- Require two feed confirmations for goals or red cards before increasing exposure.
- Allow exposure reduction on one feed confirmation.
- Pause new positions when all sports feeds are stale or disagree.
- Record feed age and provider name with every trade intent.
