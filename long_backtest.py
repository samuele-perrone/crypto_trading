#!/usr/bin/env python3
"""
Supertrend against the deployed SMA 20/30 on ETH's whole Coinbase history
(since May 2016), with BTC (since 2015) as a cross-check. Daily candles,
after fees.

pattern_backtest.py found Supertrend 10/3 daily the best of 23 rules across
22 coins over 2024-11-09 -> 2026-11-08, yet on ETH alone SMA 20/30 won
(+124% vs +54%). Picking the best of 23 rules on one window is how backtests
overfit, so this asks the question on years neither result was found on: the
summary splits every rule at SPLIT (the start of that window), and the
by-year table shows whether either rule wins consistently or only in a few
big years.

Rules (closed daily candles, decisions at the 00:00 UTC close, the deployed
bot's timing):
  SMA 20/30 = the deployed rule, through compare_strategies.sma_rule
  (kraken_bot.buy_reason with ENTER_ON_TREND); SMA 10/30 and 20/50 as its
  neighbours. Supertrend 10/3 and its neighbours 7/3, 14/3, 10/2, 10/4.
  Price above EMA50. Buy and hold.
Fees: 0.80%/side is the headline because the deployed bot sends market
orders (Kraken Pro's entry-tier taker fee since July 2026); 0.40% (maker),
0.26% (the old taker fee) and 0 are shown too. No stops, so the simulation
needs no intrahour fills: pattern_backtest.simulate on hourly candles, the
same engine and accounting as the 22-coin run.

Data: Coinbase hourly candles (no key). Not reachable from cloud sessions:
run on GitHub Actions (.github/workflows/long-backtest.yml).

Usage:
    python3 long_backtest.py
    python3 long_backtest.py --coins ETH
"""

import argparse
import time
from datetime import datetime, timezone

import requests

import pattern_backtest as pb
from compare_strategies import sma_rule
from pattern_backtest import DAY, HOUR, pct, utc

SPLIT = int(datetime(2024, 11, 9, tzinfo=timezone.utc).timestamp())
FIRST = {"ETH": datetime(2016, 5, 1, tzinfo=timezone.utc),
         "BTC": datetime(2015, 1, 1, tzinfo=timezone.utc)}
FEES = (0.008, 0.004, 0.0026, 0.0)
MAIN_FEE = 0.008


class Sma(pb.SmaBot):
    def __init__(self, candles, fast, slow):
        pb.Rule.__init__(self, "", candles)
        self.closes = [c[4] for c in candles]
        self.rule = sma_rule(fast, slow, True)


def rules():
    return [
        ("sma_20_30", "SMA 20/30 (deployed)", lambda cs: pb.SmaBot("", cs)),
        ("sma_10_30", "SMA 10/30", lambda cs: Sma(cs, 10, 30)),
        ("sma_20_50", "SMA 20/50", lambda cs: Sma(cs, 20, 50)),
        ("st_10_3", "Supertrend 10/3", lambda cs: pb.Supertrend("", cs, 10, 3.0)),
        ("st_7_3", "Supertrend 7/3", lambda cs: pb.Supertrend("", cs, 7, 3.0)),
        ("st_14_3", "Supertrend 14/3", lambda cs: pb.Supertrend("", cs, 14, 3.0)),
        ("st_10_2", "Supertrend 10/2", lambda cs: pb.Supertrend("", cs, 10, 2.0)),
        ("st_10_4", "Supertrend 10/4", lambda cs: pb.Supertrend("", cs, 10, 4.0)),
        ("ema50", "Price above EMA50", lambda cs: pb.AboveEma50("", cs)),
    ]


def jan1(year):
    return int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp())


def year_of(ts):
    return datetime.fromtimestamp(ts, timezone.utc).year


def evaluate(hourly, split=SPLIT, fees=FEES, specs=None):
    """Every rule on one coin's hourly candles. Returns {key: {fee: result}}
    plus "bh", and the window: trading starts 60 days after the first candle
    so the slowest indicator (SMA50/EMA50) is live from the first day."""
    candles = pb.aggregate(hourly, DAY)
    start = pb.ceil_day(hourly[0][0] + pb.WARMUP_DAYS * DAY)
    end = hourly[-1][0]
    year_marks = [jan1(y) for y in range(year_of(start) + 1, year_of(end) + 1)]
    marks = sorted(set(year_marks + ([split] if start < split < end else [])))
    out = {"_start": start, "_end": end, "_marks": marks, "_years": year_marks,
           "_split": split if split in marks else None}
    for key, _label, make in (specs or rules()):
        rule = make(candles)
        out[key] = {f: pb.simulate(hourly, DAY, rule, f, start, end, marks) for f in fees}
    out["bh"] = {f: pb.buy_and_hold(hourly, f, start, end, marks) for f in fees}
    return out


def value_at(res, r, ts):
    return res["marks"][r["_marks"].index(ts)]


def yearly(res, r):
    """[(year, return)] per calendar year; the first and last are partial."""
    points = [(r["_start"], 1.0)] + [(m, value_at(res, r, m)) for m in r["_years"]] + \
             [(r["_end"], 1 + res["ret"])]
    return [(year_of(a), (vb / va - 1) if va else 0.0)
            for (a, va), (_b, vb) in zip(points, points[1:])]


def split_returns(res, r):
    """(before split, after split) returns, or (None, None) without a split."""
    if not r["_split"]:
        return None, None
    v = value_at(res, r, r["_split"])
    return v - 1, ((1 + res["ret"]) / v - 1) if v else 0.0


def summary(r, key, fee):
    res = r[key][fee]
    yrs = (r["_end"] - r["_start"]) / (365.25 * DAY)
    total = res["ret"]
    cagr = (1 + total) ** (1 / yrs) - 1 if total > -1 else -1.0
    before, after = split_returns(res, r)
    ys = yearly(res, r)
    bh = dict(yearly(r["bh"][fee], r))
    return {"total": total, "cagr": cagr, "max_dd": res["max_dd"],
            "dd_when": f"{utc(res['dd_from'], '%b %Y')} -> {utc(res['dd_to'], '%b %Y')}",
            "trades_per_year": len(res["trades"]) / yrs, "before": before, "after": after,
            "beat_bh": sum(1 for y, v in ys if v > bh[y]), "years": len(ys),
            "worst": min(v for _, v in ys), "by_year": ys}


def report_coin(coin, r):
    L = []
    w = L.append
    labels = dict((k, label) for k, label, _ in rules())
    labels["bh"] = "Buy and hold"
    keys = [k for k, _, _ in rules()] + ["bh"]
    split = r["_split"]
    w(f"## {coin}: {utc(r['_start'])} -> {utc(r['_end'])} "
      f"({(r['_end'] - r['_start']) / (365.25 * DAY):.1f} years), {MAIN_FEE * 100:.2f}%/side")
    w("")
    w(f"| Rule | Total | CAGR | Max drawdown | Peak -> trough | Trades/yr | Before {utc(split)} | "
      f"{utc(split)} on | Years beating buy & hold | Worst year |")
    w("|" + "---|" * 10)
    for k in keys:
        s = summary(r, k, MAIN_FEE)
        w(f"| {labels[k]} | {pct(s['total'])} | {pct(s['cagr'])} | {pct(s['max_dd'])} | "
          f"{s['dd_when']} | "
          f"{s['trades_per_year']:.1f} | {pct(s['before'])} | {pct(s['after'])} | "
          f"{s['beat_bh']}/{s['years']} | {pct(s['worst'])} |")
    w("")
    years = [y for y, _ in summary(r, "bh", MAIN_FEE)["by_year"]]
    w(f"### {coin} by calendar year ({years[0]} and {years[-1]} partial)")
    w("")
    w("| Rule | " + " | ".join(str(y) for y in years) + " |")
    w("|" + "---|" * (len(years) + 1))
    for k in keys:
        w(f"| {labels[k]} | " + " | ".join(pct(v) for _, v in summary(r, k, MAIN_FEE)["by_year"]) + " |")
    w("")
    a = dict(summary(r, "st_10_3", MAIN_FEE)["by_year"])
    b = dict(summary(r, "sma_20_30", MAIN_FEE)["by_year"])
    wins = sum(1 for y in years if a[y] > b[y])
    w(f"Supertrend 10/3 beat SMA 20/30 in {wins} of {len(years)} calendar years.")
    w("")
    w(f"### {coin} total return (max drawdown) by fee")
    w("")
    fees = sorted(r["bh"])
    w("| Rule | " + " | ".join(f"{f * 100:.2f}%" for f in fees) + " |")
    w("|" + "---|" * (len(fees) + 1))
    for k in keys:
        w(f"| {labels[k]} | " + " | ".join(
            f"{pct(r[k][f]['ret'])} ({pct(r[k][f]['max_dd'])})" for f in fees) + " |")
    w("")
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--coins", nargs="+", default=list(FIRST))
    args = p.parse_args()
    now = int(time.time())
    end = now - now % HOUR - HOUR
    session = requests.Session()
    print(f"Fees per side: {MAIN_FEE * 100:.2f}% headline (Kraken Pro entry-tier taker since "
          f"July 2026; the deployed bot uses market orders). Split at {utc(SPLIT)}, the start "
          f"of the 22-coin window where Supertrend 10/3 looked best. Each coin trades from "
          f"{pb.WARMUP_DAYS} days after its first Coinbase candle.")
    print()
    for coin in args.coins:
        t0 = time.time()
        got = pb.fetch_coinbase(coin, int(FIRST[coin].timestamp()), end, session) or {}
        hourly = sorted((t,) + v for t, v in got.items())
        if len(hourly) < 24 * 365:
            print(f"{coin}: not enough Coinbase history ({len(hourly)} hours).")
            continue
        r = evaluate(hourly)
        print(f"<!-- {coin}: {len(hourly)} hours from {utc(hourly[0][0])}, "
              f"{time.time() - t0:.0f}s -->", flush=True)
        print(report_coin(coin, r))


if __name__ == "__main__":
    main()
