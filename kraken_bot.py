#!/usr/bin/env python3
"""
Kraken auto-trading bot.

Trades any cryptocurrency against your USD balance using a simple
SMA-crossover strategy with optional stop-loss / take-profit.

SAFE BY DEFAULT: runs in dry-run mode (simulated fills, no real orders)
unless you pass --live.

Usage:
    python3 kraken_bot.py --pair BTC/USD                    # dry run
    python3 kraken_bot.py --pair ETH/USD --usd 100 --live   # real orders

API keys (only needed for --live) are read from the environment:
    export KRAKEN_API_KEY=...
    export KRAKEN_API_SECRET=...
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import requests

API_URL = "https://api.kraken.com"
# Kraken Pro taker fee per side at the entry tier (under $2.5K of 30-day
# volume). Kraken raised it from 0.26% to 0.80% in July 2026; the old value
# sized a full-balance buy $0.02 above what the account could pay. Sizing
# (affordable_usd) and every backtest read this, so keep it at the worst tier
# the account can be on.
TAKER_FEE = 0.008
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_state.json")

# Kraken uses XBT for Bitcoin and prefixes some legacy assets with X/Z.
ASSET_ALIASES = {"BTC": "XBT", "DOGE": "XDG"}


# ---------------------------------------------------------------------------
# Kraken API client
# ---------------------------------------------------------------------------

class KrakenClient:
    def __init__(self, api_key=None, api_secret=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()

    def public(self, method, params=None):
        r = self.session.get(f"{API_URL}/0/public/{method}", params=params or {}, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise RuntimeError(f"Kraken API error ({method}): {data['error']}")
        return data["result"]

    def private(self, method, params=None):
        if not self.api_key or not self.api_secret:
            raise RuntimeError(
                "KRAKEN_API_KEY / KRAKEN_API_SECRET are not set. "
                "Required for live trading."
            )
        params = dict(params or {})
        params["nonce"] = str(int(time.time() * 1000000))
        path = f"/0/private/{method}"
        postdata = urllib.parse.urlencode(params)
        message = path.encode() + hashlib.sha256(
            (params["nonce"] + postdata).encode()
        ).digest()
        signature = hmac.new(
            base64.b64decode(self.api_secret), message, hashlib.sha512
        )
        headers = {
            "API-Key": self.api_key,
            "API-Sign": base64.b64encode(signature.digest()).decode(),
        }
        r = self.session.post(f"{API_URL}{path}", headers=headers, data=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            raise RuntimeError(f"Kraken API error ({method}): {data['error']}")
        return data["result"]

    # -- convenience wrappers -------------------------------------------------

    def resolve_pair(self, pair):
        """Turn 'BTC/USD' into Kraken's canonical pair name and metadata."""
        base, _, quote = pair.upper().partition("/")
        if not quote:
            raise ValueError("Pair must look like BASE/USD, e.g. BTC/USD")
        base = ASSET_ALIASES.get(base, base)
        query = f"{base}{quote}"
        result = self.public("AssetPairs", {"pair": query})
        canonical = next(iter(result))
        info = result[canonical]
        return {
            "name": canonical,
            "altname": info["altname"],
            "base": info["base"],          # e.g. XXBT
            "quote": info["quote"],        # e.g. ZUSD
            "ordermin": float(info["ordermin"]),
            "pair_decimals": info["pair_decimals"],
            "lot_decimals": info["lot_decimals"],
        }

    def ticker_price(self, pair_name):
        result = self.public("Ticker", {"pair": pair_name})
        return float(next(iter(result.values()))["c"][0])  # last trade price

    def ohlc_closes(self, pair_name, interval_min):
        result = self.public("OHLC", {"pair": pair_name, "interval": interval_min})
        candles = next(v for k, v in result.items() if k != "last")
        # Drop the still-forming last candle so signals use closed candles only.
        return [float(c[4]) for c in candles[:-1]]

    def ohlc_candles(self, pair_name, interval_min):
        """Closed candles as (open_time_unix, close) pairs, oldest first.

        Same data and the same closed-only rule as ohlc_closes(), plus the
        candle times the status page needs for its chart. The trading path
        keeps using ohlc_closes().
        """
        result = self.public("OHLC", {"pair": pair_name, "interval": interval_min})
        candles = next(v for k, v in result.items() if k != "last")
        return [(int(c[0]), float(c[4])) for c in candles[:-1]]

    def balances(self):
        return {k: float(v) for k, v in self.private("Balance").items()}

    def market_order(self, pair_name, side, volume, validate=False):
        params = {
            "pair": pair_name,
            "type": side,          # "buy" or "sell"
            "ordertype": "market",
            "volume": f"{volume:.10f}".rstrip("0").rstrip("."),
        }
        if validate:
            params["validate"] = "true"
        return self.private("AddOrder", params)


# ---------------------------------------------------------------------------
# Strategy: SMA crossover + stop-loss / take-profit
# ---------------------------------------------------------------------------

def sma(values, n):
    if len(values) < n:
        return None
    return sum(values[-n:]) / n


def sell_reason(position, price, stop_loss, take_profit, signal):
    """Why an open position should close now, or None to keep holding.

    Shared by the local loop and the deployed tick so the two cannot drift.
    Order matters: a stop-loss wins over a take-profit when a single candle
    spans both, which is the conservative reading.
    """
    change_pct = (price / position["entry"] - 1) * 100
    if stop_loss and change_pct <= -stop_loss:
        return "stop-loss"
    if take_profit and change_pct >= take_profit:
        return "take-profit"
    if signal == "sell":
        return "SMA cross down"
    return None


def buy_volume(usd, price, lot_decimals):
    """Volume a given USD stake buys, rounded to the pair's lot precision."""
    return round(usd / price, lot_decimals)


def affordable_usd(usd_balance, fee=TAKER_FEE, margin=0.995):
    """Largest stake a balance can actually cover once the taker fee is added.

    Spending the whole balance fails: a $65.81 buy costs $65.81 plus the 0.80%
    fee = $66.34, which exceeds the balance. The margin leaves a little extra
    room for the price moving between the quote and the fill.
    """
    return usd_balance / (1 + fee) * margin


def trade_stake(configured_usd, pct=0, usd_balance=None):
    """USD to spend on the next buy.

    `pct` (when set) sizes from the balance instead of a fixed amount, so
    profits compound as the account grows. Either way the stake is capped at
    what the balance can genuinely cover. A balance of None means "unknown" -
    the configured amount is used and the exchange enforces the limit.
    """
    stake = usd_balance * pct / 100 if (pct and usd_balance is not None) else configured_usd
    if usd_balance is None:
        return stake
    return min(stake, affordable_usd(usd_balance))


def crossover_signal(closes, fast_n, slow_n):
    """Return 'buy', 'sell', or None based on the last two closed candles."""
    if len(closes) < slow_n + 1:
        return None
    fast_now, slow_now = sma(closes, fast_n), sma(closes, slow_n)
    fast_prev, slow_prev = sma(closes[:-1], fast_n), sma(closes[:-1], slow_n)
    if fast_prev <= slow_prev and fast_now > slow_now:
        return "buy"
    if fast_prev >= slow_prev and fast_now < slow_now:
        return "sell"
    return None


def buy_reason(signal, closes, fast_n, slow_n, enter_on_trend=True):
    """Why a flat bot should buy now, or None to keep waiting.

    A cross up is the classic entry. With `enter_on_trend` the bot also buys
    when it is flat while the fast SMA already sits above the slow one - the
    state a cross up would have produced. Without it, a bot that starts (or
    restarts) mid-uptrend sits idle until the trend ends and a new one begins,
    which can take months. Re-entry after a cross-down sell is unaffected:
    the fast SMA is below the slow one then, so only a fresh cross buys.
    """
    if signal == "buy":
        return "SMA cross up"
    if enter_on_trend and len(closes) >= slow_n:
        fast_now, slow_now = sma(closes, fast_n), sma(closes, slow_n)
        if fast_now > slow_now:
            return "SMA trend up"
    return None


# ---------------------------------------------------------------------------
# Look-ahead: what the next close must do to trigger a trade (informational)
# ---------------------------------------------------------------------------

def cross_trigger_price(closes, fast_n, slow_n):
    """The next close at which the fast SMA would exactly meet the slow SMA.

    Both SMAs move with the next close P, so the crossing point solves
        (A + P) / fast_n = (B + P) / slow_n
    where A and B are the sums of the last fast_n-1 and slow_n-1 closes:
        P = (fast_n * B - slow_n * A) / (slow_n - fast_n)
    A next close above P leaves the fast SMA above the slow one; below P,
    beneath it. Returns None without enough history.
    """
    if fast_n >= slow_n or len(closes) < slow_n - 1:
        return None
    n = len(closes)
    a = sum(closes[n - (fast_n - 1):])   # empty (0) when fast_n == 1
    b = sum(closes[n - (slow_n - 1):])
    return (fast_n * b - slow_n * a) / (slow_n - fast_n)


PATH_DAYS = (1, 5, 10, 15, 20)  # horizons for "average needed by date"


def average_needed(closes, fast_n, slow_n, days):
    """The steady close that, held for `days` daily closes, lands the fast SMA
    exactly on the slow one at the end.

    With A and B the sums of the last fast_n-days and slow_n-days known closes,
        (A + days*P) / fast_n = (B + days*P) / slow_n
    gives P = (fast_n*B - slow_n*A) / (days * (slow_n - fast_n)). Once days
    reaches fast_n the fast SMA is all steady closes (A = 0) and this is
    B / (slow_n - days). Averaging above P gets the fast SMA above the slow one
    by that day; below P, beneath it. days = 1 is cross_trigger_price(). None
    without enough history, or from slow_n days on, when both SMAs are the
    steady price and cannot cross.
    """
    n = len(closes)
    if fast_n >= slow_n or days < 1 or days >= slow_n or n < slow_n - 1:
        return None
    b = sum(closes[n - (slow_n - days):])
    if days < fast_n:
        a = sum(closes[n - (fast_n - days):])
        return (fast_n * b - slow_n * a) / (days * (slow_n - fast_n))
    return b / (slow_n - days)


def days_if_flat(closes, fast_n, slow_n, price, holding):
    """Daily closes at `price` until the next trade's cross, or None.

    Flat waits for fast > slow, holding for fast < slow. A steady price makes
    both SMAs equal after slow_n closes, so a cross that has not come by then
    never comes; that bounds the loop.
    """
    c = list(closes)
    for d in range(1, slow_n + 1):
        c.append(price)
        f, s = sma(c, fast_n), sma(c, slow_n)
        if f is None or s is None:
            return None
        if (f < s) if holding else (f > s):
            return d
    return None


def next_trade(closes, fast_n, slow_n, price, holding, enter_on_trend=True,
               near_pct=3.0):
    """What the coming daily closes have to do for the strategy to trade.

    Purely informational - nothing here decides a trade. The bot trades at
    whatever the price is at the first tick after the cross; these figures only
    say how far away that cross is:

    - `trigger`: the single next close that would cross the SMAs (None when no
      positive close can). Flat: a close above it buys at the next tick;
      holding: a close below it sells (SMA cross down - a stop-loss or
      take-profit, when enabled, can also sell and is not covered here).
      Often far from the price; meaningful when `near`.
    - `path`: for each of PATH_DAYS, the steady average close that gets the
      cross by then (`avg_needed`, None if no positive price can).
    - `days_if_flat`: closes at today's price until the cross, or None.

    `on_track`: the price is already past `trigger` - if the candle closed now,
    the bot would trade. `near`: on track, or within `near_pct` % of `trigger`
    (0 disables the margin). Returns None with too little history, or in a
    state the rules only leave via the opposite cross first.
    """
    if not price or len(closes) < slow_n:
        return None
    fast_now, slow_now = sma(closes, fast_n), sma(closes, slow_n)
    if holding:
        if fast_now < slow_now:
            return None  # already below: the cross-down edge cannot fire
        side = "sell"
    else:
        if fast_now > slow_now and not enter_on_trend:
            return None  # cross-only entry needs a cross down first
        side = "buy"

    trigger = cross_trigger_price(closes, fast_n, slow_n)
    if trigger is None or trigger <= 0:
        trigger = distance_pct = None
        on_track = near = False
    else:
        on_track = price < trigger if holding else price > trigger
        distance_pct = (trigger / price - 1) * 100
        near = on_track or (near_pct > 0 and abs(distance_pct) <= near_pct)

    path = []
    for d in PATH_DAYS:
        p = average_needed(closes, fast_n, slow_n, d)
        if p is None:
            continue
        ok = p > 0
        path.append({"days": d,
                     "avg_needed": round(p, 2) if ok else None,
                     "vs_now_pct": round((p / price - 1) * 100, 2) if ok else None})
    return {"side": side, "trigger": trigger, "distance_pct": distance_pct,
            "on_track": on_track, "near": near, "path": path,
            "days_if_flat": days_if_flat(closes, fast_n, slow_n, price, holding)}


# ---------------------------------------------------------------------------
# State (persists position across restarts)
# ---------------------------------------------------------------------------

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC] {msg}", flush=True)


def run(args):
    client = KrakenClient(os.environ.get("KRAKEN_API_KEY"),
                          os.environ.get("KRAKEN_API_SECRET"))
    pair = client.resolve_pair(args.pair)
    mode = "LIVE" if args.live else "DRY RUN"
    log(f"Starting bot [{mode}] on {pair['altname']} "
        f"| SMA {args.fast}/{args.slow} on {args.candle}m candles "
        f"| ${args.usd:.2f} per trade "
        f"| SL {args.stop_loss}% / TP {args.take_profit}%")

    if args.live:
        bal = client.balances()
        usd = bal.get("ZUSD", bal.get("USD", 0.0))
        log(f"USD balance: ${usd:.2f}")
        if usd < args.usd:
            log(f"WARNING: balance below trade size (${args.usd:.2f}). "
                f"Buys will fail until funded.")

    state = load_state()
    key = pair["altname"]
    position = state.get(key)  # {"volume": float, "entry": float} or None
    if position:
        log(f"Resuming open position: {position['volume']} @ ${position['entry']:.2f}")

    def place(side, volume, price, reason):
        nonlocal position
        if args.live:
            result = client.market_order(pair["name"], side, volume)
            txid = ",".join(result.get("txid", ["?"]))
            log(f"{side.upper()} ORDER PLACED ({reason}): {volume:.8f} "
                f"{args.pair.split('/')[0]} @ ~${price:.2f} | txid={txid}")
        else:
            log(f"[dry-run] {side.upper()} ({reason}): {volume:.8f} "
                f"{args.pair.split('/')[0]} @ ${price:.2f} "
                f"(~${volume * price:.2f})")
        if side == "buy":
            position = {"volume": volume, "entry": price}
        else:
            entry = position["entry"] if position else price
            pnl = (price - entry) * volume
            log(f"Closed position | entry ${entry:.2f} -> exit ${price:.2f} "
                f"| PnL ${pnl:+.2f} ({(price / entry - 1) * 100:+.2f}%)")
            position = None
        state[key] = position
        save_state(state)

    log("Entering trading loop. Ctrl+C to stop.")
    while True:
        try:
            closes = client.ohlc_closes(pair["name"], args.candle)
            price = client.ticker_price(pair["name"])
            signal = crossover_signal(closes, args.fast, args.slow)

            if position:
                change_pct = (price / position["entry"] - 1) * 100
                reason = sell_reason(position, price, args.stop_loss,
                                     args.take_profit, signal)
                if reason:
                    detail = (reason if reason == "SMA cross down"
                              else f"{reason} {change_pct:.2f}%")
                    place("sell", position["volume"], price, detail)
                else:
                    log(f"Holding | price ${price:.2f} | entry "
                        f"${position['entry']:.2f} | {change_pct:+.2f}%")
            else:
                entry_reason = buy_reason(signal, closes, args.fast, args.slow,
                                   args.enter_on_trend)
                if entry_reason:
                    volume = buy_volume(args.usd, price, pair["lot_decimals"])
                    if volume < pair["ordermin"]:
                        log(f"Buy signal, but ${args.usd:.2f} buys {volume} "
                            f"< Kraken minimum {pair['ordermin']}. Increase --usd.")
                    else:
                        place("buy", volume, price, entry_reason)
                else:
                    fast_v, slow_v = sma(closes, args.fast), sma(closes, args.slow)
                    log(f"No position | price ${price:.2f} | "
                        f"SMA{args.fast} {fast_v:.2f} vs SMA{args.slow} {slow_v:.2f}")

        except KeyboardInterrupt:
            raise
        except Exception as e:
            log(f"Error (will retry): {e}")

        time.sleep(args.poll)


def main():
    p = argparse.ArgumentParser(description="Kraken SMA-crossover trading bot")
    p.add_argument("--pair", default="BTC/USD",
                   help="Trading pair, e.g. BTC/USD, ETH/USD, SOL/USD (default: BTC/USD)")
    p.add_argument("--usd", type=float, default=50.0,
                   help="USD to spend per buy (default: 50)")
    p.add_argument("--fast", type=int, default=10,
                   help="Fast SMA period in candles (default: 10)")
    p.add_argument("--slow", type=int, default=30,
                   help="Slow SMA period in candles (default: 30)")
    p.add_argument("--candle", type=int, default=1440, choices=[1, 5, 15, 30, 60, 240, 1440],
                   help="Candle size in minutes (default: 1440 = daily)")
    p.add_argument("--stop-loss", type=float, default=0.0,
                   help="Stop-loss %% below entry, 0 to disable (default: 0/off)")
    p.add_argument("--take-profit", type=float, default=0.0,
                   help="Take-profit %% above entry, 0 to disable (default: 0/off)")
    p.add_argument("--poll", type=int, default=300,
                   help="Seconds between checks (default: 300)")
    p.add_argument("--no-enter-on-trend", dest="enter_on_trend", action="store_false",
                   help="When flat, wait for a fresh cross up instead of buying "
                        "into an existing uptrend (default: buy into it)")
    p.add_argument("--live", action="store_true",
                   help="Place REAL orders. Without this flag, trades are simulated.")
    args = p.parse_args()

    if args.fast >= args.slow:
        p.error("--fast must be smaller than --slow")
    if args.live:
        print("\n*** LIVE MODE: this will place REAL market orders on Kraken. ***")
        confirm = input("Type 'yes' to continue: ").strip().lower()
        if confirm != "yes":
            print("Aborted.")
            sys.exit(0)

    try:
        run(args)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
