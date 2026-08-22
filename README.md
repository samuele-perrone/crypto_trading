# Kraken Trading Bot

Automatically buys and sells any cryptocurrency against your USD balance on
Kraken, using an SMA-crossover strategy with stop-loss and take-profit.

## Strategy

- **Buy** when the fast SMA crosses **above** the slow SMA (uptrend starting)
- **Sell** when the fast SMA crosses **below** the slow SMA (uptrend ending)
- Optional **stop-loss** / **take-profit** (off by default — backtesting showed
  tight stops on daily candles get shaken out by normal crypto volatility)

Defaults are SMA 10/30 on **daily** candles, chosen from a 2-year backtest
(`backtest.py`) where this configuration beat buy-and-hold on BTC and ETH
after fees. Past performance is no guarantee — rerun the backtest yourself:

```sh
python3 backtest.py --pair ETH/USD
```

Signals are computed on closed candles only; open positions persist in
`bot_state.json` so the bot survives restarts.

## Setup

Requires Python 3.9+ and `requests` (already installed on this machine).

For live trading, create an API key at kraken.com → Settings → API with
**Query Funds** and **Create & Modify Orders** permissions (nothing else —
no withdrawal permission), then:

```sh
export KRAKEN_API_KEY="your-key"
export KRAKEN_API_SECRET="your-secret"
```

## Usage

Always start with a dry run (default — no keys needed, no real orders):

```sh
python3 kraken_bot.py --pair BTC/USD
python3 kraken_bot.py --pair ETH/USD --usd 100 --candle 15
python3 kraken_bot.py --pair SOL/USD --fast 20 --slow 50 --stop-loss 2 --take-profit 4
```

When you're happy with its behavior, add `--live` (it asks for confirmation):

```sh
python3 kraken_bot.py --pair BTC/USD --usd 50 --live
```

### Options

| Flag | Default | Meaning |
|---|---|---|
| `--pair` | BTC/USD | Any Kraken pair vs USD (BTC, ETH, SOL, DOGE, …) |
| `--usd` | 50 | USD spent per buy |
| `--fast` / `--slow` | 10 / 30 | SMA periods (in candles) |
| `--candle` | 1440 | Candle size in minutes (1, 5, 15, 30, 60, 240, 1440) |
| `--stop-loss` | 0 (off) | Sell if down this % from entry (0 disables) |
| `--take-profit` | 0 (off) | Sell if up this % from entry (0 disables) |
| `--poll` | 300 | Seconds between market checks |
| `--live` | off | Place real orders |

## Backtest results (deployed config)

ETH/USD, SMA 20/30 on daily candles, no stop-loss/take-profit, 0.26% taker
fee per side. Period: 2024-08-27 → 2026-08-16 (719 days), real Kraken data.

| Metric | Value |
|---|---|
| Trades closed | 14 |
| Win rate | 57% (8/14) |
| Avg win / avg loss | +16.6% / −2.8% |
| Best / worst trade | +45.0% / −5.0% |
| Profit factor | 7.81 |
| Max drawdown | −4.7% |
| Total return | +115.5% (≈ +59%/yr) |
| Buy & hold ETH same period | −28.8% |
| Positive months | 58% (avg +9.6%/mo, worst −5.0%) |

Compared against alternatives on the same data (EMA cross, MACD, Donchian
breakout, 30/60-day momentum): only 30-day momentum was competitive
(+45%/yr on ETH); MACD and Donchian lost money. Every strategy profited on
ETH and lost on SOL — the asset choice matters more than the indicator.

**Read this before extrapolating:**

- One 2-year window with strong trends in both directions — ideal conditions
  for a crossover system. Expect meaningfully less going forward.
- This config was the best of a 45-configuration sweep, so part of the result
  is selection bias. The robust finding is that *most* slow trend-following
  configs on ETH were profitable, not the peak number.
- Small implementation changes (e.g. warm-up window) shifted the annualized
  result by ~16 points on the same data. Treat all figures as ±half.
- 14 trades in 2 years: silence for weeks is normal operation.

## Hosted on Vercel (always running)

Instead of the local loop, `api/tick.py` runs the same strategy as a Vercel
function triggered by Vercel Cron daily at 00:15 UTC — right after the daily
candle closes, which is the only moment signals can change. Position state
lives in a SQLite file (`state_store.py`); trade alerts go to Telegram.

Vercel functions can only write to `/tmp`, which is wiped between invocations,
so the SQLite file cannot simply sit on disk there. Instead it rests in a
private **Vercel Blob** store between ticks: pulled before every read, pushed
after every write. It is still an ordinary SQLite file — Blob is just where it
lives when no function is running.

- Reads use a cache-busting query param. Blob reads are CDN-cached and would
  otherwise serve a stale file, and a stale position means a wrong trade.
- A failed pull raises instead of returning "no position", so the tick fails
  loudly (500 + Telegram alert) rather than trading on unknown state.
- The object name defaults to `<VERCEL_ENV>/bot_state.db`, so a local test tick
  writes to `development/…` and cannot clobber production's position.

### One-time setup

1. **State** — create the Blob store once; it wires up `BLOB_READ_WRITE_TOKEN`
   automatically:
   ```sh
   vercel blob create-store crypto-trading-state --access private
   ```
   The SQLite file and its `bot_state` table are created on first run. Without
   a Blob token the bot falls back to a plain local file (`BOT_DB_PATH`), which
   is correct off Vercel but ephemeral on it — the tick response carries a
   `state_warning` when that applies.
2. **Telegram** (optional) — message @BotFather → `/newbot` → copy the token.
   Send your new bot any message, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `chat.id`.
3. **Env vars** — set in Vercel (Project → Settings → Environment Variables
   or `vercel env add NAME production`):

   | Name | Value |
   |---|---|
   | `PAIR` | `ETH/USD` |
   | `SMA_FAST` / `SMA_SLOW` | `20` / `30` |
   | `USD_PER_TRADE` | e.g. `50` |
   | `BLOB_READ_WRITE_TOKEN` | set automatically by `vercel blob create-store` |
   | `BOT_BLOB_PATHNAME` | optional; default `<VERCEL_ENV>/bot_state.db` |
   | `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | from step 2 |
   | `CRON_SECRET` | any random string (protects the endpoint) |
   | `KRAKEN_API_KEY` / `KRAKEN_API_SECRET` | only when going live |
   | `LIVE` | unset = dry-run; `true` = real orders |

4. Deploy: pushing to `main` builds automatically; `vercel --prod --yes` is the
   fallback.

Test a tick manually:
```sh
curl -H "Authorization: Bearer $CRON_SECRET" https://<your-app>.vercel.app/api/tick
```

See **[OPERATIONS.md](OPERATIONS.md)** for what is currently deployed, the
runbook (testing a tick, inspecting or clearing state, going live), the design
decisions behind the state storage, and the CLI gotchas worth knowing before
touching any of it.

## Warnings

- SMA crossover is a simple trend-following strategy. It loses money in
  choppy/sideways markets. Backtest and dry-run before going live.
- Market orders pay the spread plus Kraken's taker fee (~0.26%). Frequent
  trading on small moves can lose money to fees alone.
- Only trade money you can afford to lose. This is not financial advice.
