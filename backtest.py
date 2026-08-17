#!/usr/bin/env python3
"""
Backtest the exact strategy from kraken_bot.py on historical Kraken OHLC data.

Same rules: buy on SMA fast/slow cross up, sell on cross down, or on
stop-loss / take-profit checked against candle lows/highs. Includes
Kraken's 0.26% taker fee on both sides.

Usage:
    python3 backtest.py --pair BTC/USD --candle 1440 --fast 10 --slow 30
"""

import argparse
from datetime import datetime, timezone

from kraken_bot import KrakenClient, sma

TAKER_FEE = 0.0026  # 0.26% per side


def fetch_candles(client, pair_name, interval):
    result = client.public("OHLC", {"pair": pair_name, "interval": interval})
    rows = next(v for k, v in result.items() if k != "last")
    # (time, open, high, low, close)
    return [(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]))
            for r in rows[:-1]]


def backtest(candles, fast, slow, stop_loss, take_profit, usd_per_trade):
    closes = [c[4] for c in candles]
    trades = []
    position = None  # (entry_price, volume)

    for i in range(slow + 1, len(candles)):
        t, o, high, low, close = candles[i]
        window, prev = closes[:i + 1], closes[:i]
        fast_now, slow_now = sma(window, fast), sma(window, slow)
        fast_prev, slow_prev = sma(prev, fast), sma(prev, slow)

        if position:
            entry, vol = position
            exit_price = None
            reason = None
            # Intra-candle stop/TP (checked against low/high; stop first = conservative)
            if stop_loss and low <= entry * (1 - stop_loss / 100):
                exit_price, reason = entry * (1 - stop_loss / 100), "stop"
            elif take_profit and high >= entry * (1 + take_profit / 100):
                exit_price, reason = entry * (1 + take_profit / 100), "tp"
            elif fast_prev >= slow_prev and fast_now < slow_now:
                exit_price, reason = close, "cross"
            if exit_price:
                gross = (exit_price - entry) * vol
                fees = (entry * vol + exit_price * vol) * TAKER_FEE
                trades.append({"pnl": gross - fees, "reason": reason,
                               "ret_pct": (exit_price / entry - 1) * 100 - TAKER_FEE * 200,
                               "time": t})
                position = None
        else:
            if fast_prev <= slow_prev and fast_now > slow_now:
                position = (close, usd_per_trade / close)

    # Mark-to-market any open position at the end
    open_pnl = 0.0
    if position:
        entry, vol = position
        open_pnl = (closes[-1] - entry) * vol - entry * vol * TAKER_FEE

    return trades, open_pnl


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", default="BTC/USD")
    p.add_argument("--candle", type=int, default=1440)
    p.add_argument("--fast", type=int, default=10)
    p.add_argument("--slow", type=int, default=30)
    p.add_argument("--stop-loss", type=float, default=0.0)
    p.add_argument("--take-profit", type=float, default=0.0)
    p.add_argument("--usd", type=float, default=100.0)
    args = p.parse_args()

    client = KrakenClient()
    pair = client.resolve_pair(args.pair)
    candles = fetch_candles(client, pair["name"], args.candle)
    start = datetime.fromtimestamp(candles[0][0], tz=timezone.utc)
    end = datetime.fromtimestamp(candles[-1][0], tz=timezone.utc)
    days = (candles[-1][0] - candles[0][0]) / 86400

    trades, open_pnl = backtest(candles, args.fast, args.slow,
                                args.stop_loss, args.take_profit, args.usd)

    wins = [t for t in trades if t["pnl"] > 0]
    total_pnl = sum(t["pnl"] for t in trades) + open_pnl
    total_ret = total_pnl / args.usd * 100
    years = days / 365.25
    buy_hold = (candles[-1][4] / candles[args.slow][4] - 1) * 100

    print(f"\n{args.pair} | {args.candle}m candles | SMA {args.fast}/{args.slow} "
          f"| SL {args.stop_loss}% TP {args.take_profit}% | fee {TAKER_FEE*100:.2f}%/side")
    print(f"Period: {start:%Y-%m-%d} -> {end:%Y-%m-%d} ({days:.0f} days)")
    print(f"Trades closed: {len(trades)}"
          + (f" (+1 still open, PnL ${open_pnl:+.2f})" if open_pnl else ""))
    if trades:
        print(f"Accuracy (win rate): {len(wins)}/{len(trades)} "
              f"= {len(wins)/len(trades)*100:.0f}%")
        print(f"Avg return per trade: "
              f"{sum(t['ret_pct'] for t in trades)/len(trades):+.2f}%")
        exits = {}
        for t in trades:
            exits[t["reason"]] = exits.get(t["reason"], 0) + 1
        print(f"Exit breakdown: {exits}")
    print(f"Total return on ${args.usd:.0f} stake: {total_ret:+.1f}% over {days:.0f} days")
    print(f"Annualized: {total_ret/years:+.1f}%/year (simple)")
    print(f"Buy & hold same period: {buy_hold:+.1f}%")


if __name__ == "__main__":
    main()
