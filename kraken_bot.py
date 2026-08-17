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
                if args.stop_loss and change_pct <= -args.stop_loss:
                    place("sell", position["volume"], price, f"stop-loss {change_pct:.2f}%")
                elif args.take_profit and change_pct >= args.take_profit:
                    place("sell", position["volume"], price, f"take-profit {change_pct:.2f}%")
                elif signal == "sell":
                    place("sell", position["volume"], price, "SMA cross down")
                else:
                    log(f"Holding | price ${price:.2f} | entry "
                        f"${position['entry']:.2f} | {change_pct:+.2f}%")
            else:
                if signal == "buy":
                    volume = round(args.usd / price, pair["lot_decimals"])
                    if volume < pair["ordermin"]:
                        log(f"Buy signal, but ${args.usd:.2f} buys {volume} "
                            f"< Kraken minimum {pair['ordermin']}. Increase --usd.")
                    else:
                        place("buy", volume, price, "SMA cross up")
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
