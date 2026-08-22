# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Kraken SMA-crossover trading bot that places **real market orders with real
money** when `LIVE=true`. Treat state handling, order placement, and the
dry-run gate as safety-critical. `README.md` documents the strategy and setup;
`OPERATIONS.md` documents what is deployed, the runbook, and past decisions —
read it before changing state storage or strategy rules.

## Commands

There is no test suite, no linter, and no build step. Verification is done by
running the backtester and by dry-run ticks against live Kraken data.

```sh
# Dry-run the local loop (no keys needed, no real orders)
python3 kraken_bot.py --pair ETH/USD --usd 100

# Backtest a config on real Kraken daily candles
python3 backtest.py --pair ETH/USD --fast 20 --slow 30

# Run one production-shaped tick locally
python3 -c "import sys; sys.path.insert(0,'api'); from tick import run_tick; print(run_tick())"

# Hit the deployed tick (fires a real Telegram message)
curl -H "Authorization: Bearer $(grep -o '[^=]*$' .cron_secret_local)" \
  https://cryptotrading-omega.vercel.app/api/tick

# Deploy: pushing to main builds automatically
git push && vercel ls --prod
vercel --prod --yes        # fallback if no build is triggered
```

Python 3.9 locally, 3.13 on Vercel. The only dependency is `requests` — keep it
that way unless there is a strong reason; the runtime has no package manifest
beyond `requirements.txt` and `pyproject.toml`.

## Architecture

Two independent entry points share one strategy core:

- **`kraken_bot.py`** — the original always-on local loop (`while True` +
  `--poll`). Also the module everything else imports: `KrakenClient`, `sma`,
  `crossover_signal`. Keeps its own state in `bot_state.json`.
- **`api/tick.py`** — the deployed path. A `BaseHTTPRequestHandler` invoked by
  Vercel Cron daily at 00:15 UTC (`vercel.json`). One GET = one tick. Uses
  `state_store.py`, not the JSON file.

So there are **two separate state stores** by design, and strategy logic lives
in `kraken_bot.py` — a rule change must be made there to affect both, and
`backtest.py` imports the same `sma` so backtests stay honest.

`state_store.py` keeps the SQLite position file durable across stateless Vercel
invocations by resting it in a private Vercel Blob store. Its three invariants
exist because breaking them causes wrong trades, not crashes:

1. **Reads are cache-busted** — Blob reads are CDN-cached and were observed
   serving a stale file after an overwrite.
2. **A failed pull raises**, never falls back to an empty database — "no
   position" is the dangerous wrong answer, since it makes the bot buy while
   already holding.
3. **Object name is namespaced by `VERCEL_ENV`**, so local ticks cannot
   clobber production's position.

The Vercel Blob REST contract used there is not publicly documented; it is
recorded in `OPERATIONS.md`.

## Conventions that matter

- **Signals use closed candles only.** `ohlc_closes()` drops the still-forming
  final candle. Do not "fix" this — it prevents intraday signal flicker.
- **Dry-run is the default everywhere.** `LIVE`/`--live` gates only the Kraken
  order call; every other code path runs identically so dry-run exercises the
  real logic, including state writes.
- **Notifications must never break trading.** `notify()` swallows exceptions by
  design.
- **Config reads treat empty env vars as unset** (`os.environ.get(X) or
  default`) — Vercel stores unset vars as empty strings.
- **Judge strategy changes on total return, not win rate**, and back them with
  `backtest.py`. A rejected take-profit raised the win rate from 62% to 79%
  while cutting returns by two-thirds; see `OPERATIONS.md`.
