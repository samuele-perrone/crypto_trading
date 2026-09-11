# Operations & project log

Working notes for running this bot and picking the work back up later.
`README.md` covers the strategy and first-time setup; this file covers what is
deployed, how it behaves in production, why things are the way they are, and
the traps that already cost time once.

Last updated: 2026-09-11.

## Current status

- **Live URL:** `https://cryptotrading-omega.vercel.app/api/tick`
- **Mode: LIVE since 2026-09-11.** `LIVE=true` in Vercel production — real
  market orders. The simulated position was deleted in the same change, so the
  bot started flat and enters only on a fresh cross up.
- **Schedule:** Vercel Cron, daily at 00:15 UTC (`vercel.json`), just after the
  daily candle closes — the only moment an SMA signal can change.
- **Config:** ETH/USD, SMA 20/30 on daily candles, **$20 per trade**, no
  stop-loss, no take-profit. The tick response echoes the effective
  `usd_per_trade` and `sma`, since `vercel env ls` cannot show values.
- **State:** private Vercel Blob store `crypto-trading-state`, object
  `production/bot_state.db`.
- **Kraken account:** $65.81 USD, no ETH. API key verified end to end.
- **Open simulated position** since 2026-08-21 00:15 UTC: entry $2,332.51,
  volume 0.04287227 (~$100 at the old trade size), around +5.6% in mid
  September. This was the first signal the deployed bot produced, and it
  confirms Blob persistence works in real operation — written by a cron tick,
  intact across weeks of cold invocations.

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

## How a tick works

`api/tick.py` is the whole production path. One HTTP GET = one strategy tick.

1. Reject the request unless `Authorization: Bearer $CRON_SECRET` matches.
2. Resolve the pair on Kraken, fetch daily closes and the current price.
3. Compute the SMA crossover signal on **closed candles only** — the still
   forming candle is dropped, so signals never flicker intraday.
4. Load the open position from state.
5. Sell if stop-loss, take-profit, or an SMA cross down fires; buy on a cross
   up when flat. In dry-run everything runs except the Kraken order call.
6. Persist the new position, notify Telegram, return the tick as JSON (also
   printed to the Vercel function log).

If nothing traded, it still sends a daily 📊 heartbeat so silence means
"broken", not "no signal". Disable with `DAILY_REPORT=false`.

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

**1. Deterministic rules** — `python3 -m unittest test_strategy test_state_store`

No network, no keys, runs in a second. `test_strategy` covers when to buy, when
to sell, and how much: crossover edges (the signal must fire once, not every
day of a trend), stop-loss and take-profit thresholds and their precedence, `0`
meaning "disabled" rather than "sell at breakeven", and rounding that never
overspends the stake. `test_state_store` stubs HTTP and pins the one-directional
safety property — failing loudly is fine, reporting "no position" when one may
be held is not. Run both after touching `kraken_bot.py` or `state_store.py`.

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

The same logic argues against a tight stop-loss — the worst trade was only
−5.0%. `STOP_LOSS_PCT` is 0 and untested as of this date.

## Gotchas

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

- Deriving the position from the Kraken balance instead of storing it, making
  the exchange the single source of truth. Attractive because stored state can
  drift from reality — a crash between placing an order and saving leaves them
  disagreeing. Rejected for now: it needs API keys even in dry-run, cannot
  distinguish bot-bought coin from coin bought by hand, and entry price has to
  be recovered from trade history.
- Running the cron off Vercel on a machine with a real disk, which would make
  the SQLite file work with no sync layer at all.
