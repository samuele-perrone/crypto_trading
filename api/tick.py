"""
Vercel Cron endpoint: runs one tick of the Kraken SMA-crossover strategy.

Called on a schedule (see vercel.json). Reads config from env vars:

    PAIR            trading pair, e.g. ETH/USD        (default ETH/USD)
    SMA_FAST        fast SMA period in daily candles  (default 20)
    SMA_SLOW        slow SMA period in daily candles  (default 30)
    USD_PER_TRADE   USD spent per buy                 (default 50)
    STOP_LOSS_PCT   0 disables                        (default 0)
    TAKE_PROFIT_PCT 0 disables                        (default 0)
    LIVE            "true" places real orders         (default: dry run)
    KRAKEN_API_KEY / KRAKEN_API_SECRET   required only when LIVE=true
    CRON_SECRET     if set, requests must carry Authorization: Bearer <secret>

Position state is stored in a local SQLite file (table `bot_state`), created
automatically on first use:

    BOT_DB_PATH     path to the SQLite file (default: bot_state.db in the repo)

WARNING: on Vercel this defaults to /tmp/bot_state.db, which is wiped between
invocations — the bot forgets any open position between ticks. Point
BOT_DB_PATH at durable storage, or run the bot somewhere with a real disk.
"""

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from kraken_bot import KrakenClient, sma, crossover_signal  # noqa: E402
from state_store import load_position, save_position, db_path, is_ephemeral  # noqa: E402

import requests  # noqa: E402


# ---------------------------------------------------------------------------
# Telegram notifications (optional)
# ---------------------------------------------------------------------------

def notify(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception:
        pass  # notifications must never break trading


# ---------------------------------------------------------------------------
# One strategy tick
# ---------------------------------------------------------------------------

def run_tick():
    pair_arg = os.environ.get("PAIR") or "ETH/USD"
    fast = int(os.environ.get("SMA_FAST") or 20)
    slow = int(os.environ.get("SMA_SLOW") or 30)
    usd = float(os.environ.get("USD_PER_TRADE") or 50)
    stop_loss = float(os.environ.get("STOP_LOSS_PCT") or 0)
    take_profit = float(os.environ.get("TAKE_PROFIT_PCT") or 0)
    live = os.environ.get("LIVE", "").lower() == "true"

    out = {
        "time": datetime.now(timezone.utc).isoformat(),
        "pair": pair_arg,
        "mode": "live" if live else "dry-run",
        "action": "none",
    }

    client = KrakenClient(os.environ.get("KRAKEN_API_KEY"),
                          os.environ.get("KRAKEN_API_SECRET"))
    pair = client.resolve_pair(pair_arg)
    closes = client.ohlc_closes(pair["name"], 1440)
    price = client.ticker_price(pair["name"])
    signal = crossover_signal(closes, fast, slow)

    out["price"] = price
    out["sma_fast"] = round(sma(closes, fast), 4)
    out["sma_slow"] = round(sma(closes, slow), 4)
    out["signal"] = signal

    state_key = f"kraken_bot:{pair['altname']}"
    position = load_position(state_key)
    out["position"] = position
    out["state_db"] = db_path()
    if is_ephemeral():
        out["state_warning"] = ("SQLite file lives on ephemeral storage — any open "
                                "position is forgotten between ticks. Set BOT_DB_PATH "
                                "to durable storage.")

    def execute(side, volume, reason):
        if live:
            result = client.market_order(pair["name"], side, volume)
            out["txid"] = result.get("txid")
        out["action"] = f"{side} ({reason})"
        out["volume"] = volume

    if position:
        change_pct = (price / position["entry"] - 1) * 100
        out["unrealized_pct"] = round(change_pct, 2)
        sell_reason = None
        if stop_loss and change_pct <= -stop_loss:
            sell_reason = "stop-loss"
        elif take_profit and change_pct >= take_profit:
            sell_reason = "take-profit"
        elif signal == "sell":
            sell_reason = "SMA cross down"
        if sell_reason:
            execute("sell", position["volume"], sell_reason)
            out["realized_pct"] = round(change_pct, 2)
            save_position(state_key, None)
            notify(f"🔴 SOLD {position['volume']} {pair_arg} @ ${price:,.2f} "
                   f"({sell_reason})\nPnL: {change_pct:+.2f}% "
                   f"[{out['mode']}]")
    else:
        if signal == "buy":
            volume = round(usd / price, pair["lot_decimals"])
            if volume < pair["ordermin"]:
                out["action"] = (f"buy skipped: {volume} below Kraken minimum "
                                 f"{pair['ordermin']} — increase USD_PER_TRADE")
            else:
                execute("buy", volume, "SMA cross up")
                save_position(state_key, {"volume": volume, "entry": price})
                notify(f"🟢 BOUGHT {volume} {pair_arg} @ ${price:,.2f} "
                       f"(~${usd:.2f}) [{out['mode']}]")

    # Daily proof-of-life when nothing traded (disable with DAILY_REPORT=false)
    if out["action"] == "none" and os.environ.get("DAILY_REPORT", "true").lower() != "false":
        if position:
            status = (f"holding {position['volume']} @ ${position['entry']:,.2f} "
                      f"({out.get('unrealized_pct', 0):+.2f}%)")
        else:
            status = "no position, waiting for SMA cross up"
        notify(f"📊 {pair_arg} ${price:,.2f} | SMA{fast} {out['sma_fast']:,.2f} vs "
               f"SMA{slow} {out['sma_slow']:,.2f} | {status} [{out['mode']}]")

    return out


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        secret = os.environ.get("CRON_SECRET")
        if secret and self.headers.get("Authorization") != f"Bearer {secret}":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error": "unauthorized"}')
            return
        try:
            result = run_tick()
            status = 200
        except Exception as e:
            result = {"error": str(e)}
            status = 500
            notify(f"⚠️ Kraken bot tick failed: {e}")
        body = json.dumps(result, indent=2).encode()
        print(body.decode())  # goes to Vercel function logs
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)
