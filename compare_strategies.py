#!/usr/bin/env python3
"""
Compare entry/exit rules on real Kraken candles, sized like the deployed bot.

Unlike backtest.py (fixed stake, one config), this compounds the whole
balance into every buy (TRADE_PCT=100), pays the taker fee on both sides,
and runs several strategies side by side:

  sma-cross     SMA fast/slow, buy only on a fresh cross up (pre-2026-11-03)
  sma-trend     same, but a flat bot also buys while fast > slow (ENTER_ON_TREND)
  mom-N         hold while close > close N candles ago, else flat
  buy-hold      buy on the first candle, never sell

Buy rules for the SMA strategies come from kraken_bot.buy_reason() /
crossover_signal(), so this tests the code that actually trades.

Because entry rules only differ when the bot is flat mid-trend, a single
full-period run hides most of the difference. --starts also launches the
bot on many start dates (every --step candles) and reports the average and
worst outcome to the end of the data - "what if I had gone live on day X".

Usage:
    python3 compare_strategies.py --pairs ETH/USD BTC/USD --candle 1440
"""

import argparse
from datetime import datetime, timezone

from kraken_bot import KrakenClient, TAKER_FEE, buy_reason, crossover_signal


def fetch(client, pair_arg, interval):
    pair = client.resolve_pair(pair_arg)
    result = client.public("OHLC", {"pair": pair["name"], "interval": interval})
    rows = next(v for k, v in result.items() if k != "last")[:-1]  # closed only
    return [(int(r[0]), float(r[4])) for r in rows]


def sma_rule(fast, slow, enter_on_trend):
    def rule(window, holding):
        signal = crossover_signal(window, fast, slow)
        if holding:
            return "sell" if signal == "sell" else None
        return "buy" if buy_reason(signal, window, fast, slow, enter_on_trend) else None
    rule.warmup = slow + 1
    return rule


def momentum_rule(n):
    def rule(window, holding):
        up = window[-1] > window[-1 - n]
        if holding and not up:
            return "sell"
        if not holding and up:
            return "buy"
        return None
    rule.warmup = n + 1
    return rule


def buy_hold_rule(window, holding):
    return None if holding else "buy"
buy_hold_rule.warmup = 1


def simulate(closes, rule, start):
    """Run from candle `start` to the end. Returns (return %, trades, max DD %)."""
    cash, coins, trades = 1.0, 0.0, 0
    peak, max_dd = 1.0, 0.0
    for i in range(max(start, rule.warmup), len(closes)):
        price = closes[i]
        action = rule(closes[:i + 1], coins > 0)
        if action == "buy":
            coins, cash = cash * (1 - TAKER_FEE) / price, 0.0
            trades += 1
        elif action == "sell":
            cash, coins = coins * price * (1 - TAKER_FEE), 0.0
        equity = cash + coins * price
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1)
    final = cash + coins * closes[-1] * (1 - TAKER_FEE if coins else 1)
    return (final - 1) * 100, trades, max_dd * 100


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pairs", nargs="+", default=["ETH/USD", "BTC/USD", "SOL/USD"])
    p.add_argument("--candle", type=int, default=1440)
    p.add_argument("--fast", type=int, default=20)
    p.add_argument("--slow", type=int, default=30)
    p.add_argument("--momentum", type=int, nargs="+", default=[20, 30, 60])
    p.add_argument("--step", type=int, default=15,
                   help="Candles between simulated go-live dates")
    p.add_argument("--min-run", type=int, default=90,
                   help="Shortest go-live -> end span to include, in candles")
    args = p.parse_args()

    strategies = {
        f"sma-cross {args.fast}/{args.slow}": sma_rule(args.fast, args.slow, False),
        f"sma-trend {args.fast}/{args.slow}": sma_rule(args.fast, args.slow, True),
        **{f"mom-{n}": momentum_rule(n) for n in args.momentum},
        "buy-hold": buy_hold_rule,
    }
    warm = max(s.warmup for s in strategies.values())

    client = KrakenClient()
    for pair_arg in args.pairs:
        candles = fetch(client, pair_arg, args.candle)
        closes = [c for _, c in candles]
        fmt = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
        days = (candles[-1][0] - candles[warm][0]) / 86400
        print(f"\n## {pair_arg} | {args.candle}m candles | {fmt(candles[warm][0])} -> "
              f"{fmt(candles[-1][0])} ({days:.0f} days) | fee {TAKER_FEE*100:.2f}%/side, "
              f"full balance compounded\n")

        starts = list(range(warm, len(closes) - args.min_run, args.step))
        print("| Strategy | Full period | Buys | Max DD | Avg over go-live dates "
              "| Worst go-live | Go-lives with 0 trades |")
        print("|---|---|---|---|---|---|---|")
        for name, rule in strategies.items():
            ret, trades, dd = simulate(closes, rule, warm)
            runs = [simulate(closes, rule, s) for s in starts]
            avg = sum(r[0] for r in runs) / len(runs)
            worst = min(r[0] for r in runs)
            idle = sum(1 for r in runs if r[1] == 0)
            print(f"| {name} | {ret:+.1f}% | {trades} | {dd:.1f}% | {avg:+.1f}% "
                  f"| {worst:+.1f}% | {idle}/{len(runs)} |")

        # Where the bot stands today
        fast_now = sum(closes[-args.fast:]) / args.fast
        slow_now = sum(closes[-args.slow:]) / args.slow
        print(f"\nLast close {closes[-1]:,.2f} | SMA{args.fast} {fast_now:,.2f} vs "
              f"SMA{args.slow} {slow_now:,.2f} -> "
              f"{'uptrend (sma-trend would be IN)' if fast_now > slow_now else 'downtrend (both SMA rules flat)'}")
        for n in args.momentum:
            print(f"mom-{n}: close vs {n} candles ago {closes[-1 - n]:,.2f} -> "
                  f"{'IN' if closes[-1] > closes[-1 - n] else 'OUT'}")


if __name__ == "__main__":
    main()
