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
    HEADS_UP_PCT    daily report leads with "⏳ may be coming" when the
                    next trade's trigger close is within this % of the
                    price; 0 = only when already past it  (default 3)
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
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # for `import status`
from kraken_bot import (KrakenClient, sma, crossover_signal, buy_reason,  # noqa: E402
                        sell_reason, buy_volume, trade_stake, next_trade)
from state_store import (load_position, save_position,  # noqa: E402
                         state_location, is_ephemeral)

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


REPORT_PATH_DAYS = (10, 20)  # horizons quoted in the daily report


def _day_month(d):
    return f"{d.day} {d.strftime('%b')}"  # portable "18 Nov" (no %-d)


def round_next_trade(nt):
    """next_trade() with its one-day figures rounded for JSON output."""
    r = lambda v: None if v is None else round(v, 2)  # noqa: E731
    return {**nt, "trigger": r(nt["trigger"]), "distance_pct": r(nt["distance_pct"])}


def next_trade_line(nt, fast, slow, today=None):
    """The daily report's line on what it takes for the next trade.

    The bot trades at whatever the price is at the first tick after the SMA
    cross, so the line leads with the cross, not a price. When the very next
    close could do it (`near`), it names that close; otherwise it quotes the
    steady average that gets the cross by REPORT_PATH_DAYS, and whether
    today's price held flat ever does. Dates are when the 00:15 tick acts:
    a tick on day D sees closes up to D, so N more closes act on D + N.
    """
    side = nt["side"]
    word = "above" if side == "buy" else "below"
    if nt["near"] and nt["trigger"] is not None:
        return (f"Next {side}: daily close {word} ${nt['trigger']:,.2f} "
                f"({nt['distance_pct']:+.1f}% from now)")
    today = today or datetime.now(timezone.utc).date()
    line = (f"Next {side}: when SMA{fast} closes {word} SMA{slow}, at whatever "
            f"the price is then.")
    picks = [p for p in nt.get("path", [])
             if p["days"] in REPORT_PATH_DAYS and p["avg_needed"] is not None]
    if picks:
        parts = [f"by {_day_month(today + timedelta(days=p['days']))} "
                 f"averaging {word} ${p['avg_needed']:,.0f} ({p['vs_now_pct']:+.1f}%)"
                 for p in picks]
        line += " ETH gets there " + ", or ".join(parts) + "."
    flat = nt.get("days_if_flat")
    line += (f" Flat at today's price: in {flat} days." if flat
             else " Flat at today's price, it never does.")
    return line


def heads_up_text(nt):
    """Headline for the daily report when the next close could trade, else None."""
    if not nt or not nt["near"]:
        return None
    word = "above" if nt["side"] == "buy" else "below"
    return (f"⏳ {nt['side'].upper()} may be coming: a daily close {word} "
            f"${nt['trigger']:,.2f} at 00:00 UTC triggers it at the 00:15 tick")


# ---------------------------------------------------------------------------
# One strategy tick
# ---------------------------------------------------------------------------

def run_tick():
    pair_arg = os.environ.get("PAIR") or "ETH/USD"
    fast = int(os.environ.get("SMA_FAST") or 20)
    slow = int(os.environ.get("SMA_SLOW") or 30)
    usd = float(os.environ.get("USD_PER_TRADE") or 50)
    # TRADE_PCT sizes from the live USD balance instead of a fixed amount, so
    # gains compound as the account grows. 0/unset keeps the fixed stake.
    trade_pct = float(os.environ.get("TRADE_PCT") or 0)
    stop_loss = float(os.environ.get("STOP_LOSS_PCT") or 0)
    take_profit = float(os.environ.get("TAKE_PROFIT_PCT") or 0)
    # ENTER_ON_TREND (default on): when flat, buy if SMA fast is already above
    # SMA slow instead of waiting for a fresh cross up. See buy_reason().
    enter_on_trend = (os.environ.get("ENTER_ON_TREND") or "true").lower() != "false"
    live = os.environ.get("LIVE", "").lower() == "true"
    # VALIDATE sends the order to Kraken with validate=true: real auth, real
    # signing, real pair/volume checks, but nothing is ever placed. It is the
    # only way to exercise the credentials before money is at risk.
    validate = not live and os.environ.get("VALIDATE", "").lower() == "true"

    out = {
        "time": datetime.now(timezone.utc).isoformat(),
        "pair": pair_arg,
        "mode": "live" if live else ("validate" if validate else "dry-run"),
        # Echo the effective config: env values are not readable from
        # `vercel env ls`, and this is the number that decides how much money
        # moves. Without it, a mis-set trade size is invisible until it fills.
        "sizing": (f"{trade_pct:g}% of USD balance" if trade_pct
                   else f"fixed ${usd:g}"),
        "usd_per_trade": usd,      # fallback when the balance cannot be read
        "trade_pct": trade_pct,
        "sma": f"{fast}/{slow}",
        "enter_on_trend": enter_on_trend,
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
    out["state_db"] = state_location()
    if is_ephemeral():
        out["state_warning"] = ("SQLite file lives on ephemeral storage — any open "
                                "position is forgotten between ticks. Set "
                                "BLOB_READ_WRITE_TOKEN or BOT_DB_PATH.")

    def execute(side, volume, reason):
        if live:
            result = client.market_order(pair["name"], side, volume)
            out["txid"] = result.get("txid")
        elif validate:
            result = client.market_order(pair["name"], side, volume, validate=True)
            out["validated"] = result.get("descr", True)
        out["action"] = f"{side} ({reason})"
        out["volume"] = volume

    if position:
        change_pct = (price / position["entry"] - 1) * 100
        out["unrealized_pct"] = round(change_pct, 2)
        reason = sell_reason(position, price, stop_loss, take_profit, signal)
        if reason:
            execute("sell", position["volume"], reason)
            out["realized_pct"] = round(change_pct, 2)
            save_position(state_key, None)
            notify(f"🔴 SOLD {position['volume']} {pair_arg} @ ${price:,.2f} "
                   f"({reason})\nPnL: {change_pct:+.2f}% "
                   f"[{out['mode']}]")
    else:
        entry_reason = buy_reason(signal, closes, fast, slow, enter_on_trend)
        if entry_reason:
            # Size against the real balance when we can see it. A stake equal
            # to the balance always fails -- the taker fee pushes the cost
            # above it -- so this caps rather than letting the order bounce.
            balance = None
            if client.api_key and client.api_secret:
                try:
                    funds = client.balances()
                    balance = funds.get("ZUSD", funds.get("USD", 0.0))
                    out["usd_available"] = round(balance, 2)
                except Exception as e:
                    out["balance_check"] = f"unavailable: {e}"
            stake = trade_stake(usd, trade_pct, balance)
            if stake < usd:
                out["stake_capped_from"] = usd
            out["stake"] = round(stake, 2)

            volume = buy_volume(stake, price, pair["lot_decimals"])
            if volume < pair["ordermin"]:
                out["action"] = (f"buy skipped: {volume} below Kraken minimum "
                                 f"{pair['ordermin']} — raise USD_PER_TRADE or "
                                 f"fund the account")
            else:
                execute("buy", volume, entry_reason)
                save_position(state_key, {"volume": volume, "entry": price})
                notify(f"🟢 BOUGHT {volume} {pair_arg} @ ${price:,.2f} "
                       f"(~${stake:.2f}, {entry_reason}) [{out['mode']}]")

    # Look-ahead for the report: which close would trigger the next trade.
    # Informational only, computed after every decision above is final, and
    # fenced off so a bug here can never cost the trade or the heartbeat.
    nt = None
    if out["action"] == "none":
        try:
            heads_up_pct = float(os.environ.get("HEADS_UP_PCT") or 3)
            nt = next_trade(closes, fast, slow, price, bool(position),
                            enter_on_trend, heads_up_pct)
            if nt:
                out["next_trade"] = round_next_trade(nt)
        except Exception as e:
            nt = None
            out["next_trade_error"] = str(e)

    # Daily proof-of-life when nothing traded (disable with DAILY_REPORT=false)
    if out["action"] == "none" and os.environ.get("DAILY_REPORT", "true").lower() != "false":
        if position:
            status = (f"holding {position['volume']} @ ${position['entry']:,.2f} "
                      f"({out.get('unrealized_pct', 0):+.2f}%)")
        else:
            status = ("no position, waiting for SMA trend up" if enter_on_trend
                      else "no position, waiting for SMA cross up")
        report = (f"📊 {pair_arg} ${price:,.2f} | SMA{fast} {out['sma_fast']:,.2f} vs "
                  f"SMA{slow} {out['sma_slow']:,.2f} | {status} [{out['mode']}]")
        try:
            if nt:
                report += "\n" + next_trade_line(nt, fast, slow)
                headline = heads_up_text(nt)
                if headline:
                    report = headline + "\n" + report
        except Exception as e:
            out["next_trade_error"] = str(e)
        notify(report)

    return out


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

def is_status_path(path):
    """True only for the read-only status route, /api/status (query ignored)."""
    return urlsplit(path or "").path.rstrip("/") == "/api/status"


class handler(BaseHTTPRequestHandler):
    def _serve_status(self):
        # Read-only (see api/status.py), so no CRON_SECRET. Imported lazily so
        # a problem in the status code can never stop the module - and with it
        # the tick - from loading.
        try:
            import status
            code, headers, data = status.status_response()
        except Exception as e:
            code = 500
            headers = {"Content-Type": "application/json", "Cache-Control": "no-store"}
            data = json.dumps({"error": f"status unavailable: {e}"}).encode()
        self.send_response(code)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if is_status_path(self.path):
            self._serve_status()
            return
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
