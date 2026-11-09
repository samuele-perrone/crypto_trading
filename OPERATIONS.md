# Operations & project log

Working notes for running this bot and picking the work back up later.
`README.md` covers the strategy and first-time setup; this file covers what is
deployed, how it behaves in production, why things are the way they are, and
the traps that already cost time once.

Last updated: 2026-11-09.

## Current status

- **Live URL:** `https://cryptotrading-omega.vercel.app/api/tick`
- **Status URL (read-only, public):**
  `https://cryptotrading-omega.vercel.app/api/status` — price, SMAs, the close
  that would trigger the next trade, open/flat, 180 days of history. Feeds the
  claude.ai "ETH bot" dashboard artifact through the Vercel connector. Added
  2026-11-08; see **Decisions**.
- **Daily report look-ahead (2026-11-08):** the 📊 heartbeat carries a
  "Next buy/sell" line. Normally it leads with the cross, not a price ("when
  SMA20 closes above SMA30, at whatever the price is then") and quotes the
  steady average ETH needs to get there within 10 and 20 days, plus whether
  today's price held flat ever does. When the very next close could trade —
  within `HEADS_UP_PCT` (default 3%) of the one-day trigger, or already past
  it — it names that close instead and leads with "⏳ BUY/SELL may be coming".
  Unset in Vercel = default.
- **Mode: LIVE since 2026-09-11.** `LIVE=true` in Vercel production — real
  market orders. The simulated position was deleted in the same change, so the
  bot started flat and enters only on a fresh cross up.
- **Schedule:** Vercel Cron, daily at 00:15 UTC (`vercel.json`), just after the
  daily candle closes — the only moment an SMA signal can change.
- **Config:** ETH/USD, SMA 20/30 on daily candles, no stop-loss, no
  take-profit. **Sizing: `TRADE_PCT=100`** — every buy uses the whole USD
  balance, less the fee headroom (at $65.81 that is a $64.96 stake costing
  $65.48 at Kraken's 0.80% entry-tier taker fee; `TAKER_FEE` raised from
  0.26% on 2026-11-08 — see **Decisions**). `USD_PER_TRADE=20` remains only as the fallback for when the
  balance cannot be read. The tick echoes `sizing`, `trade_pct` and
  `usd_per_trade`, since `vercel env ls` cannot show values.
- **State:** private Vercel Blob store `crypto-trading-state`, object
  `production/bot_state.db`.
- **Kraken account:** $65.81 USD, no ETH. API key verified end to end.
- **Entry rule: `ENTER_ON_TREND` on (default) since 2026-11-03.** A flat bot
  buys at the next tick whenever SMA20 is above SMA30, not only on the day of
  a cross up. Before this, the bot had sat flat for ~8 weeks of live running
  because it went live mid-uptrend and was waiting for the trend to end and a
  new one to start. Set `ENTER_ON_TREND=false` to restore cross-only entry.

### Going live — what to watch

- **The daily 📊 heartbeat must keep arriving.** Errors inside a tick are
  caught and sent as ⚠️ Telegram alerts, but a failure *outside* the handler —
  an import error on cold start, a broken deployment, or cron not firing at
  all — sends nothing. Silence is the only symptom of that class, which is why
  the heartbeat exists. Missing heartbeats mean broken, not "no signal".
- **The first 🟢 BOUGHT alert should carry a `txid`.** Dry-run alerts never do.
- **Stop condition:** a buy that fills but does not persist, or two buys with
  no sell between them. Unset `LIVE` and redeploy to halt immediately.

### Readiness for live

Everything that can be tested without money has been, and one thing that
could not was tested with 4 cents (see **Testing** below): strategy rules,
the sell path, Kraken auth and permissions, and a real fill.

Two steps remain, and they belong in the same change:

1. **Clear the stored position.** It is simulated — the coin was never bought,
   so the bot's first live action would be a sell of something it does not
   hold. `vercel blob del production/bot_state.db --rw-token "$BLOB_READ_WRITE_TOKEN"`
2. **Set `LIVE=true` and redeploy.** Env changes need a new deployment.

Then expect to wait. SMA20 is currently well above SMA30, so a flat bot needs
a cross down followed by a fresh cross up before it enters — plausibly weeks,
on a strategy that traded 13 times in two years. The daily heartbeat is how
you tell "waiting" from "broken".

## Scaling the trade size

**Set to `TRADE_PCT=100` on 2026-09-11**: every buy uses the whole USD balance
rather than a fixed amount, so gains compound with no further changes. This is
intended to be the last sizing change — the stake tracks the balance by
itself.

It also means the entire account rides on every trade, with no reserve. That
was judged defensible on the 2024–2026 backtest (worst trade −5.0%, max
drawdown −4.7%), but that window understates the risk. **Over ETH's full
history (2016-07 → 2026-11, `long_results.md`, 0.80% fee) the same rule lost
84% peak to trough (Jan 2018 → Nov 2019; −80% even before fees), with −40% and
−47% calendar years back to back.** It still compounded at 81%/yr over the
decade, so the strategy is not broken, but a full-balance stake means the
account can fall by four-fifths and stay down for years. It is a real choice,
not a default. To dial back, set `TRADE_PCT`
to a smaller percentage; to pin a fixed amount, set `TRADE_PCT=0` and use
`USD_PER_TRADE`.

```sh
echo "50" | vercel env add TRADE_PCT production   # or 0 for a fixed stake
git commit --allow-empty -m "adjust sizing" && git push
```

Note the account must hold only money intended for trading: at 100% the bot
will spend USD deposited for any other purpose.

Three things make a larger size safe, all in `kraken_bot.py` and covered by
tests:

- **You cannot spend the whole balance.** A $65.81 stake costs $65.81 plus the
  0.80% taker fee = $66.34, more than the balance, and the order is rejected.
  `affordable_usd()` derives the real ceiling, and `trade_stake()` caps every
  stake to it — so an over-sized `USD_PER_TRADE` is clamped rather than
  bouncing. The tick reports `usd_available`, `stake`, and `stake_capped_from`
  when that happens.
- **`TRADE_PCT` compounds.** A fixed dollar amount stays fixed as the account
  grows; set `TRADE_PCT=90` to size from the live balance instead. The same
  fee cap applies.
- **The balance is read before buying.** Kraken's validate does not check
  funds, so this is the only pre-flight that catches underfunding. If the
  balance call fails the tick proceeds and lets the order fail loudly — the
  reported `balance_check` field says so.

Diversifying across coins was considered and rejected on 2026-09-11: the
strategy's result swings from −27%/yr (LTC) to +79%/yr (XRP) by asset, but
daily returns correlate **0.74** on average (0.83 with BTC), so a basket
spreads the same bet rather than reducing risk. Equal-weighting all ten tested
pairs returned +16.8%/yr against ETH's +62.9% — though that gap flatters ETH,
which was chosen partly because it won. Revisit only if the account grows
enough that variance matters more than the added complexity of multi-pair
state.

## How a tick works

`api/tick.py` is the whole production path. One HTTP GET = one strategy tick.

1. Reject the request unless `Authorization: Bearer $CRON_SECRET` matches.
2. Resolve the pair on Kraken, fetch daily closes and the current price.
3. Compute the SMA crossover signal on **closed candles only** — the still
   forming candle is dropped, so signals never flicker intraday.
4. Load the open position from state.
5. Sell if stop-loss, take-profit, or an SMA cross down fires. When flat, buy
   on a cross up, or (with `ENTER_ON_TREND`, the default) whenever the fast
   SMA is already above the slow one — see `buy_reason()`. In dry-run everything runs except the Kraken order call.
6. Persist the new position, notify Telegram, return the tick as JSON (also
   printed to the Vercel function log).
7. If nothing traded, compute the look-ahead with `next_trade()` — the next
   daily close that would cross the SMAs (`cross_trigger_price()`). It runs
   after every decision is final, is informational only, and sits in a
   `try` so a bug there lands in `next_trade_error`, never in the trade.

If nothing traded, it still sends a daily 📊 heartbeat so silence means
"broken", not "no signal". Disable with `DAILY_REPORT=false`. The heartbeat
includes the look-ahead line, and a ⏳ headline when the trigger is near.

### The trigger price

Tomorrow's SMAs both include tomorrow's close P, so the crossing point is
exact, not an estimate: with A and B the sums of the last 19 and 29 closes,
SMA20 = SMA30 when `P = (20·B − 30·A) / 10`. Flat, a close above P buys at the
next 00:15 tick; holding, a close below P sells. `test_strategy` feeds every
trigger back through `crossover_signal()` to prove it. When the SMAs are far
apart the trigger can be unreachable (≤ 0, or a huge move); `next_trade()`
sets `trigger` to None for the non-positive case.

**The one-day trigger is not the bar to clear.** The bot trades at whatever
the price is once the cross happens; the trigger is only what forces it *by
tomorrow*. On 2026-11-08 it read $4,875.70 with ETH at $2,225 (+119%) and was
read as "the bot waits for $4,875" (see **Decisions**). So `next_trade()` also
returns `path`: for 1, 5, 10, 15 and 20 more closes, the steady average close
that gets the cross by then (`average_needed()`; same algebra with N closes:
`P = (20·B − 30·A) / (10·N)`, A and B now the last 20−N and 30−N closes), and
`days_if_flat`: closes at today's price until the cross, or None. That day the
path read $2,797 / $2,494 / $2,303 / $2,267 for 13 / 18 / 23 / 28 Nov, and
flat never crossed: SMA20 > SMA30 just means the last 20 closes average above
the 10 before them, so it needs recent prices to beat slightly older ones.
`test_strategy` pins those real figures.

### `/api/status` and the routing quirk

The project deploys with Vercel's Python framework preset
(`framework: python`), where the pyproject entrypoint `api.tick:handler` may
receive every path. So `/api/status` is answered from **both** places:
`api/status.py`'s own handler, and a dispatch at the top of
`tick.handler.do_GET` that matches exactly `/api/status` (query ignored) and
hands it to `status.status_response()`. Every other path, including
`/api/tick`, still goes through the `CRON_SECRET` check and the tick, unchanged.

The status path never trades or writes: keyless `KrakenClient()` (public
calls only), and `load_position()` only, which pulls the Blob file into its own
`/tmp` scratch copy and pushes nothing. `test_status` pins all of this. It also
reports `checks.tick_module` — whether `api/tick.py` imports cleanly on the
live deployment, a failure class that otherwise only shows as a missing
heartbeat. Responses are CDN-cached 60 s.

## State storage

This is the part that is easy to get wrong, and was wrong once.

**The problem.** Vercel functions can only write to `/tmp`, and `/tmp` is wiped
between invocations. A SQLite file sitting on disk therefore starts empty on
every tick. The bot would buy, forget it had bought, never sell, and buy again
on the next cross up — with real money once live. It was deployed in this
broken state on 2026-08-20 and fixed the same day.

**The fix.** The SQLite file rests in a private Vercel Blob store between
ticks: pulled before every read, pushed after every write. It is still an
ordinary SQLite file with a `bot_state(key, value, updated_at)` table — Blob is
only where it lives while no function is running. All of this is in
`state_store.py`; `api/tick.py` just calls `load_position` / `save_position`.

Four properties worth preserving if you touch that file:

- **Reads are cache-busted.** Blob reads go through a CDN. A read seconds after
  an overwrite was observed returning the *previous* file (`x-vercel-cache:
  HIT`). A stale position is a wrong trade, so every GET carries a unique query
  param. Do not remove it.
- **A failed pull raises.** It deliberately does not fall back to an empty
  database, because "no position" is exactly the dangerous wrong answer — it
  makes the bot buy again while already holding. A failed tick returns 500 and
  fires a Telegram alert instead.
- **A 404 is not believed on its own.** Blob reads are eventually consistent:
  an object that definitely existed returned 404 on roughly **one read in
  eight** during testing. Since 404 previously meant "no state yet", that was a
  live path to the exact failure the store is meant to prevent. Absence is now
  confirmed against the list API (`GET /?prefix=…`, not CDN-cached); a 404 for
  an object that does exist is retried and then raised.
- **Environments are separated.** The object name defaults to
  `<VERCEL_ENV>/bot_state.db`, so a local test tick writes `development/…` and
  cannot clobber production's position.

Without `BLOB_READ_WRITE_TOKEN` the bot falls back to a plain local file — the
right behaviour off Vercel, ephemeral on it. When that combination is detected
the tick response carries a `state_warning` field.

### Vercel Blob HTTP contract

Vercel documents only the JS SDK. The Python client here talks to the REST API
directly, and this contract was derived by running the real SDK against a local
logging server. Recorded because re-deriving it is tedious.

Upload:

```
PUT https://blob.vercel-storage.com/?pathname=<name>
  Authorization: Bearer $BLOB_READ_WRITE_TOKEN
  x-api-version: 12
  x-vercel-blob-access: private
  x-add-random-suffix: 0
  x-allow-overwrite: 1
  x-cache-control-max-age: 0
  Content-Type: application/octet-stream
  <body = file bytes>
```

The pathname is a **query parameter**, not a path segment. Putting it in the
path returns `{"error":{"code":"bad_request","message":"Invalid pathname"}}`.

Download:

```
GET https://<store-id-lowercased>.private.blob.vercel-storage.com/<pathname>?cb=<unique>
  Authorization: Bearer $BLOB_READ_WRITE_TOKEN
```

The store id is the 4th underscore-separated field of the token
(`vercel_blob_rw_<storeId>_<random>`), lowercased for the hostname — the same
derivation the official SDK uses. Without the bearer token the request returns
403, which is the point of a private store. A 404 means "missing" only after
the list API agrees; see the consistency note above.

Existence check and delete:

```
GET  https://blob.vercel-storage.com/?prefix=<pathname>&limit=100
POST https://blob.vercel-storage.com/delete   {"urls": ["<blob url>"]}
```

## Testing

Four layers, because each catches what the others cannot.

**1. Deterministic rules** — `python3 -m unittest test_strategy test_state_store test_status`

No network, no keys, runs in a second. `test_strategy` covers when to buy, when
to sell, and how much: crossover edges (the signal must fire once, not every
day of a trend), stop-loss and take-profit thresholds and their precedence, `0`
meaning "disabled" rather than "sell at breakeven", and rounding that never
overspends the stake. `test_state_store` stubs HTTP and pins the one-directional
safety property — failing loudly is fine, reporting "no position" when one may
be held is not. `test_status` covers the look-ahead and `/api/status`: the
status payload never exposes volumes, never reaches a trading or writing call,
and the handler routes only `/api/status` past the secret; a broken look-ahead
or report formatter still delivers the heartbeat. Run all three after touching
`kraken_bot.py`, `state_store.py` or anything in `api/`.

**2. End-to-end sell rehearsal** — `python3 rehearse_sell.py`

Waiting for a real cross down can take weeks, so this seeds a position in an
isolated Blob namespace (`development/rehearsal-<timestamp>.db`, unique per run
and deleted afterwards), forces a take-profit, and
runs the real `run_tick()`. Proves the whole sell path — realized P&L, cleared
state, and the push of that cleared state to Blob. It refuses to run against
`production/` and stays silent on Telegram unless given `--notify`.

**3. Kraken order validation** — `python3 rehearse_sell.py --validate`

Sends the order to Kraken with `validate=true`: real authentication, real
signing, real pair and volume checks, nothing placed. This is the **only** test
that exercises the credentials, and it immediately caught a key missing the
order permission. Set `VALIDATE=true` in Vercel to run the deployed bot the
same way. Caveat: Kraken's validate does not check balance, so "insufficient
funds" still only surfaces when live.

**4. Live smoke trade** — `python3 smoke_trade.py` (preview) / `--yes` (real)

One real minimum-size round trip, ~$2.50 of exposure for a few seconds. The
only test that reaches actual execution: balance sufficiency (Kraken's validate
does not check funds), a real fill, a real txid, and any account-level
restriction. Run on 2026-09-11: buy `OHJY5F-ZYV3R-QFRN5K`, sell
`OAQ3MR-I2ZFH-CGPB5J`, total cost **3.95¢** on $2.46. Volume is always the
exchange minimum and the script aborts above `MAX_COST_USD`.

### Modes

`api/tick.py` has three, in increasing order of consequence:

| Mode | Env | Kraken order call |
|---|---|---|
| dry-run | neither set (default) | none |
| validate | `VALIDATE=true` | `AddOrder` with `validate=true`, nothing placed |
| live | `LIVE=true` | real market order |

`LIVE` wins if both are set. Everything else — signals, state, notifications —
runs identically in all three, so dry-run genuinely exercises the logic.

## Deploying

Pushing to `main` triggers a Vercel build automatically. This was broken around
2026-08-18 and confirmed working again on 2026-08-20.

```sh
git push                       # normally all you need
vercel ls --prod               # confirm a new deployment appeared
vercel --prod --yes            # fallback if no build was triggered
```

If you deploy manually *and* a push builds the same commit, both deployments
race for the production alias. `vercel alias ls` is the authoritative mapping
of alias → deployment; `vercel inspect <deployment>` lists aliases it has ever
held, which is misleading.

## Runbook

Test a tick by hand (note: this fires a real Telegram message, and in dry-run
it can still write state):

```sh
curl -H "Authorization: Bearer $(grep -o '[^=]*$' .cron_secret_local)" \
  https://cryptotrading-omega.vercel.app/api/tick
```

Only the production alias works — per-deployment URLs sit behind Deployment
Protection and return a redirect.

Inspect or clear stored state:

```sh
TOKEN=$(grep '^BLOB_READ_WRITE_TOKEN=' .env.local | cut -d= -f2- | tr -d '"')
vercel blob list --rw-token "$TOKEN"
vercel blob del production/bot_state.db --rw-token "$TOKEN"   # forget the position
```

Deleting the object resets the bot to "no position". That is the recovery
action if stored state ever disagrees with the Kraken account.

Going live, once funded:

```sh
vercel env add LIVE production      # value: true
git commit --allow-empty -m "go live" && git push   # env changes need a redeploy
```

Env var changes only take effect on a new deployment. Watch the next tick, and
keep in mind a signal may not appear for weeks — 13 trades in 2 years.

## Decisions

**`TAKER_FEE` raised from 0.26% to 0.80% (2026-11-08).** Kraken redesigned
its Pro fee tiers in July 2026: the entry tier (under $2.5K of 30-day spot
volume) is now 0.40% maker / 0.80% taker (Kraken's published fee schedule,
checked 2026-11-08). The bot still assumed 0.26%, so a `TRADE_PCT=100` buy on
$65.81 was sized at $65.31 and would have cost $65.83 — $0.02 over the
balance, an "insufficient funds" rejection on the first live buy. Kraken's
validate mode does not check funds, so no rehearsal would have caught it. The
constant is set to the worst tier the account can be on; the stake is now
$64.96. Every backtest reads the same constant, so results recorded before
this date (`backtest_results.md`, the comparisons below) used 0.26%/side and
overstate returns: about 1.1 points per round trip, ~14 points over the
deployed rule's 13 trades in two years. `test_strategy` pins the 0.80% case.

**Lead the look-ahead with the cross and an average path, not the one-day
trigger (2026-11-08).** The first version reported "the next buy needs a daily
close above $4,875.70", which reads as a price target the bot waits for. It
does not: it buys at any price once SMA20 closes above SMA30. The one-day
figure is now shown only when it is close enough to matter (`near`); otherwise
the report and dashboard show the average needed by date. Replaced the
interim "- not a one-day move yet" suffix (`FAR_PCT`) the same day.

**Look-ahead in the daily report, and a public read-only status endpoint
(2026-11-08).** Asked for: a Telegram heads-up before a trade, and a
dashboard. The heads-up is folded into the existing daily 📊 message (a ⏳
headline when near) rather than a second message, so there is still exactly
one message a day and "no message" still means "broken". The dashboard is a
claude.ai artifact; artifacts cannot call outside hosts, so it reads
`/api/status` through the claude.ai Vercel connector (`web_fetch_vercel_url`).
The endpoint is public rather than secret-protected because a token embedded
in the artifact page would be no secret; instead it exposes nothing beyond
market data, the rules, open/flat and the entry price — no balances, volumes
or txids. Supabase was not considered, per the 2026-08-20 decision below.

**Enter on trend state, not only on the cross (2026-11-03).** Live since
2026-09-11 with zero trades: the bot went live flat while SMA20 was already
above SMA30, and a cross-only rule then waits for a cross down *and* a fresh
cross up before entering — on a system that crosses ~7 times a year, that can
be months. `buy_reason()` now also buys when flat and fast > slow.

What it changes and what it does not: in normal operation nothing — after a
cross-down sell the fast SMA is below the slow one, so only a fresh cross up
re-enters, exactly as before. It only matters when the bot is flat during an
uptrend: first start, a restart with cleared state, or (if ever enabled) after
a stop-loss/take-profit exit. The cost is that such an entry can come late in
a trend that is about to roll over; the worst case is one losing trade sized
like any other, ended by the next cross down. `backtest.py` gained
`--no-enter-on-trend` to compare the two.

Backtested 2026-11-03 with `compare_strategies.py` (ETH/USD daily,
2025-01-13 → 2026-11-02, full balance compounded, 0.26%/side): identical over
the full period (+108.6%, 13 buys, max DD −17.6%), and +29.8% vs +28.7% on
average across 38 simulated go-live dates, same worst case (−6.0%). A small
gain, no added risk — it only removes the idle-start problem.

**Supabase removed (2026-08-20).** State used to live in a Supabase `bot_state`
table over PostgREST. Removed at the user's request — code, Vercel env vars,
and local `.env.local` — and the service role key was rotated. Do not
reintroduce it.

**Take-profit rejected (2026-08-22).** Tested every level against off, 719 days
of real Kraken daily candles:

| TP | ETH SMA20/30 ann. | BTC SMA10/30 ann. |
|---|---|---|
| **off** | **+64.6%** | **+14.4%** |
| 5% | +19.1% | −13.3% |
| 10% | +29.8% | +0.6% |
| 20% | +34.4% | +1.1% |
| 30% | +49.6% | +11.3% |

Every level underperformed. ETH's 13 trades were `+45.0%, +36.8%, +36.2%`, then
nothing above `+7.2%` — the top two supply 68% of all profit. This is
trend-following: a take-profit truncates precisely the few outsized winners
that pay for all the small losses, while leaving every loser intact. Capping at
10% forfeits 88 points across 3 trades.

Note the trap: a 5% take-profit *raises* the win rate from 62% to 79% while
cutting returns by two-thirds. Judge changes on total return, not win rate.

**Re-tested 2026-11-09 on ten years and with re-entry — still rejected.**
Since `ENTER_ON_TREND`, a take-profit sale is followed by a re-buy at the next
tick while SMA20 is above SMA30, so it no longer ends the trade for the rest
of the trend; the August test predates that. `takeprofit_backtest.py`
(results in `takeprofit_results.md`, `takeprofit-backtest` workflow), daily,
0.80% taker. ETH 2016-07 → 2026-11, no take-profit +45,157% (81%/yr):
`TAKE_PROFIT_PCT=5` +809% (24%/yr), 3% +559%, 10% +4,884%, 20% +6,555%; a
+5% limit order resting on the book (maker fee on the exit) +83%; +5% then
wait for a fresh cross −4.6%. BTC 2015-09 → 2026-11: none +5,174%, 5% at the
tick +107%, resting +6%. Every variant lost on both coins, before and after
2024-11-09, at every fee including zero (ETH, 0%: +33,634% vs +139,232%), and
beat no take-profit in at most 4 of 11–12 calendar years. Re-buying does not
rescue it: each sale sits out the next day of a strong move and re-enters
higher, so one big winner becomes several +5–7% wins and a final loss from a
late entry (ETH average loss −12.7% vs −8.6%). It does not cut risk either:
max drawdown stays −79% to −86% with re-entry; the wait-for-a-cross variant
cuts it to −60% only by giving up almost all the return. Win rate rose to
73–82% throughout. `TAKE_PROFIT_PCT` stays 0.

The same logic argues against a tight stop-loss — the worst trade was only
−5.0%. `STOP_LOSS_PCT` is 0 and untested as of this date.

## Gotchas

- **Filling stops at exactly the stop price invents an edge.** In
  `pattern_backtest.py`, a trailing stop on simulated no-edge paths "beat"
  buy-and-hold by ~30% over 200 days purely because the simulated sell happened
  at the level, while a bot that checks every few minutes sells after the price
  has already crossed it. Stops now fill below the level by the expected
  overshoot (`stop_slip()`, Siegmund's 0.5826 × one check's volatility) and
  `test_pattern.TestStopsDoNotCreateEdge` pins it. Any new backtest with stops
  needs the same check: run it on a random walk and confirm it does not win.
- **Coinbase does not list every Kraken coin.** TRX, SPX and TRUMP needed
  Binance's public data dumps (`data.binance.vision`, timestamps in ms before
  2025 and microseconds after) or KuCoin; both answer from GitHub's runners.

- **Exchange fees change under you.** Kraken's July 2026 fee change tripled
  the taker fee with no API-visible signal, and the bot's sizing silently
  became $0.02 too large to fill. Check Kraken's fee schedule (and the
  account's tier under Settings) whenever sizing or backtests matter, and
  keep `TAKER_FEE` at the worst tier the account can be on.

- **Every path reaches `tick.handler`, not just `/api/tick`.** With the
  Python framework preset and the pyproject entrypoint, a request for
  `/api/status` *before* the 2026-11-08 change came back 401 — it had hit
  the tick handler's `CRON_SECRET` check, not a 404. So a new route cannot be
  added by dropping a file in `api/` alone; it needs the dispatch at the top
  of `tick.handler.do_GET` (see "`/api/status` and the routing quirk").
  Branch pushes build a preview: test a new route on the preview URL first.
- **The claude.ai Vercel connector needs the team authorised**, separately
  from the project: until then `web_fetch_vercel_url` and deployment reads
  fail with 403 "Not authorized ... scope". `authorize_team_access` gives a
  one-time consent link.

- **Freshly bought coin is not immediately sellable.** A smoke trade on
  2026-09-11 bought 0.001 ETH, `Balance` reported the full `0.0010000000`, and
  an immediate sell of that exact amount was rejected with
  `EGeneral:Invalid arguments:volume minimum not met` — the settled balance was
  briefly under the minimum. The same sell succeeded moments later. It does not
  affect the bot (its buys and sells are a day apart, and a $20 trade is ~8×
  the minimum), but any script that round-trips at the minimum must retry.
- **Kraken charges the buy fee in USD, not in the coin.** 0.001 ETH bought
  leaves exactly 0.001 ETH, so a sell of the full bought amount is correct.

- **A Kraken key that reads fine may still not trade.** `Balance` succeeding
  proves only the key and signing, not the order permission — those are
  separate grants. Check with `rehearse_sell.py --validate` rather than
  assuming, and re-check after rotating a key.

- **`vercel env pull` and `vercel blob create-store` rewrite `.env.local`** and
  mangle single-quoted values: `KEY='v'` becomes `KEY="'v'"`, so the value
  gains literal quotes. This silently corrupted the Kraken API keys once. Check
  them after any Vercel CLI env operation.
- **`vercel blob <cmd>` fails** with "VERCEL_OIDC_TOKEN and BLOB_STORE_ID must
  both be set" when `.env.local` holds an OIDC token. Pass
  `--rw-token "$BLOB_READ_WRITE_TOKEN"`.
- **`.cron_secret_local` holds `CRON_SECRET=<value>`**, not a bare value —
  strip the key before using it as a bearer token.
- **Backtest numbers move** as the data window advances. The same ETH config
  read +115.5% total on 2026-08-16 and +127.2% on 2026-08-22. Treat any single
  figure as indicative, not exact.

## Ideas not pursued

- **Switching the deployed rule to Supertrend 10/3 (2026-11-09).** The
  22-coin run picked it as the best of 23 rules, so it was tested on the years
  it was not picked on: `long_backtest.py` (results in `long_results.md`, run
  by the `long-backtest` workflow on its own branch), daily candles, 0.80%
  taker. ETH 2016-07 → 2026-11: Supertrend 10/3 +79,214% (91%/yr, max DD −59%)
  vs SMA 20/30 +45,157% (81%/yr, −84%), but almost all of the gap is
  2017–2019; it beat SMA 20/30 in only 6 of 11 calendar years, lost to it from
  2024-11-09 on (+47.5% vs +103.6%), and SMA 10/30 did as well as it on ETH
  (+75,833%, 90%/yr, −60%). Neighbouring parameters moved results more than
  the choice of rule did (Supertrend 10/4 +29,770%, 10/2 +34,523%). On BTC
  2015-09 → 2026-11 Supertrend 10/3 did worse than SMA 20/30 (39%/yr vs 43%/yr)
  and buy-and-hold beat every rule (67%/yr, +31,088%); on ETH every SMA and
  Supertrend rule beat buy-and-hold (65%/yr), mostly by sidestepping 2018 and
  2022. No consistent winner, so SMA 20/30 stays. The useful finding was the
  rule's real drawdown — see "Scaling the trade size".

- **The old PHP bot's MACD/EMA rule and the other patterns in its repo
  (2026-11-08).** `samuele-perrone/crypto-signals` ran 22 coins at $60 a
  trade on 4h candles (it "worked a bit, then started losing"). Ported exactly
  to `pattern_backtest.py` (results in `pattern_results.md`, run by the
  `pattern-backtest` workflow on its own branch), 22 coins, 2024-11-09 →
  2026-11-08, Coinbase hourly candles (TRX from Binance's data dumps, SPX and
  TRUMP from KuCoin), 0.40%/side unless stated. The live rule as it ran — on
  the still-forming candle, 3% trailing stop — lost 93% (82% at the 0.25% it
  paid in 2025), on all 22 coins and in every one of the 8 quarters,
  including May–Jul 2025 when buy-and-hold made +22%. It traded 178 times a
  coin a year and had no edge before fees (−5.8%). Closed candles only: −84%;
  no stop: −62%; daily candles: −39%. Every 4h pattern in the repo lost 34–99%
  (MACD, EMA50, the chatgpt.txt spec, volume profile, Heikin Ashi,
  Supertrend). Buy-and-hold lost 35%. Only slow daily trend filters with a
  handful of trades a year came out ahead of buy-and-hold: Supertrend 10/3
  +8.7% (neighbours 7/3 +5.1%, 14/3 +16.0%, 10/2 +0.8%, 10/4 −8.6%; +1.9% at
  0.80% taker), price above EMA50 −5.2%, SMA 20/30 −8.5% (−18.0% at its real
  0.80%). They "won" mostly by being out during the crash: every one lost in
  Year 2 (−13% to −32% against buy-and-hold's −51%). On ETH alone SMA 20/30
  beat Supertrend 10/3 (+124% vs +54%), so no change to the deployed rule; a
  longer-history ETH comparison would be the test before considering one. The
  PHP bot's bugs were fixed in its own repo (PR #1) without changing this
  verdict.

- **Day trading: buy in the morning, sell at the first profit or at the end
  of the day (2026-11-08).** Tested with `intraday_backtest.py` (results in
  `intraday_results.md`, run by the `intraday-backtest` workflow on its own
  branch): buy 08:00 UTC, sell at the first +0.5/1/2/3% or at 20:00 UTC, ten
  coins, 2024-11-08 → 2026-11-07, two years of Coinbase hourly candles since
  Kraken serves only 30 days of hourly data. Every variant on every coin lost
  89–99% after fees. Fees alone explain it: 729 round trips at 0.26%/side
  compound to −97.8% before any price move. Before fees the rule still had no
  edge: 08:00 → 20:00 holding lost on 9 of 10 coins (XRP the exception), and a
  +0.5% take-profit can never win after fees (0% win rate). The take-profit
  variants won 50–70% of days and still lost, because a capped win of ~0.5–1.9%
  pays for a full-day loss of ~1.5–2.9%. Same days, bot's SMA 20/30: +133% on
  ETH, positive on 5 of 10 coins, beat buy-and-hold on 8 of 10; over the last 12
  months it lost on all 10 (−3.5% ETH to −45.7% XRP) but less than buy-and-hold
  on every one. Adding coins to the bot remains rejected for the reasons in
  "Scaling the trade size".
- **30/20/60-day momentum, 4h candles, and trading BTC or SOL (2026-11-03).**
  Tested with `compare_strategies.py` (results in `backtest_results.md`, run by
  the `backtests` GitHub Actions workflow because Kraken is unreachable from
  cloud sessions). ETH daily: mom-30 +99.7% but max DD −44.7%, against SMA
  20/30's +108.6% at −17.6% — similar return for 2.5× the drawdown; mom-20
  +22.2%, mom-60 +68.4%. 4h candles over the ~100 days Kraken serves: SMA 20/30
  −0.8% on ETH and −4.5% on BTC, worse than buy-and-hold (+18.8% / +18.5%) —
  more trades mostly bought fees. BTC and SOL daily lost or roughly broke even
  under every rule (SMA 20/30 −15.7% / −2.7%), so adding pairs adds trades
  without adding edge. Kept: SMA 20/30, daily, ETH only.
- Deriving the position from the Kraken balance instead of storing it, making
  the exchange the single source of truth. Attractive because stored state can
  drift from reality — a crash between placing an order and saving leaves them
  disagreeing. Rejected for now: it needs API keys even in dry-run, cannot
  distinguish bot-bought coin from coin bought by hand, and entry price has to
  be recovered from trade history.
- Running the cron off Vercel on a machine with a real disk, which would make
  the SQLite file work with no sync layer at all.
