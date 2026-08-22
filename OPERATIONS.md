# Operations & project log

Working notes for running this bot and picking the work back up later.
`README.md` covers the strategy and first-time setup; this file covers what is
deployed, how it behaves in production, why things are the way they are, and
the traps that already cost time once.

Last updated: 2026-08-22.

## Current status

- **Live URL:** `https://cryptotrading-omega.vercel.app/api/tick`
- **Mode:** dry-run. `LIVE` is unset in Vercel, so no real orders are placed.
- **Schedule:** Vercel Cron, daily at 00:15 UTC (`vercel.json`), just after the
  daily candle closes — the only moment an SMA signal can change.
- **Config:** ETH/USD, SMA 20/30 on daily candles, $100 per trade, no
  stop-loss, no take-profit.
- **State:** private Vercel Blob store `crypto-trading-state`, object
  `production/bot_state.db`. Currently empty (no open position).
- **Blocking going live:** the Kraken account holds ~$0.01 against a $100
  trade size. Fund it, verify the balance, then set `LIVE=true`.

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

Three properties worth preserving if you touch that file:

- **Reads are cache-busted.** Blob reads go through a CDN. A read seconds after
  an overwrite was observed returning the *previous* file (`x-vercel-cache:
  HIT`). A stale position is a wrong trade, so every GET carries a unique query
  param. Do not remove it.
- **A failed pull raises.** It deliberately does not fall back to an empty
  database, because "no position" is exactly the dangerous wrong answer — it
  makes the bot buy again while already holding. A failed tick returns 500 and
  fires a Telegram alert instead.
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
derivation the official SDK uses. A missing object returns 404, which the code
treats as "no state yet". Without the bearer token the request returns 403,
which is the point of a private store.

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
