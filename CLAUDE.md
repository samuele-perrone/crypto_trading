# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Kraken SMA-crossover trading bot that places **real market orders with real
money** when `LIVE=true`. Treat state handling, order placement, and the
dry-run gate as safety-critical. `README.md` documents the strategy and setup;
`OPERATIONS.md` documents what is deployed, the runbook, and past decisions —
read it before changing state storage or strategy rules.

## Keep the docs current — required, not optional

These files are the memory of this project. Update them **in the same commit**
as the change, never as a follow-up:

- **Changed what is deployed** (env vars, schedule, pair/SMA config, going
  live, a new store or service) → update `OPERATIONS.md` "Current status" and
  its "Last updated" date.
- **Changed how something works** (state storage, tick flow, deploy path) →
  update the matching `OPERATIONS.md` section and, if it changes an invariant
  or an entry point, this file.
- **Made a judgement call** (adopted or rejected a strategy rule, chose a
  provider, ruled an approach out) → add it to `OPERATIONS.md` "Decisions" or
  "Ideas not pursued", with the evidence and the date.
- **Hit a trap that cost time** (CLI mangling a file, a misleading command, a
  silent cache) → add it to `OPERATIONS.md` "Gotchas" so it is paid for once.
- **Changed setup or usage** → update `README.md`.

A change that leaves these stale is incomplete. If a doc claim turns out to be
wrong, correct it rather than working around it.

## Commands

No linter, no build step. Tests are stdlib `unittest` — no pytest, no dev
dependencies.

```sh
# Strategy rules: deterministic, no network, run after touching kraken_bot.py
python3 -m unittest test_strategy
python3 -m unittest test_strategy.TestSellReason.test_stop_loss_beats_take_profit
# Everything (rules, state store, look-ahead + /api/status routing, day-trade
# backtest, PHP-bot pattern backtest, long-history and take-profit backtests)
python3 -m unittest test_strategy test_state_store test_status test_intraday test_pattern test_long test_takeprofit

# Rehearse a full sell without waiting for the market (isolated Blob namespace)
python3 rehearse_sell.py
python3 rehearse_sell.py --validate   # + round-trip the order through Kraken

# Dry-run the local loop (no keys needed, no real orders)
python3 kraken_bot.py --pair ETH/USD --usd 100

# Backtest a config on real Kraken daily candles
python3 backtest.py --pair ETH/USD --fast 20 --slow 30
# Day-trading rule vs the bot across coins (needs network: runs on GitHub
# Actions via the intraday-backtest branch, results in intraday_results.md)
python3 intraday_backtest.py --coins BTC ETH SOL
# The old PHP bot's rules (samuele-perrone/crypto-signals) and its repo's
# other patterns, 22 coins, 2 years (network: GitHub Actions via the
# pattern-backtest branch, results in pattern_results.md)
python3 pattern_backtest.py --coins BTC ETH --days 365
# Supertrend vs the deployed SMA 20/30 on ETH since 2016 / BTC since 2015
# (network: GitHub Actions via the long-backtest branch, long_results.md)
python3 long_backtest.py --coins ETH
# The deployed rule with and without a take-profit, same history
# (network: GitHub Actions via the takeprofit-backtest branch)
python3 takeprofit_backtest.py --coins ETH

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

A third, **`api/status.py`**, is read-only: `GET /api/status` for the
dashboard (price, SMAs, next-trade trigger and average-needed path, open/flat, history). Because the
project deploys with the Python framework preset, the pyproject entrypoint
`api.tick:handler` may receive every path, so `tick.handler.do_GET` dispatches
exactly `/api/status` to `status.status_response()` before the `CRON_SECRET`
check; every other path is unchanged. See `OPERATIONS.md`.

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
  real logic, including state writes. `VALIDATE=true` is the middle mode —
  a real `AddOrder` with `validate=true`, nothing placed. It is the only way to
  test credentials, and dry-run provably cannot: a key that reads balances fine
  may still lack order permission.
- **Sell rules live in `sell_reason()`, buy rules in `buy_reason()`**, both in
  `kraken_bot.py` and shared by the local loop, the deployed tick and
  `backtest.py`. Change them there, not inline in any caller, or the paths
  drift. `buy_reason()` buys into an existing uptrend when flat
  (`ENTER_ON_TREND`, default on) — `crossover_signal()` alone is an edge, not
  a state, and would leave a flat bot idle mid-trend.
- **Position sizing goes through `trade_stake()`**, never `usd / price`
  directly. A stake equal to the balance always fails — the taker fee pushes
  the cost above it — so every stake is capped by `affordable_usd()`.
  `TRADE_PCT` sizes from the live balance instead of a fixed amount.
- **Notifications must never break trading.** `notify()` swallows exceptions by
  design. The same goes for the daily report's look-ahead (`next_trade()`,
  `next_trade_line()`, `heads_up_text()`): it runs only after the trade
  decision, inside `try`, and failures go to `next_trade_error`.
- **`/api/status` stays read-only and secret-free.** Keyless `KrakenClient()`,
  `load_position()` only — never `save_position()`, never a private call. It
  is public, so it must not expose balances, volumes or txids.
  `test_status` guards both.
- **Config reads treat empty env vars as unset** (`os.environ.get(X) or
  default`) — Vercel stores unset vars as empty strings.
- **Judge strategy changes on total return, not win rate**, and back them with
  `backtest.py`. A rejected take-profit raised the win rate from 62% to 79%
  while cutting returns by two-thirds; see `OPERATIONS.md`.
