"""
Read-only status endpoint for the dashboard: GET /api/status.

Reports what the deployed bot sees - price, the two SMAs, where the next
trade would trigger, whether a position is open - plus daily history for a
chart. It NEVER trades and NEVER writes state: no private Kraken call, no
save_position(). Reading the position pulls the Blob file into this
function's own /tmp scratch copy, exactly like a tick's first step, and
pushes nothing back.

Public on purpose, so the dashboard can read it without a secret embedded in
the page. It therefore exposes no balances, volumes or order ids - only
market data, the configured rules, and the entry price of an open position.
Responses are CDN-cached for 60 s so repeated loads do not hammer Kraken.

Reads the same env vars as api/tick.py (PAIR, SMA_FAST, SMA_SLOW,
ENTER_ON_TREND, LIVE, VALIDATE, HEADS_UP_PCT) with the same defaults.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_HERE, ".."))
sys.path.append(_HERE)
from kraken_bot import KrakenClient, sma, crossover_signal, next_trade  # noqa: E402
from state_store import load_position  # noqa: E402

HISTORY_DAYS = 180
DAY = 86400


def config(env=None):
    env = os.environ if env is None else env
    live = (env.get("LIVE") or "").lower() == "true"
    validate = not live and (env.get("VALIDATE") or "").lower() == "true"
    return {
        "pair": env.get("PAIR") or "ETH/USD",
        "fast": int(env.get("SMA_FAST") or 20),
        "slow": int(env.get("SMA_SLOW") or 30),
        "enter_on_trend": (env.get("ENTER_ON_TREND") or "true").lower() != "false",
        "heads_up_pct": float(env.get("HEADS_UP_PCT") or 3),
        "mode": "live" if live else ("validate" if validate else "dry-run"),
    }


def _day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def tick_module_check():
    """Whether api/tick.py imports cleanly on this deployment.

    An import error in the trading function fails before its handler runs,
    so it sends no Telegram alert - the heartbeat simply stops. This makes
    that class of breakage visible on the dashboard as well.
    """
    try:
        import tick  # noqa: F401
        return "ok"
    except Exception as e:  # pragma: no cover - depends on the deployment
        return f"import failed: {e}"


def build_status(client, load_position_fn, cfg, now=None):
    """Assemble the status payload. Pure apart from the two injected readers."""
    now = now or datetime.now(timezone.utc)
    fast, slow = cfg["fast"], cfg["slow"]

    pair = client.resolve_pair(cfg["pair"])
    candles = client.ohlc_candles(pair["name"], 1440)
    price = client.ticker_price(pair["name"])
    times = [t for t, _ in candles]
    closes = [c for _, c in candles]

    sma_fast, sma_slow = sma(closes, fast), sma(closes, slow)
    out = {
        "generated_at": now.isoformat(),
        "pair": cfg["pair"],
        "mode": cfg["mode"],
        "rules": {"sma_fast": fast, "sma_slow": slow, "candle": "1d",
                  "enter_on_trend": cfg["enter_on_trend"],
                  "heads_up_pct": cfg["heads_up_pct"]},
        "price": price,
        "sma_fast": round(sma_fast, 2) if sma_fast is not None else None,
        "sma_slow": round(sma_slow, 2) if sma_slow is not None else None,
        "trend": (None if sma_fast is None or sma_slow is None
                  else "up" if sma_fast > sma_slow else "down"),
        "last_closed_candle": _day(times[-1]) if times else None,
        # The forming candle opened when the last closed one ended, and closes
        # a day later; the next tick runs 15 minutes after that.
        "next_close_at": _iso(times[-1] + 2 * DAY) if times else None,
    }

    # Position: market data above stays useful even if the state read fails.
    state_key = f"kraken_bot:{pair['altname']}"
    holding = None
    try:
        position = load_position_fn(state_key)
        holding = bool(position)
        out["position"] = {"holding": holding}
        if position:
            out["position"]["entry"] = position["entry"]
            out["position"]["unrealized_pct"] = round(
                (price / position["entry"] - 1) * 100, 2)
    except Exception as e:
        out["position"] = {"holding": None, "error": str(e)}

    nt = None
    if holding is not None:
        nt = next_trade(closes, fast, slow, price, holding,
                        cfg["enter_on_trend"], cfg["heads_up_pct"])
    if nt is not None:
        r = lambda v: None if v is None else round(v, 2)  # noqa: E731
        nt = {**nt, "trigger": r(nt["trigger"]), "distance_pct": r(nt["distance_pct"])}
        # The date each horizon's cross would be acted on: the tick after the
        # Nth close from here, i.e. the last closed candle's day + N + 1.
        last_day = datetime.fromtimestamp(times[-1], timezone.utc).date()
        nt["path"] = [{**p, "by": (last_day + timedelta(days=p["days"] + 1)).isoformat()}
                      for p in nt["path"]]
    out["next_trade"] = nt

    # Daily history for the chart, with the SMA values the rules used each day.
    start = max(slow, len(closes) - HISTORY_DAYS)
    history = []
    for i in range(start, len(closes)):
        window = closes[:i + 1]
        history.append({"date": _day(times[i]), "close": closes[i],
                        "sma_fast": round(sma(window, fast), 2),
                        "sma_slow": round(sma(window, slow), 2)})
    out["history"] = history

    # Where the rule crossed inside that window: the strategy's signals, not
    # fills - the bot only acts on them while running and in the right state.
    crosses = []
    for i in range(max(start, slow), len(closes)):
        side = crossover_signal(closes[:i + 1], fast, slow)
        if side:
            crosses.append({"date": _day(times[i]), "side": side,
                            "close": closes[i]})
    out["crosses"] = crosses
    return out


def status_response():
    """(http_status, headers, body_bytes) for GET /api/status.

    Shared by this file's handler and by the dispatch in api/tick.py's
    handler: the project deploys with the Python framework preset, where the
    pyproject entrypoint (api.tick:handler) may receive every path, so
    /api/status has to be answerable from there too.
    """
    try:
        # A keyless client: even a bug here could not authenticate an order.
        body = build_status(KrakenClient(), load_position, config())
        body["checks"] = {"tick_module": tick_module_check()}
        code = 200
    except Exception as e:
        body = {"error": str(e)}
        code = 502
    headers = {"Content-Type": "application/json",
               "Cache-Control": "public, s-maxage=60" if code == 200 else "no-store"}
    return code, headers, json.dumps(body, indent=2).encode()


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        code, headers, data = status_response()
        self.send_response(code)
        for k, v in headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)
