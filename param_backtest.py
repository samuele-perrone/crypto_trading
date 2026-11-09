#!/usr/bin/env python3
"""
Would tuning the SMA or Supertrend settings make the bot more profitable?

Some setting always looks best in hindsight; the question is whether
settings chosen on past data keep winning on data that came after. So this
runs a walk-forward test on ETH (since 2016) and BTC (since 2015), daily
candles, 0.80%/side:

  hindsight best   the single setting with the best return over the test
                   window itself - what tuning on the same data shows, and
                   not something anyone could have traded
  walk-forward     at every 1 January, pick the setting with the best return
                   over the previous 2 years (or over all history so far) and
                   trade the coming year with it; one continuous account, so a
                   change of setting only trades when the two settings disagree
  fixed            SMA 20/30 (deployed), SMA 10/30, Supertrend 10/3

Test window: 2019-01-01 to now, the first 1 January with two full years of
history behind it for both coins. Grids: SMA fast {5..50} x slow {20..200}
(61 pairs, fast < slow), Supertrend period {5..50} x multiplier {1.5..5}
(49 pairs).

The rules are the deployed ones, written as state machines so 110 settings
x 10 years run in seconds: SMA buys whenever fast > slow (the cross up or
ENTER_ON_TREND) and sells when fast < slow (crossover_signal's cross down);
Supertrend holds while its trend is up. test_param checks both against
pattern_backtest.simulate running kraken_bot's own code.

Data: Coinbase hourly candles via pattern_backtest, reachable only from
GitHub Actions (.github/workflows/param-backtest.yml).

Usage:
    python3 param_backtest.py
    python3 param_backtest.py --coins ETH
"""

import argparse
import statistics
import time
from datetime import datetime, timezone

import requests

import long_backtest as lb
import pattern_backtest as pb
from pattern_backtest import DAY, HOUR, pct, utc

FEE = 0.008
TEST_FROM = datetime(2019, 1, 1, tzinfo=timezone.utc)
SMA_FAST = (5, 10, 15, 20, 25, 30, 40, 50)
SMA_SLOW = (20, 30, 40, 50, 60, 75, 100, 150, 200)
ST_PERIOD = (5, 7, 10, 14, 20, 30, 50)
ST_MULT = (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0)
FIXED = [("sma", (20, 30), "SMA 20/30 (deployed)"), ("sma", (10, 30), "SMA 10/30"),
         ("st", (10, 3.0), "Supertrend 10/3")]


def daily_candles(hourly):
    """Closed daily candles only: today's partial candle is dropped."""
    cs = pb.aggregate(hourly, DAY)
    if cs and cs[-1][0] + DAY > hourly[-1][0] + HOUR:
        cs = cs[:-1]
    return cs


def sma_series(closes, n):
    out, s = [None] * len(closes), 0.0
    for i, c in enumerate(closes):
        s += c
        if i >= n:
            s -= closes[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def sma_state(closes, fast, slow, cache=None):
    """True = be in (fast > slow), False = be out (fast < slow), None = keep
    whatever you have (equal, or warm-up)."""
    cache = {} if cache is None else cache
    f = cache.setdefault(fast, sma_series(closes, fast))
    s = cache.setdefault(slow, sma_series(closes, slow))
    return [None if a is None or b is None or a == b else a > b for a, b in zip(f, s)]


def st_state(candles, period, mult):
    return pb.supertrend_up(candles, period, mult)


def run(closes, state, i0, i1, fee=FEE):
    """Trade state[i0..i1-1] at each close, liquidate at closes[i1].
    Returns (return, trades, max drawdown on daily closes, in_market_days)."""
    cash, coins, trades, peak, dd, days_in = 1.0, 0.0, 0, 1.0, 0.0, 0
    for i in range(i0, i1):
        want, p = state[i], closes[i]
        if want is True and coins == 0:
            coins, cash = cash * (1 - fee) / p, 0.0
            trades += 1
        elif want is False and coins > 0:
            cash, coins = coins * p * (1 - fee), 0.0
        if coins:
            days_in += 1
        v = cash + coins * p * (1 - fee)
        peak = max(peak, v)
        dd = min(dd, v / peak - 1)
    final = cash + coins * closes[i1] * (1 - fee)
    peak = max(peak, final)
    dd = min(dd, final / peak - 1)
    return final - 1, trades, dd, days_in


def grids(candles, closes):
    """{(kind, params): state series} for every setting."""
    cache, out = {}, {}
    for f in SMA_FAST:
        for s in SMA_SLOW:
            if f < s:
                out[("sma", (f, s))] = sma_state(closes, f, s, cache)
    for p in ST_PERIOD:
        for m in ST_MULT:
            out[("st", (p, m))] = st_state(candles, p, m)
    return out


def year_starts(candles, first_year, last_year):
    """{year: index of the first candle on or after 1 January}."""
    idx, y = {}, first_year
    for i, c in enumerate(candles):
        while y <= last_year and c[0] >= int(datetime(y, 1, 1, tzinfo=timezone.utc).timestamp()):
            idx[y] = i
            y += 1
    return idx


def walk_forward(candles, closes, states, kind, lookback_years, i_test, i_end):
    """Splice each year's chosen setting into one state series and trade it.
    Returns (result tuple, [(year, params, lookback return)])."""
    y0 = datetime.fromtimestamp(candles[i_test][0], timezone.utc).year
    y1 = datetime.fromtimestamp(candles[i_end][0], timezone.utc).year
    starts = year_starts(candles, 2010, y1 + 1)
    first_i = next(i for i, c in enumerate(closes) if c)            # first candle
    spliced, picks = [None] * len(closes), []
    for y in range(y0, y1 + 1):
        a = starts.get(y)
        b = starts.get(y + 1, i_end + 1)
        if a is None:
            continue
        lb_from = starts.get(y - lookback_years, first_i) if lookback_years else first_i
        lb_from = max(lb_from, first_i + 60)                        # indicator warm-up
        best = max((k for k in states if k[0] == kind),
                   key=lambda k: run(closes, states[k], lb_from, a)[0])
        picks.append((y, best[1], run(closes, states[best], lb_from, a)[0]))
        for i in range(a, min(b, len(closes))):
            spliced[i] = states[best][i]
    # before the test window: the first pick's own state, so day one starts
    # in the position that setting would hold
    first = next(k for k in states if k[0] == kind and k[1] == picks[0][1])
    for i in range(i_test):
        spliced[i] = states[first][i]
    return run(closes, spliced, i_test, i_end), picks


def label(kind, params):
    return f"SMA {params[0]}/{params[1]}" if kind == "sma" else f"Supertrend {params[0]}/{params[1]:g}"


def analyse(coin, hourly):
    candles = daily_candles(hourly)
    closes = [c[4] for c in candles]
    states = grids(candles, closes)
    t_test = int(TEST_FROM.timestamp())
    i_test = next(i for i, c in enumerate(candles) if c[0] >= t_test)
    i_end = len(candles) - 1
    years = (candles[i_end][0] - candles[i_test][0]) / (365.25 * DAY)
    res = {k: run(closes, st, i_test, i_end) for k, st in states.items()}
    bh = (closes[i_end] * (1 - FEE) ** 2 / closes[i_test] - 1)
    L = []
    w = L.append

    def line(name, r):
        ret, trades, dd, _ = r
        cagr = (1 + ret) ** (1 / years) - 1 if ret > -1 else -1
        return (f"| {name} | {pct(ret)} | {pct(cagr)} | {pct(dd)} | {trades / years:.1f} |")

    w(f"## {coin}: test window {utc(candles[i_test][0])} -> {utc(candles[i_end][0])} "
      f"({years:.1f} years), {FEE * 100:.2f}%/side")
    w("")
    w("| Strategy | Total | CAGR | Max drawdown | Buys/yr |")
    w("|---|---|---|---|---|")
    for kind, name in (("sma", "SMA"), ("st", "Supertrend")):
        best = max((k for k in res if k[0] == kind), key=lambda k: res[k][0])
        w(line(f"Hindsight best {name}: {label(*best)} (not tradable)", res[best]))
    wf = {}
    for kind in ("sma", "st"):
        for lbk, lbname in ((2, "previous 2 years"), (0, "all history so far")):
            r, picks = walk_forward(candles, closes, states, kind, lbk, i_test, i_end)
            wf[(kind, lbk)] = picks
            w(line(f"Walk-forward {'SMA' if kind == 'sma' else 'Supertrend'}, re-picked "
                   f"yearly on {lbname}", r))
    for kind, params, name in FIXED:
        w(line(f"Fixed {name}", res[(kind, params)]))
    w(f"| Buy and hold | {pct(bh)} | {pct((1 + bh) ** (1 / years) - 1)} | - | - |")
    w("")

    for kind, name in (("sma", "SMA"), ("st", "Supertrend")):
        rets = sorted(res[k][0] for k in res if k[0] == kind)
        n = len(rets)
        fixed_k = ("sma", (20, 30)) if kind == "sma" else ("st", (10, 3.0))
        rank = 1 + sum(1 for r in rets if r > res[fixed_k][0])
        w(f"All {n} {name} settings over the test window: median {pct(statistics.median(rets))}, "
          f"worst {pct(rets[0])}, best {pct(rets[-1])}; {sum(1 for r in rets if r > bh)}/{n} beat "
          f"buy and hold. {label(*fixed_k)} ranks {rank} of {n}.")
        w("")

    w(f"### {coin}: what walk-forward picked each year (and the lookback return that won it)")
    w("")
    w("| Year | SMA, previous 2 yrs | SMA, all history | Supertrend, previous 2 yrs | Supertrend, all history |")
    w("|---|---|---|---|---|")
    for row in zip(wf[("sma", 2)], wf[("sma", 0)], wf[("st", 2)], wf[("st", 0)]):
        cells = [f"{label(kind, p)} ({pct(r)})" for (kind, (y, p, r)) in zip(("sma", "sma", "st", "st"), row)]
        w(f"| {row[0][0]} | " + " | ".join(cells) + " |")
    w("")

    w(f"### {coin}: every SMA setting over the test window (rows fast, columns slow)")
    w("")
    w("| fast \\ slow | " + " | ".join(str(s) for s in SMA_SLOW) + " |")
    w("|" + "---|" * (len(SMA_SLOW) + 1))
    for f in SMA_FAST:
        w(f"| {f} | " + " | ".join(pct(res[("sma", (f, s))][0]) if f < s else "" for s in SMA_SLOW) + " |")
    w("")
    w(f"### {coin}: every Supertrend setting over the test window (rows period, columns multiplier)")
    w("")
    w("| period \\ mult | " + " | ".join(f"{m:g}" for m in ST_MULT) + " |")
    w("|" + "---|" * (len(ST_MULT) + 1))
    for p in ST_PERIOD:
        w(f"| {p} | " + " | ".join(pct(res[("st", (p, m))][0]) for m in ST_MULT) + " |")
    w("")
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--coins", nargs="+", default=list(lb.FIRST))
    args = p.parse_args()
    now = int(time.time())
    end = now - now % HOUR - HOUR
    session = requests.Session()
    print(f"Daily candles, {FEE * 100:.2f}%/side. Walk-forward re-picks the best setting "
          f"every 1 January using only data before it.")
    print()
    for coin in args.coins:
        t0 = time.time()
        got = pb.fetch_coinbase(coin, int(lb.FIRST[coin].timestamp()), end, session) or {}
        hourly = sorted((t,) + v for t, v in got.items())
        if len(hourly) < 24 * 365 * 3:
            print(f"{coin}: not enough Coinbase history ({len(hourly)} hours).")
            continue
        text = analyse(coin, hourly)
        print(f"<!-- {coin}: {len(hourly)} hours from {utc(hourly[0][0])}, "
              f"{time.time() - t0:.0f}s -->", flush=True)
        print(text)


if __name__ == "__main__":
    main()
