#!/usr/bin/env python3
"""
Does a take-profit help the deployed SMA 20/30 bot? ETH since 2016, BTC
since 2015, daily candles, after fees.

The bot already has one: TAKE_PROFIT_PCT makes sell_reason() sell at the
00:15 UTC tick once the price is that far above the entry. It was rejected on
2026-08-22 on 719 days of data (a 5% take-profit cut ETH's annual return from
+64.6% to +19.1%). Two things have changed since: the test can now cover ten
years, and ENTER_ON_TREND (2026-11-03) means a flat bot buys back at the next
tick if SMA20 is still above SMA30, so a take-profit no longer ends the trade
for the rest of the trend. Variants:

  tick  TAKE_PROFIT_PCT as deployed: checked at the daily close; flat again,
        the bot re-buys at the next close if the trend is still up.
  rest  a limit sell resting on Kraken at entry +X%: fills inside the day the
        moment the price touches it, at the maker fee (half the taker fee);
        re-buys at the next close if the trend is still up.
  wait  take the profit at the tick, then sit out until a fresh cross up
        (the old behaviour, before ENTER_ON_TREND).

All of them run kraken_bot's own crossover_signal, buy_reason and
sell_reason, on pattern_backtest.simulate (hourly path, so a resting order
fills at the hour it is touched). Headline fee 0.80%/side, the entry-tier
taker fee the bot's market orders pay.

Data: Coinbase hourly candles, reachable only from GitHub Actions
(.github/workflows/takeprofit-backtest.yml).

Usage:
    python3 takeprofit_backtest.py
    python3 takeprofit_backtest.py --coins ETH
"""

import argparse
import time

import requests

import long_backtest as lb
import pattern_backtest as pb
from kraken_bot import buy_reason, crossover_signal, sell_reason
from pattern_backtest import DAY, HOUR, pct, utc

FAST, SLOW = 20, 30


class SmaTakeProfit(pb.Rule):
    """The deployed tick with a take-profit, in one of three styles."""

    def __init__(self, candles, tp_pct, style):
        assert style in ("tick", "rest", "wait")
        super().__init__("", candles, target=tp_pct / 100 if style == "rest" else None)
        self.target_fee_ratio = 0.5                 # maker 0.40% vs taker 0.80%
        self.closes = [c[4] for c in candles]
        self.tp, self.style = tp_pct, style
        self.entry, self.was_holding, self.blocked = None, False, False

    def decide(self, i, holding):
        if i + 1 < SLOW + 1:
            return None
        window = self.closes[:i + 1]
        price, signal = window[-1], crossover_signal(window, FAST, SLOW)
        self.was_holding = holding
        if holding:
            tp = 0 if self.style == "rest" else self.tp    # the resting order handles it
            reason = sell_reason({"entry": self.entry}, price, 0, tp, signal)
            if reason:
                if reason == "take-profit" and self.style == "wait":
                    self.blocked = True
                self.was_holding = False
                return "sell"
            return None
        if self.blocked:                    # wait style: only a fresh cross re-enters
            if signal != "buy":
                return None
            self.blocked = False
        if buy_reason(signal, window, FAST, SLOW, True):
            self.entry, self.was_holding = price, True
            return "buy"
        return None


def rules():
    out = [("none", "No take-profit (deployed)", lambda cs: pb.SmaBot("", cs))]
    for tp in (3, 5, 10, 20):
        out.append((f"tick{tp}", f"+{tp}% at the daily tick, re-buy if trend up",
                    lambda cs, tp=tp: SmaTakeProfit(cs, tp, "tick")))
    for tp in (5, 10):
        out.append((f"rest{tp}", f"+{tp}% resting limit order, re-buy if trend up",
                    lambda cs, tp=tp: SmaTakeProfit(cs, tp, "rest")))
    for tp in (5, 10):
        out.append((f"wait{tp}", f"+{tp}% at the tick, then wait for a fresh cross",
                    lambda cs, tp=tp: SmaTakeProfit(cs, tp, "wait")))
    return out


def report_coin(coin, r, specs=None):
    specs = specs or rules()
    labels = {k: label for k, label, _ in specs}
    labels["bh"] = "Buy and hold"
    keys = [k for k, _, _ in specs] + ["bh"]
    fee = lb.MAIN_FEE if lb.MAIN_FEE in r["bh"] else max(r["bh"])
    split = r["_split"]
    base = dict(lb.summary(r, "none", fee)["by_year"])
    L = []
    w = L.append
    w(f"## {coin}: {utc(r['_start'])} -> {utc(r['_end'])} "
      f"({(r['_end'] - r['_start']) / (365.25 * DAY):.1f} years), {fee * 100:.2f}%/side")
    w("")
    w(f"| Rule | Total | CAGR | Max drawdown | Trades/yr | Win rate | Avg win / avg loss | "
      f"Before {utc(split) if split else '-'} | After | Years beating no take-profit |")
    w("|" + "---|" * 10)
    for k in keys:
        s = lb.summary(r, k, fee)
        trades = r[k][fee]["trades"]
        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]
        avg_w = sum(wins) / len(wins) if wins else 0.0
        avg_l = sum(losses) / len(losses) if losses else 0.0
        beat = sum(1 for y, v in s["by_year"] if v > base[y]) if k != "none" else "-"
        beat_s = f"{beat}/{s['years']}" if k != "none" else "-"
        w(f"| {labels[k]} | {pct(s['total'])} | {pct(s['cagr'])} | {pct(s['max_dd'])} | "
          f"{s['trades_per_year']:.1f} | {pct(len(wins) / len(trades) if trades else 0, False)} | "
          f"{pct(avg_w)} / {pct(avg_l)} | {pct(s['before']) if s['before'] is not None else '-'} | "
          f"{pct(s['after']) if s['after'] is not None else '-'} | {beat_s} |")
    w("")
    years = [y for y, _ in lb.summary(r, "bh", fee)["by_year"]]
    w(f"### {coin} by calendar year ({years[0]} and {years[-1]} partial)")
    w("")
    w("| Rule | " + " | ".join(str(y) for y in years) + " |")
    w("|" + "---|" * (len(years) + 1))
    for k in ("none", "tick5", "rest5", "wait5", "tick20", "bh"):
        if k in r:
            w(f"| {labels[k]} | " + " | ".join(pct(v) for _, v in lb.summary(r, k, fee)["by_year"]) + " |")
    w("")
    w(f"### {coin} total return by fee")
    w("")
    fees = sorted(r["bh"])
    w("| Rule | " + " | ".join(f"{f * 100:.2f}%" for f in fees) + " |")
    w("|" + "---|" * (len(fees) + 1))
    for k in keys:
        w(f"| {labels[k]} | " + " | ".join(pct(r[k][f]["ret"]) for f in fees) + " |")
    w("")
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--coins", nargs="+", default=list(lb.FIRST))
    args = p.parse_args()
    now = int(time.time())
    end = now - now % HOUR - HOUR
    session = requests.Session()
    print(f"SMA {FAST}/{SLOW} daily with ENTER_ON_TREND, as deployed. Fee {lb.MAIN_FEE * 100:.2f}%/side "
          f"(taker); a resting take-profit exits at half that (maker). Split at "
          f"{utc(lb.SPLIT)} as in long_results.md.")
    print()
    for coin in args.coins:
        t0 = time.time()
        got = pb.fetch_coinbase(coin, int(lb.FIRST[coin].timestamp()), end, session) or {}
        hourly = sorted((t,) + v for t, v in got.items())
        if len(hourly) < 24 * 365:
            print(f"{coin}: not enough Coinbase history ({len(hourly)} hours).")
            continue
        r = lb.evaluate(hourly, specs=rules())
        print(f"<!-- {coin}: {len(hourly)} hours from {utc(hourly[0][0])}, "
              f"{time.time() - t0:.0f}s -->", flush=True)
        print(report_coin(coin, r))


if __name__ == "__main__":
    main()
