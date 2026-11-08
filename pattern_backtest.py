#!/usr/bin/env python3
"""
Backtest the old PHP bot (samuele-perrone/crypto-signals, last commit
2025-09-10) and the other patterns in that repo, on two years of candles for
its 22 coins, after Kraken's fees.

That bot "worked a bit, then started losing". Its own backtests never tested
its live rule (none of them compute MACD or EMA), covered 2-3 months, and two
of three ignored fees. This answers whether the losses were the code or the
approach.

Ported exactly from kraken_bot.php and indicators/VolumeProfileStrategy.php:
  ema()     SMA-seeded EMA, None until `len` values
  macd()    12/26/9; the signal line is an SMA-seeded EMA over non-null MACD
  VolumeProfileStrategy::getSignal()
  buy:   hist[last] > hist[last-1] and MACD > signal and EMA50 < close
         and volume profile == BUY
  sell:  MACD <= signal or EMA50 >= close, plus a 3% trailing stop from the
         highest price seen (checked every 3 minutes). The volume-profile SELL
         never fired: getSignal() was called without the position.
  4-hour candles: getOhlc() defaults to 240 and is called without an
  interval, so the README's "1 hr timeframe" was not what ran. The bot ran
  every 30 minutes on Kraken's OHLC, whose last candle is still forming.

Simulated on hourly candles:
  "as deployed"     every hour the 4h series is the closed candles plus the
                    forming one built from the hours so far (a flat, zero-
                    volume candle on the hour the previous one closes), and
                    the bot trades at that hour's close. Half the bot's
                    30-minute checks, the same signal.
  "closed candles"  decisions only when a candle closes, from closed candles,
                    executed at that close.
  Stops and targets fill inside the hour: a low at or below the stop sells at
  the stop (at the open if the hour opened below it), a high at or above the
  target sells at the target; the stop wins when both are in the same hour.
  Every order fills at the decision price. That flatters the PHP bot, whose
  limit buys were cancelled if not filled within ~3 minutes and whose limit
  sells, stop-losses included, sat open until the price came back.

Other patterns from the repo, each on closed 4h and closed daily candles:
  MACD alone (in while MACD > signal), price above EMA50, the volume profile
  alone (its own BUY and SELL, with the position passed), the chatgpt.txt spec
  (in after 3 closes above EMA50, out at or below it, 2% trailing stop, 5%
  target), Heikin Ashi as in backtest_ha.php (in on the 3rd green, out on the
  2nd red or a 2% trailing stop) and Supertrend 10/3 (the repo's version is
  commented out of the live bot, so the standard one). Benchmarks: buy and
  hold, and the deployed SMA 20/30 daily bot through compare_strategies'
  sma_rule, i.e. kraken_bot.buy_reason with ENTER_ON_TREND.

Accounting: per coin the whole stake rides every trade and compounds, as in
compare_strategies.py; fees come off both sides. "Portfolio" is an equal
split across the coins with no rebalancing, which is the mean coin return.
"$60 stakes" is the PHP bot's own sizing: every trade $60, P&L summed over
every coin and trade.

Data: Coinbase hourly candles (no key), then Binance's public data dumps,
then KuCoin, for coins an earlier source does not list. None is reachable
from cloud sessions: run on GitHub Actions (.github/workflows/
pattern-backtest.yml).

Usage:
    python3 pattern_backtest.py
    python3 pattern_backtest.py --coins BTC ETH --days 365 --fee 0.25
"""

import argparse
import io
import math
import statistics
import time
import zipfile
from datetime import datetime, timedelta, timezone

import requests

from compare_strategies import sma_rule

HOUR, H4, DAY = 3600, 4 * 3600, 86400
WARMUP_DAYS = 60     # history before a coin's window: daily EMA50 needs 50 candles
QUARTER = 365.25 * DAY / 4

# trading.example.json "pairs", as coin tickers (XDG = DOGE on Kraken).
COINS = ["AAVE", "FET", "DOGE", "SHIB", "TRX", "SPX", "TRUMP", "ETH", "LINK",
         "XRP", "BCH", "BTC", "ALGO", "XLM", "AVAX", "LTC", "DOT", "UNI", "POL",
         "SOL", "ADA", "SUI"]

# Kraken Pro spot, entry tier (< $2.5K 30-day volume), since July 2026.
# The PHP bot placed limit orders at the last price, so maker is its best case.
FEE_MAKER_NOW = 0.004
FEE_TAKER_NOW = 0.008
FEE_MAKER_2025 = 0.0025   # what the bot paid when it ran

UA = {"User-Agent": "crypto_trading-backtest"}


def utc(ts, fmt="%Y-%m-%d"):
    return datetime.fromtimestamp(ts, timezone.utc).strftime(fmt)


# ---------------------------------------------------------------------------
# Data: hourly candles as {open_time: (open, high, low, close, volume)}
# ---------------------------------------------------------------------------

def _get(session, url, params=None, tries=5):
    for attempt in range(tries):
        try:
            r = session.get(url, params=params, headers=UA, timeout=30)
        except requests.RequestException:
            time.sleep(1 + attempt)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(1 + attempt)
            continue
        return r
    return None


def fetch_coinbase(coin, start, end, session):
    """Hourly <coin>-USD candles, or None if Coinbase does not list the coin."""
    out = {}
    t = start
    while t < end:
        t2 = min(t + 299 * HOUR, end)   # 300 candles a request, both ends inclusive
        r = _get(session, f"https://api.exchange.coinbase.com/products/{coin}-USD/candles",
                 {"granularity": HOUR,
                  "start": datetime.fromtimestamp(t, timezone.utc).isoformat(),
                  "end": datetime.fromtimestamp(t2, timezone.utc).isoformat()})
        if r is None or r.status_code in (400, 404):
            return out or None
        r.raise_for_status()
        for ts, low, high, opn, close, vol in r.json():
            out[int(ts)] = (float(opn), float(high), float(low), float(close), float(vol))
        t = t2 + HOUR
        time.sleep(0.15)                 # public limit is ~10 requests/s
    return out or None


def to_seconds(ts):
    """Binance dump timestamps are ms before 2025 and microseconds after."""
    ts = int(ts)
    while ts > 10 ** 11:
        ts //= 1000
    return ts


def parse_binance_csv(text):
    out = {}
    for line in text.splitlines():
        f = line.split(",")
        if len(f) < 6 or not f[0].strip().isdigit():
            continue                     # header row in newer files
        out[to_seconds(f[0])] = (float(f[1]), float(f[2]), float(f[3]), float(f[4]), float(f[5]))
    return out


def fetch_binance_dump(coin, start, end, session):
    """Hourly <coin>USDT from data.binance.vision: monthly files, then daily
    files for the current month (or a month whose monthly file is missing)."""
    sym = f"{coin}USDT"
    base = "https://data.binance.vision/data/spot"
    out = {}

    def grab(url):
        r = _get(session, url, tries=3)
        if r is None or r.status_code != 200:
            return None
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            return parse_binance_csv(z.read(z.namelist()[0]).decode())

    d = datetime.fromtimestamp(start, timezone.utc).replace(day=1, hour=0, minute=0, second=0)
    last = datetime.fromtimestamp(end, timezone.utc)
    while d <= last:
        ym = d.strftime("%Y-%m")
        got = grab(f"{base}/monthly/klines/{sym}/1h/{sym}-1h-{ym}.zip")
        if got is None and (last - d).days < 62:
            # Monthly files appear after the month ends: use daily files for the
            # current month and a just-finished one. An older month with no
            # file predates the listing.
            day = d
            while day.month == d.month and day <= last:
                g = grab(f"{base}/daily/klines/{sym}/1h/{sym}-1h-{day.strftime('%Y-%m-%d')}.zip")
                if g:
                    out.update(g)
                day = datetime.fromtimestamp(day.timestamp() + DAY, timezone.utc)
        else:
            out.update(got)
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
    out = {t: v for t, v in out.items() if start <= t <= end}
    return out or None


def fetch_kucoin(coin, start, end, session):
    """Hourly <coin>-USDT from KuCoin (1500 candles a request, newest first)."""
    out = {}
    t = start
    while t < end:
        t2 = min(t + 1500 * HOUR, end)
        r = _get(session, "https://api.kucoin.com/api/v1/market/candles",
                 {"type": "1hour", "symbol": f"{coin}-USDT", "startAt": t, "endAt": t2})
        if r is None or r.status_code != 200:
            return out or None
        body = r.json()
        if body.get("code") != "200000":
            return out or None
        for ts, opn, close, high, low, vol, _turnover in body.get("data", []):
            out[int(ts)] = (float(opn), float(high), float(low), float(close), float(vol))
        t = t2
        time.sleep(0.2)
    return out or None


SOURCES = [("Coinbase", fetch_coinbase), ("Binance dump", fetch_binance_dump),
           ("KuCoin", fetch_kucoin)]


def fetch_hourly(coin, start, end, session=None):
    """(source name, [(t, o, h, l, c, v)] sorted) from the first source that
    covers the window, else the source with the longest history, else
    (None, []). Under 90 days counts as nothing."""
    s = session or requests.Session()
    best = (None, {})
    for name, fn in SOURCES:
        try:
            got = fn(coin, start, end, s) or {}
        except (requests.RequestException, ValueError, zipfile.BadZipFile):
            got = {}
        if len(got) > len(best[1]):
            best = (name, got)
        if got and min(got) <= start + 7 * DAY:
            break
    name, got = best
    if len(got) < 24 * 90:
        return None, []
    return name, sorted((t,) + v for t, v in got.items())


# ---------------------------------------------------------------------------
# Candles
# ---------------------------------------------------------------------------

def aggregate(hourly, period):
    """Hourly (t,o,h,l,c,v) rows into `period` buckets aligned to UTC (Kraken
    aligns 4h candles to 00:00, 04:00, ...). The last bucket may be partial;
    a bucket counts as closed only once `t + period` has passed."""
    out, cur = [], None
    for t, o, h, l, c, v in hourly:
        b = t - t % period
        if cur is None or cur[0] != b:
            if cur:
                out.append(tuple(cur))
            cur = [b, o, h, l, c, v]
        else:
            cur[2] = max(cur[2], h)
            cur[3] = min(cur[3], l)
            cur[4] = c
            cur[5] += v
    if cur:
        out.append(tuple(cur))
    return out


# ---------------------------------------------------------------------------
# Indicators, ported line for line from kraken_bot.php
# ---------------------------------------------------------------------------

def ema(src, n):
    """KrakenBot::ema / ema_basic: SMA of the first n values, then recursive."""
    out, k, e, s, cnt = [], 2 / (n + 1), None, 0.0, 0
    for v in src:
        if cnt < n:
            s += v
            cnt += 1
            if cnt == n:
                e = s / n
            out.append(e if cnt == n else None)
        else:
            e = v * k + e * (1 - k)
            out.append(e)
    return out


def ema_skip_none(src, n):
    """KrakenBot::ema_series_from_non_null."""
    out, k, buf, e = [None] * len(src), 2 / (n + 1), [], None
    for i, v in enumerate(src):
        if v is None:
            continue
        if len(buf) < n:
            buf.append(v)
            if len(buf) == n:
                e = sum(buf) / n
                out[i] = e
        else:
            e = v * k + e * (1 - k)
            out[i] = e
    return out


def macd(closes, fast=12, slow=26, signal=9):
    """KrakenBot::macd. Returns (ema_fast, ema_slow, macd, signal, hist)."""
    ef, es = ema(closes, fast), ema(closes, slow)
    m = [a - b if a is not None and b is not None else None for a, b in zip(ef, es)]
    s = ema_skip_none(m, signal)
    h = [a - b if a is not None and b is not None else None for a, b in zip(m, s)]
    return ef, es, m, s, h


def step(prev, value, n):
    """One EMA step: the value an EMA series would take if `value` were
    appended. This is how the forming candle's EMA/MACD are computed without
    rebuilding every series each hour; test_pattern checks it matches."""
    k = 2 / (n + 1)
    return value * k + prev * (1 - k)


def price_strength(c):
    _, o, h, l, cl, _ = c
    rng = h - l
    if rng == 0:
        return 0
    body, upper, lower = abs(cl - o), h - max(o, cl), min(o, cl) - l
    if cl > o:
        return body / rng * (1 - upper / rng)
    return -(body / rng) * (1 - lower / rng)


def volume_profile(window, holding=False):
    """VolumeProfileStrategy::getSignal(data, position) on the default config.
    `window` is the last 20+ candles (t,o,h,l,c,v), most recent last; nothing
    in the PHP looks back further than 20."""
    if len(window) < 20:
        return "HOLD"
    i = len(window) - 1
    cur = window[i]
    seg = window[max(0, i - 19):]
    vol_sum = sum(c[5] for c in seg)
    avg_vol = vol_sum / len(seg)
    vwap = (sum((c[2] + c[3] + c[4]) / 3 * c[5] for c in seg) / vol_sum) if vol_sum > 0 else cur[4]
    ratio = cur[5] / avg_vol if avg_vol > 0 else 1
    ps = price_strength(cur)
    r5 = window[max(0, i - 4):]
    a5 = sum(c[5] for c in r5) / len(r5)
    vs = a5 / avg_vol if avg_vol > 0 else 1        # 20-candle average = avg_vol
    rng = cur[2] - cur[3]
    body = abs(cur[4] - cur[1]) / rng if rng != 0 else 0
    s0 = window[max(0, i - 9)][4]
    trend = (cur[4] - s0) / s0 if s0 != 0 else 0
    above, bullish = cur[4] > vwap, cur[4] > cur[1]

    strong_buy = [ratio >= 1.5, above, bullish, ps > 0.001, vs >= 1.2, body > 0.5]
    strong_sell = [ratio >= 1.5, not above, not bullish, ps < -0.001, trend < -0.01]
    spike_buy = [ratio >= 2.0, above, trend > 0, ps > 0]
    if sum(strong_buy) + sum(spike_buy) * 0.5 >= 4 and not holding:
        return "BUY"
    if sum(strong_sell) >= 3 and holding:
        return "SELL"
    if holding and ratio >= 1.5 and not above and ps < -0.005:
        return "SELL"
    return "HOLD"


def heikin_ashi_runs(candles):
    """(green_run, red_run) per candle, as backtest_ha.php counts them."""
    green, red, prev = [], [], None
    for _, o, h, l, c, _ in candles:
        hc = (o + h + l + c) / 4
        ho = (o + c) / 2 if prev is None else (prev[0] + prev[1]) / 2
        prev = (ho, hc)
        g, r = hc > ho, hc < ho
        green.append((green[-1] + 1 if green else 1) if g else 0)
        red.append((red[-1] + 1 if red else 1) if r else 0)
    return green, red


def supertrend_up(candles, period=10, mult=3.0):
    """Standard Supertrend (Wilder ATR): True while in an uptrend, None in warm-up."""
    out = [None] * len(candles)
    trs, atr, fub, flb, up = [], None, None, None, True
    for i, (_, o, h, l, c, _) in enumerate(candles):
        pc = candles[i - 1][4] if i else None
        tr = h - l if pc is None else max(h - l, abs(h - pc), abs(l - pc))
        if atr is None:
            trs.append(tr)
            if len(trs) < period:
                continue
            atr = sum(trs) / period
        else:
            atr = (atr * (period - 1) + tr) / period
        hl2 = (h + l) / 2
        ub, lb = hl2 + mult * atr, hl2 - mult * atr
        if fub is None:
            fub, flb = ub, lb
        else:
            prev_ub, prev_lb = fub, flb
            fub = ub if (ub < prev_ub or pc > prev_ub) else prev_ub
            flb = lb if (lb > prev_lb or pc < prev_lb) else prev_lb
            if up and c < prev_lb:
                up = False
            elif not up and c > prev_ub:
                up = True
        out[i] = up
    return out


# ---------------------------------------------------------------------------
# Rules: decide(i, holding) on closed candle i -> "buy" / "sell" / None
# ---------------------------------------------------------------------------

class Rule:
    """A rule bound to one coin's candles. `trail`/`target` are fractions
    checked inside every hour while holding. A forming rule also implements
    decide_forming(last_closed, part, holding)."""
    forming = False

    def __init__(self, label, candles, trail=None, target=None):
        self.label, self.candles, self.trail, self.target = label, candles, trail, target

    def decide(self, i, holding):
        raise NotImplementedError


class PhpLive(Rule):
    """The PHP bot's live buy/sell rule."""

    def __init__(self, label, candles, trail=0.03, forming=False):
        super().__init__(label, candles, trail=trail)
        self.forming = forming
        closes = [c[4] for c in candles]
        self.ema50 = ema(closes, 50)
        self.ef, self.es, self.m, self.s, self.h = macd(closes)

    def _rule(self, holding, close, ema50, m, s, h, h_prev, window):
        if None in (ema50, m, s, h, h_prev):
            return None
        if holding:
            return "sell" if (m <= s or ema50 >= close) else None
        if h > h_prev and m > s and ema50 < close and volume_profile(window) == "BUY":
            return "buy"
        return None

    def decide(self, i, holding):
        if i < 20:
            return None
        return self._rule(holding, self.candles[i][4], self.ema50[i], self.m[i],
                          self.s[i], self.h[i], self.h[i - 1], self.candles[i - 19:i + 1])

    def decide_forming(self, last, part, holding):
        """`last` = index of the newest closed candle; `part` = the forming one."""
        if last < 20 or None in (self.ema50[last], self.ef[last], self.es[last], self.s[last]):
            return None
        c = part[4]
        ema50 = step(self.ema50[last], c, 50)
        m = step(self.ef[last], c, 12) - step(self.es[last], c, 26)
        s = step(self.s[last], m, 9)
        window = list(self.candles[last - 18:last + 1]) + [part]
        return self._rule(holding, c, ema50, m, s, m - s, self.h[last], window)


class MacdAlone(Rule):
    def __init__(self, label, candles):
        super().__init__(label, candles)
        _, _, self.m, self.s, _ = macd([c[4] for c in candles])

    def decide(self, i, holding):
        if self.s[i] is None:
            return None
        above = self.m[i] > self.s[i]
        return "buy" if (above and not holding) else "sell" if (holding and not above) else None


class AboveEma50(Rule):
    def __init__(self, label, candles):
        super().__init__(label, candles)
        self.e = ema([c[4] for c in candles], 50)

    def decide(self, i, holding):
        if self.e[i] is None:
            return None
        above = self.candles[i][4] > self.e[i]
        return "buy" if (above and not holding) else "sell" if (holding and not above) else None


class OriginalSpec(Rule):
    """chatgpt.txt: buy when EMA50 < close for the last 3 candles; sell when
    EMA50 >= close; 2% trailing stop; sell at +5%."""

    def __init__(self, label, candles):
        super().__init__(label, candles, trail=0.02, target=0.05)
        self.e = ema([c[4] for c in candles], 50)

    def decide(self, i, holding):
        if i < 2 or self.e[i - 2] is None:
            return None
        if holding:
            return "sell" if self.e[i] >= self.candles[i][4] else None
        if all(self.e[j] < self.candles[j][4] for j in (i - 2, i - 1, i)):
            return "buy"
        return None


class VolumeProfileAlone(Rule):
    def decide(self, i, holding):
        if i < 19:
            return None
        sig = volume_profile(self.candles[i - 19:i + 1], holding)
        return "buy" if sig == "BUY" else "sell" if sig == "SELL" else None


class HeikinAshi(Rule):
    def __init__(self, label, candles):
        super().__init__(label, candles, trail=0.02)
        self.green, self.red = heikin_ashi_runs(candles)

    def decide(self, i, holding):
        if i < 3:
            return None
        if holding:
            return "sell" if self.red[i] >= 2 else None
        return "buy" if self.green[i] >= 3 else None


class Supertrend(Rule):
    def __init__(self, label, candles):
        super().__init__(label, candles)
        self.up = supertrend_up(candles)

    def decide(self, i, holding):
        if self.up[i] is None:
            return None
        return "buy" if (self.up[i] and not holding) else "sell" if (holding and not self.up[i]) else None


class SmaBot(Rule):
    """The deployed bot: SMA 20/30 with ENTER_ON_TREND, kraken_bot's own code."""

    def __init__(self, label, candles):
        super().__init__(label, candles)
        self.closes = [c[4] for c in candles]
        self.rule = sma_rule(20, 30, True)

    def decide(self, i, holding):
        if i + 1 < self.rule.warmup:
            return None
        return self.rule(self.closes[:i + 1], holding)


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def stop_slip(hourly, check_minutes=3):
    """Expected fill below a stop level for a bot that checks every
    `check_minutes`: a sampled random walk overshoots a level it crosses by
    about 0.5826 of one step's standard deviation (Siegmund's constant). The
    step's deviation is scaled down from the coin's hourly volatility.
    Filling stops at exactly the stop price instead flatters every stop rule:
    on simulated paths with no edge, a 3% trailing stop "beat" buy and hold by
    tens of percent from that alone (test_pattern pins this)."""
    rets = [math.log(b[4] / a[4]) for a, b in zip(hourly, hourly[1:])
            if a[4] > 0 and b[4] > 0 and b[0] - a[0] == HOUR]
    if len(rets) < 2:
        return 0.0
    return 0.5826 * statistics.pstdev(rets) * math.sqrt(check_minutes / 60)


def simulate(hourly, period, rule, fee, start, end, marks=(), slip=0.0):
    """Run `rule` over the hourly path from `start` to `end`. A stop fills
    `slip` below the stop level (see stop_slip), or at the open after a gap.

    Returns {"ret", "trades": [net returns], "hours_in", "hours", "max_dd",
    "marks": [liquidation value at each mark time]}. Values start at 1.0.
    """
    candles = rule.candles
    idx_of = {c[0]: i for i, c in enumerate(candles)}
    cash, coins, highest, entry = 1.0, 0.0, None, None
    trades, hours_in, hours, peak, max_dd = [], 0, 0, 1.0, 0.0
    mark_vals, mi = [], 0
    k = 0                                   # next candle whose close we have not passed
    part = None                             # forming candle of the current bucket

    def buy(price):
        nonlocal cash, coins, highest, entry
        coins, cash, highest, entry = cash * (1 - fee) / price, 0.0, price, price

    def sell(price):
        nonlocal cash, coins, highest, entry
        cash = coins * price * (1 - fee)
        trades.append((price / entry) * (1 - fee) ** 2 - 1)
        coins, highest, entry = 0.0, None, None

    last_close = None
    for t, o, h, l, c, v in hourly:
        if t > end:
            break
        # 1. candles that closed at or before this hour opened
        while k < len(candles) and candles[k][0] + period <= t:
            close_time = candles[k][0] + period
            if not rule.forming and start <= close_time:
                act = rule.decide(k, coins > 0)
                if act == "buy" and coins == 0:
                    buy(candles[k][4])
                elif act == "sell" and coins > 0:
                    sell(candles[k][4])
            k += 1
        b = t - t % period
        part = [b, o, h, l, c, v] if (part is None or part[0] != b) else \
            [b, part[1], max(part[2], h), min(part[3], l), c, part[5] + v]
        last_close = c
        if t < start:
            continue
        hours += 1
        # 2. stop and target inside the hour
        if coins > 0:
            if rule.trail:
                stop = highest * (1 - rule.trail)
                if l <= stop:
                    sell(o if o <= stop else stop * (1 - slip))
            if coins > 0 and rule.target and h >= entry * (1 + rule.target):
                sell(max(o, entry * (1 + rule.target)))
            if coins > 0:
                highest = max(highest, h)
        # 3. the deployed bot's check at this hour's close, on the forming candle
        if rule.forming:
            T = t + HOUR
            if T % period == 0:            # the bucket just closed; a new one opens
                last = idx_of[b]
                forming = (T, c, c, c, c, 0.0)
            else:
                last = idx_of[b] - 1
                forming = tuple(part)
            act = rule.decide_forming(last, forming, coins > 0)
            if act == "buy" and coins == 0:
                buy(c)
            elif act == "sell" and coins > 0:
                sell(c)
        if coins > 0:
            hours_in += 1
        value = cash + coins * c * (1 - fee)
        peak = max(peak, value)
        max_dd = min(max_dd, value / peak - 1)
        while mi < len(marks) and t + HOUR >= marks[mi]:
            mark_vals.append(value)
            mi += 1
    if coins > 0:
        sell(last_close)                    # liquidate at the end, counted as a trade
    while mi < len(marks):
        mark_vals.append(cash)
        mi += 1
    return {"ret": cash - 1, "trades": trades, "hours_in": hours_in, "hours": hours,
            "max_dd": max_dd, "marks": mark_vals}


def buy_and_hold(hourly, fee, start, end, marks=()):
    path = [r for r in hourly if start <= r[0] <= end]
    entry = path[0][4]
    vals, mi = [], 0
    peak, max_dd = 1.0, 0.0
    for t, *_rest in path:
        value = (1 - fee) ** 2 * _rest[3] / entry
        peak = max(peak, value)
        max_dd = min(max_dd, value / peak - 1)
        while mi < len(marks) and t + HOUR >= marks[mi]:
            vals.append(value)
            mi += 1
    while mi < len(marks):
        vals.append(vals[-1] if vals else 1.0)
        mi += 1
    ret = (1 - fee) ** 2 * path[-1][4] / entry - 1
    return {"ret": ret, "trades": [ret], "hours_in": len(path), "hours": len(path),
            "max_dd": max_dd, "marks": vals}


# Rows of the report: (key, label, period, factory(candles) -> Rule)
def rule_specs():
    return [
        ("php_live", "PHP live rule, as deployed (forming 4h candles, 3% stop)", H4,
         lambda cs: PhpLive("as deployed", cs, forming=True)),
        ("php_closed", "PHP live rule, closed 4h candles (3% stop)", H4,
         lambda cs: PhpLive("closed", cs)),
        ("php_closed_nostop", "PHP live rule, closed 4h candles, no stop", H4,
         lambda cs: PhpLive("closed, no stop", cs, trail=None)),
        ("php_closed_1d", "PHP live rule, closed daily candles (3% stop)", DAY,
         lambda cs: PhpLive("daily", cs)),
        ("macd_4h", "MACD above signal, 4h", H4, lambda cs: MacdAlone("", cs)),
        ("macd_1d", "MACD above signal, daily", DAY, lambda cs: MacdAlone("", cs)),
        ("ema_4h", "Price above EMA50, 4h", H4, lambda cs: AboveEma50("", cs)),
        ("ema_1d", "Price above EMA50, daily", DAY, lambda cs: AboveEma50("", cs)),
        ("spec_4h", "chatgpt.txt spec (3 closes > EMA50, 2% stop, +5%), 4h", H4,
         lambda cs: OriginalSpec("", cs)),
        ("spec_1d", "chatgpt.txt spec (3 closes > EMA50, 2% stop, +5%), daily", DAY,
         lambda cs: OriginalSpec("", cs)),
        ("vp_4h", "Volume profile alone, 4h", H4, lambda cs: VolumeProfileAlone("", cs)),
        ("vp_1d", "Volume profile alone, daily", DAY, lambda cs: VolumeProfileAlone("", cs)),
        ("ha_4h", "Heikin Ashi 3 green / 2 red, 2% stop, 4h", H4, lambda cs: HeikinAshi("", cs)),
        ("ha_1d", "Heikin Ashi 3 green / 2 red, 2% stop, daily", DAY, lambda cs: HeikinAshi("", cs)),
        ("st_4h", "Supertrend 10/3, 4h", H4, lambda cs: Supertrend("", cs)),
        ("st_1d", "Supertrend 10/3, daily", DAY, lambda cs: Supertrend("", cs)),
        ("sma_1d", "Deployed bot: SMA 20/30 daily (ENTER_ON_TREND)", DAY,
         lambda cs: SmaBot("", cs)),
    ]


def evaluate_coin(hourly, fee, start, end, specs=None, extra_fees=()):
    """All rules on one coin. Returns {key: {fee: result}} plus "bh".

    Quarter marks are calendar dates from the shared `start`, so quarters line
    up across coins; `_active[q]` is False for a quarter that began before
    this coin's own window (a late listing), which the averages skip."""
    start = start - start % DAY                     # align to a daily close
    coin_start = max(start, hourly[0][0] + WARMUP_DAYS * DAY)
    coin_start = coin_start - coin_start % DAY + (DAY if coin_start % DAY else 0)
    marks = [start + q * QUARTER for q in range(1, 9)]
    candles = {H4: aggregate(hourly, H4), DAY: aggregate(hourly, DAY)}
    slip = stop_slip([r for r in hourly if r[0] >= coin_start])
    out = {"_start": coin_start, "_end": min(end, hourly[-1][0]), "_marks": marks,
           "_active": [m - QUARTER >= coin_start for m in marks], "_slip": slip}
    start = coin_start
    for key, _label, period, make in (specs or rule_specs()):
        rule = make(candles[period])
        fees = [fee, 0.0] + [f for f in extra_fees if key in ("php_live", "sma_1d")]
        out[key] = {f: simulate(hourly, period, rule, f, start, end, marks, slip) for f in fees}
    out["bh"] = {f: buy_and_hold(hourly, f, start, end, marks) for f in (fee, 0.0)}
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def pct(x, signed=True):
    return f"{x * 100:+.1f}%" if signed else f"{x * 100:.1f}%"


def summarize(results, key, fee):
    rows = [(coin, r[key][fee], r["bh"][fee if fee in r["bh"] else 0.0])
            for coin, r in results.items() if key in r and fee in r[key]]
    rets = [x["ret"] for _, x, _ in rows]
    trades = [t for _, x, _ in rows for t in x["trades"]]
    years = sum(x["hours"] for _, x, _ in rows) / (365.25 * 24)
    active = [r["_active"] for coin, r in results.items() if key in r and fee in r[key]]

    def growth(m, a, b):
        """Value change from mark a-1 (a=0: the start) to mark b."""
        prev = m[a - 1] if a else 1.0
        return m[b] / prev - 1 if prev else 0.0

    def avg(a, b):
        vals = [growth(x["marks"], a, b) for (_, x, _), act in zip(rows, active)
                if all(act[a:b + 1])]
        return statistics.mean(vals) if vals else 0.0

    quarters = [avg(q, q) for q in range(8)]
    y1, y2 = avg(0, 3), avg(4, 7)
    return {
        "n": len(rows),
        "mean": statistics.mean(rets) if rets else 0.0,
        "median": statistics.median(rets) if rets else 0.0,
        "beat_bh": sum(1 for _, x, b in rows if x["ret"] > b["ret"]),
        "profitable": sum(1 for r in rets if r > 0),
        "trades_per_year": len(trades) / len(rows) / (years / len(rows)) if rows and years else 0,
        "win_rate": sum(1 for t in trades if t > 0) / len(trades) if trades else 0,
        "avg_trade": statistics.mean(trades) if trades else 0,
        "in_market": (sum(x["hours_in"] for _, x, _ in rows) /
                      max(1, sum(x["hours"] for _, x, _ in rows))),
        "median_dd": statistics.median([x["max_dd"] for _, x, _ in rows]) if rows else 0,
        "stake_pnl": sum(60 * t for t in trades),
        "y1": y1, "y2": y2, "quarters": quarters,
    }


def report(results, sources, fee, start_ts, end_ts, missing, extra_fees):
    L = []
    w = L.append
    coins = list(results)
    w(f"Window {utc(start_ts)} -> {utc(end_ts)} ({(end_ts - start_ts) / DAY:.0f} days), "
      f"{len(coins)} of {len(coins) + len(missing)} coins. Fee {fee * 100:.2f}%/side "
      f"(Kraken Pro maker, entry tier, since July 2026) unless stated; the bot paid "
      f"{FEE_MAKER_2025 * 100:.2f}% in 2025. Coins listed late start {WARMUP_DAYS} days "
      f"after their first candle.")
    w("")
    by_src = {}
    for coin, s in sources.items():
        by_src.setdefault(s, []).append(coin)
    w("Data: " + "; ".join(f"{s}: {', '.join(cs)}" for s, cs in by_src.items()) + ".")
    if missing:
        w(f"No two-year hourly source reachable for: {', '.join(missing)}.")
    w("")

    head = ("| Rule | Portfolio | Before fees | Year 1 | Year 2 | Beat buy & hold | "
            "In profit | Trades/coin/yr | Win rate | Avg trade | $60 stakes |")
    sep = "|" + "---|" * 11

    def row(label, key):
        s, z = summarize(results, key, fee), summarize(results, key, 0.0)
        return (f"| {label} | {pct(s['mean'])} | {pct(z['mean'])} | {pct(s['y1'])} | "
                f"{pct(s['y2'])} | {s['beat_bh']}/{s['n']} | {s['profitable']}/{s['n']} | "
                f"{s['trades_per_year']:.0f} | {pct(s['win_rate'], False)} | "
                f"{pct(s['avg_trade'])} | ${s['stake_pnl']:+,.0f} |")

    specs = {k: label for k, label, _p, _m in rule_specs()}
    w("## The PHP bot's live rule")
    w("")
    w(head)
    w(sep)
    for k in ("php_live", "php_closed", "php_closed_nostop", "php_closed_1d"):
        w(row(specs[k], k))
    w(row("Buy and hold (benchmark)", "bh"))
    w(row(specs["sma_1d"], "sma_1d"))
    w("")
    w("Portfolio = equal split across the coins, no rebalancing (the mean coin "
      "return). Year 1/2 = mean coin return in each year. Beat buy & hold and In "
      "profit count coins. $60 stakes = the PHP bot's sizing: $60 a trade, P&L "
      "summed over every coin and trade.")
    w("")
    w("## Other patterns from the repo")
    w("")
    w(head)
    w(sep)
    for k in ("macd_4h", "macd_1d", "ema_4h", "ema_1d", "spec_4h", "spec_1d",
              "vp_4h", "vp_1d", "ha_4h", "ha_1d", "st_4h", "st_1d"):
        w(row(specs[k], k))
    w(row("Buy and hold (benchmark)", "bh"))
    w("")

    w("## By quarter: average coin return")
    w("")
    marks = next(iter(results.values()))["_marks"]
    qs = [utc(m - QUARTER, "%b %y") for m in marks]
    w("| Rule | " + " | ".join(qs) + " |")
    w("|" + "---|" * (len(qs) + 1))
    for label, key in (("PHP rule, as deployed", "php_live"),
                       ("PHP rule, closed 4h", "php_closed"),
                       ("Price above EMA50, daily", "ema_1d"),
                       ("SMA 20/30 daily", "sma_1d"),
                       ("Buy and hold", "bh")):
        s = summarize(results, key, fee)
        w(f"| {label} | " + " | ".join(pct(q) for q in s["quarters"]) + " |")
    w("")
    w("Calendar quarters from the window start. A late-listed coin enters the "
      "averages (here and in Year 1/2) from the first quarter it traded in full.")
    w("")

    if extra_fees:
        w("## Fee sensitivity")
        w("")
        w("| Rule | " + " | ".join(f"{f * 100:.2f}%/side" for f in (0.0, *extra_fees, fee)) + " |")
        w("|" + "---|" * (len(extra_fees) + 3))
        for key in ("php_live", "sma_1d"):
            cells = []
            for f in (0.0, *extra_fees, fee):
                cells.append(pct(summarize(results, key, f)["mean"]))
            w(f"| {specs[key]} | " + " | ".join(cells) + " |")
        w("")
        w(f"The deployed SMA bot uses market orders, so it pays the taker fee "
          f"({FEE_TAKER_NOW * 100:.2f}% at the entry tier).")
        w("")

    w("## Per coin: the PHP live rule")
    w("")
    w("| Coin | Window from | As deployed | Closed 4h | Closed 4h, no stop | "
      "Trades (deployed) | Buy & hold |")
    w("|---|---|---|---|---|---|---|")
    for coin, r in results.items():
        a, c, n = r["php_live"][fee], r["php_closed"][fee], r["php_closed_nostop"][fee]
        w(f"| {coin} | {utc(r['_start'])} | {pct(a['ret'])} | {pct(c['ret'])} | "
          f"{pct(n['ret'])} | {len(a['trades'])} | {pct(r['bh'][fee]['ret'])} |")
    w("")
    w("Assumptions that flatter the strategies: every signal order fills at the "
      "decision price (no spread, no unfilled limit orders). Stops fill below the "
      "stop by the expected overshoot of a bot checking every 3 minutes (per coin, "
      "from its hourly volatility; median " +
      f"{statistics.median(r['_slip'] for r in results.values()) * 100:.2f}%) or at "
      "the open after a gap. On simulated no-edge paths that still leaves stop "
      "rules about 0.02% a stop better off than they would really be.")
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--coins", nargs="+", default=COINS)
    p.add_argument("--days", type=int, default=730)
    p.add_argument("--fee", type=float, default=FEE_MAKER_NOW * 100, help="%% per side")
    args = p.parse_args()
    fee = args.fee / 100
    extra = (FEE_MAKER_2025, FEE_TAKER_NOW)

    now = int(time.time())
    end = now - now % HOUR - HOUR
    start = end - args.days * DAY
    session = requests.Session()
    results, sources, missing = {}, {}, []
    for coin in args.coins:
        t0 = time.time()
        src, hourly = fetch_hourly(coin, start - WARMUP_DAYS * DAY, end, session)
        if not hourly:
            missing.append(coin)
            print(f"<!-- {coin}: no source -->", flush=True)
            continue
        sources[coin] = src
        results[coin] = evaluate_coin(hourly, fee, start, end, extra_fees=extra)
        print(f"<!-- {coin}: {src}, {len(hourly)} hours from {utc(hourly[0][0])}, "
              f"{time.time() - t0:.0f}s -->", flush=True)
    if not results:
        print("No data.")
        return
    first_start = min(r["_start"] for r in results.values())
    print()
    print(report(results, sources, fee, first_start, end, missing, extra))


if __name__ == "__main__":
    main()
