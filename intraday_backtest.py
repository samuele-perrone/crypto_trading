#!/usr/bin/env python3
"""
Backtest "buy in the morning, sell at the first profit or at the end of the
day" against the deployed daily SMA bot and plain buy-and-hold, per coin.

Kraken serves only its latest 720 candles - 30 days of hourly data, far too
short to judge a rule that trades every day - so this pulls two years of
hourly candles from Coinbase's public market-data API (no key; major USD
pairs track Kraken's prices within a fraction of a percent). Neither exchange
is reachable from cloud sessions: run it on the GitHub Actions runner
(.github/workflows/intraday-backtest.yml). A coin Coinbase cannot serve falls
back to Kraken's 30 days and is labelled so.

The day-trade rule, every UTC day:
  buy at the open of the BUY_HOUR candle (08:00 UTC = 08:00 London in winter)
  sell at the first hourly high >= entry * (1 + tp), filled at exactly that
  price; otherwise sell at the close of the last hour before SELL_HOUR (20:00)
Each trade pays the fee on both sides, the whole balance rides every trade,
and gains compound - the same sizing compare_strategies.py uses. "hold" is the
same rule with no take-profit: in at 08:00, out at 20:00.

Benchmarks over the same days, from the same candles (daily close = the
close of the 23:00 UTC hour): the deployed rule (SMA 20/30, ENTER_ON_TREND)
via compare_strategies.simulate(), so it runs the bot's real buy/sell code,
and buy-and-hold.

Usage:
    python3 intraday_backtest.py
    python3 intraday_backtest.py --coins BTC ETH --days 365 --tp 0.5 1 2
"""

import argparse
import time
from datetime import datetime, timezone

import requests

from compare_strategies import buy_hold_rule, simulate, sma_rule
from kraken_bot import TAKER_FEE, KrakenClient

HOUR, DAY = 3600, 86400
COINBASE = "https://api.exchange.coinbase.com"
DEFAULT_COINS = ["BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "LINK", "AVAX", "DOT"]
SMA_WARMUP_DAYS = 40   # extra history before the window so SMA30 is live on day 1


def utc(ts, fmt="%Y-%m-%d"):
    return datetime.fromtimestamp(ts, timezone.utc).strftime(fmt)


# ---------------------------------------------------------------------------
# Data: hourly candles as {open_time: (open, high, low, close)}
# ---------------------------------------------------------------------------

def fetch_coinbase_hourly(coin, start, end, session=None):
    """Hourly candles for <coin>-USD from start to end (unix seconds)."""
    s = session or requests.Session()
    out = {}
    t = start
    while t < end:
        t2 = min(t + 299 * HOUR, end)   # 300 candles a request, both ends inclusive
        for attempt in range(5):
            r = s.get(f"{COINBASE}/products/{coin}-USD/candles",
                      params={"granularity": HOUR,
                              "start": datetime.fromtimestamp(t, timezone.utc).isoformat(),
                              "end": datetime.fromtimestamp(t2, timezone.utc).isoformat()},
                      headers={"User-Agent": "crypto_trading-backtest"}, timeout=30)
            if r.status_code == 429:
                time.sleep(1 + attempt)
                continue
            r.raise_for_status()
            break
        else:
            r.raise_for_status()
        for ts, low, high, opn, close, _vol in r.json():
            out[int(ts)] = (float(opn), float(high), float(low), float(close))
        t = t2 + HOUR
        time.sleep(0.15)                 # public limit is ~10 requests/s
    return out


def fetch_kraken_hourly(coin):
    """Kraken's last 720 hourly candles (30 days): the fallback."""
    client = KrakenClient()
    pair = client.resolve_pair(f"{coin}/USD")
    result = client.public("OHLC", {"pair": pair["name"], "interval": 60})
    rows = next(v for k, v in result.items() if k != "last")[:-1]  # closed only
    return {int(r[0]): (float(r[1]), float(r[2]), float(r[3]), float(r[4])) for r in rows}


def daily_closes(candles):
    """[(day_start, close)] using the 23:00 UTC hour's close, complete days only."""
    days = sorted({ts - ts % DAY for ts in candles})
    return [(d, candles[d + 23 * HOUR][3]) for d in days if d + 23 * HOUR in candles]


# ---------------------------------------------------------------------------
# The day-trade rule
# ---------------------------------------------------------------------------

def day_trades(candles, tp, fee, buy_hour=8, sell_hour=20, first_day=None):
    """One trade per UTC day with every hour from buy_hour to sell_hour present.

    tp: take-profit as a fraction (0.01 = +1%), or None to hold to sell_hour.
    Returns [(day_start, multiplier, hit_tp)]; multiplier = the balance after
    the trade over the balance before, fees included.
    """
    days = sorted({ts - ts % DAY for ts in candles})
    out = []
    for d in days:
        if first_day is not None and d < first_day:
            continue
        hours = [candles.get(d + h * HOUR) for h in range(buy_hour, sell_hour)]
        if not hours or any(c is None for c in hours):
            continue                              # gap in the data: no trade
        entry = hours[0][0]
        exit_price, hit = hours[-1][3], False
        if tp is not None:
            target = entry * (1 + tp)
            for _o, high, _l, _c in hours:
                if high >= target:
                    exit_price, hit = target, True
                    break
        out.append((d, exit_price / entry * (1 - fee) ** 2, hit))
    return out


def stats(trades, since=None):
    """Summary of [(day, multiplier, hit)]: compounded return, win rate, etc."""
    if since is not None:
        trades = [t for t in trades if t[0] >= since]
    if not trades:
        return None
    equity, peak, max_dd = 1.0, 1.0, 0.0
    wins, losses = [], []
    for _d, m, _h in trades:
        equity *= m
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1)
        (wins if m > 1 else losses).append(m - 1)
    return {
        "return_pct": (equity - 1) * 100,
        "trades": len(trades),
        "win_rate": len(wins) / len(trades) * 100,
        "avg_win": sum(wins) / len(wins) * 100 if wins else 0.0,
        "avg_loss": sum(losses) / len(losses) * 100 if losses else 0.0,
        "worst": min(m for _d, m, _h in trades) * 100 - 100,
        "tp_hit": sum(1 for t in trades if t[2]) / len(trades) * 100,
        "max_dd": max_dd * 100,
    }


def daily_benchmark(closes_by_day, rule, first_day, last_year):
    """Run a compare_strategies rule on daily closes; whole window and last year."""
    closes = [c for _d, c in closes_by_day]
    days = [d for d, _c in closes_by_day]
    start = next(i for i, d in enumerate(days) if d >= first_day)
    start_y = next(i for i, d in enumerate(days) if d >= last_year)
    ret, buys, dd = simulate(closes, rule, start)
    ret_y, _b, _dd = simulate(closes, rule, start_y)
    return ret, ret_y, buys, dd


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--coins", nargs="+", default=DEFAULT_COINS)
    p.add_argument("--days", type=int, default=730)
    p.add_argument("--tp", type=float, nargs="+", default=[0.5, 1, 2, 3],
                   help="Take-profit levels in percent")
    p.add_argument("--buy-hour", type=int, default=8)
    p.add_argument("--sell-hour", type=int, default=20)
    p.add_argument("--fee", type=float, default=TAKER_FEE * 100,
                   help="Fee per side in percent (default: the bot's taker fee)")
    args = p.parse_args()
    fee = args.fee / 100

    now = int(time.time())
    end = now - now % DAY                       # midnight UTC today: complete days only
    first_day = end - args.days * DAY
    last_year = end - 365 * DAY
    variants = [(f"take +{t:g}%", t / 100) for t in args.tp] + [("hold to close", None)]

    print(f"\nWindow {utc(first_day)} -> {utc(end - DAY)} ({args.days} days). "
          f"Day trade: buy {args.buy_hour:02d}:00 UTC, sell at the first +X% or at "
          f"{args.sell_hour:02d}:00 UTC. Fee {args.fee:.2f}%/side, full balance compounded. "
          f"'No fees' shows the rule's edge before costs.\n")

    summary = []
    session = requests.Session()
    for coin in args.coins:
        source = "Coinbase"
        try:
            candles = fetch_coinbase_hourly(coin, first_day - SMA_WARMUP_DAYS * DAY,
                                            end - HOUR, session)
            if not candles:
                raise RuntimeError("no candles")
        except Exception as e:  # noqa: BLE001 - report and fall back
            source = f"Kraken, last 30 days only (Coinbase failed: {e})"
            try:
                candles = fetch_kraken_hourly(coin)
            except Exception as e2:  # noqa: BLE001
                print(f"\n## {coin}/USD\n\nNo data: {e2}\n")
                continue
        candles = {t: c for t, c in candles.items() if t < end}
        closes_by_day = daily_closes(candles)
        window_start = max(first_day, min(candles) - min(candles) % DAY + DAY)

        print(f"\n## {coin}/USD\n\nData: {source}; {len(candles):,} hourly candles.\n")
        print("| Rule | Return, full window | Return, no fees | Return, last 12 months "
              "| Trades | Win rate | Avg win / avg loss | Worst day | Hit target | Max drawdown |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        best = None
        for name, tp in variants:
            tr = day_trades(candles, tp, fee, args.buy_hour, args.sell_hour, window_start)
            s = stats(tr)
            if s is None:
                continue
            gross = stats(day_trades(candles, tp, 0.0, args.buy_hour, args.sell_hour,
                                     window_start))
            y = stats(tr, last_year)
            print(f"| Day trade, {name} | {s['return_pct']:+.1f}% | {gross['return_pct']:+.1f}% "
                  f"| {y['return_pct']:+.1f}% | {s['trades']} | {s['win_rate']:.0f}% "
                  f"| {s['avg_win']:+.2f}% / {s['avg_loss']:+.2f}% | {s['worst']:+.1f}% "
                  f"| {s['tp_hit']:.0f}% | {s['max_dd']:.1f}% |")
            if best is None or s["return_pct"] > best[1]:
                best = (name, s["return_pct"], y["return_pct"])

        sma = bh = None
        try:
            sma = daily_benchmark(closes_by_day, sma_rule(20, 30, True), window_start, last_year)
            bh = daily_benchmark(closes_by_day, buy_hold_rule, window_start, last_year)
            print(f"| Bot's rule, SMA 20/30 daily | {sma[0]:+.1f}% | | {sma[1]:+.1f}% | {sma[2]} buys "
                  f"| | | | | {sma[3]:.1f}% |")
            print(f"| Buy and hold | {bh[0]:+.1f}% | | {bh[1]:+.1f}% | 1 | | | | | {bh[3]:.1f}% |")
        except StopIteration:
            print("\nNot enough daily history for the SMA and buy-and-hold rows.")
        if best:
            summary.append((coin, best, sma, bh))

    if summary:
        print("\n## Summary, full window, after fees\n")
        print("| Coin | Best day-trade variant | Its return | Bot's SMA 20/30 | Buy and hold |")
        print("|---|---|---|---|---|")
        for coin, best, sma, bh in summary:
            print(f"| {coin} | {best[0]} | {best[1]:+.1f}% | "
                  f"{f'{sma[0]:+.1f}%' if sma else 'n/a'} | {f'{bh[0]:+.1f}%' if bh else 'n/a'} |")


if __name__ == "__main__":
    main()
