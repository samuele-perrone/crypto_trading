#!/usr/bin/env python3
"""
Tests for the look-ahead additions: the read-only status endpoint and the
"trade may be coming" line in the daily Telegram report. No network, no keys -
the Kraken client, state store and Telegram are all stubbed.

    python3 -m unittest test_status -v

Two properties matter most. The status endpoint must never reach anything
that trades or writes state. And the report additions must never cost the
tick its trade or its heartbeat: a bug in the look-ahead is reported in the
tick output, not raised.
"""

import os
import sys
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "api"))
import status  # noqa: E402
import tick  # noqa: E402
from kraken_bot import cross_trigger_price  # noqa: E402

DAY = 86400
T0 = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())


def ramp(start, step, n):
    return [start + step * i for i in range(n)]


# SMAs close together, one daily close away from crossing (as test_strategy).
DOWN = [100] * 45 + [99, 98, 97]   # fast below slow
UP = [100] * 45 + [101, 102, 103]  # fast above slow


class FakeClient:
    """Serves fixed candles; anything that could trade fails the test."""

    def __init__(self, closes, price, *_, **__):
        self.closes, self.price = closes, price
        self.api_key = self.api_secret = None

    def resolve_pair(self, pair):
        return {"name": "XETHZUSD", "altname": "ETHUSD", "ordermin": 0.001,
                "lot_decimals": 8}

    def ohlc_closes(self, name, interval):
        return list(self.closes)

    def ohlc_candles(self, name, interval):
        return [(T0 + i * DAY, c) for i, c in enumerate(self.closes)]

    def ticker_price(self, name):
        return self.price

    def market_order(self, *a, **k):
        raise AssertionError("market_order must not be called here")

    def balances(self):
        raise AssertionError("balances must not be called here")

    def private(self, *a, **k):
        raise AssertionError("private API must not be called here")


CFG = status.config({})


class TestStatusPayload(unittest.TestCase):
    def test_flat_downtrend(self):
        out = status.build_status(FakeClient(DOWN, DOWN[-1]), lambda k: None, CFG)
        self.assertEqual(out["trend"], "down")
        self.assertEqual(out["position"], {"holding": False})
        self.assertEqual(out["next_trade"]["side"], "buy")
        self.assertAlmostEqual(out["next_trade"]["trigger"],
                               cross_trigger_price(DOWN, 20, 30), places=2)
        self.assertEqual(out["mode"], "dry-run")

    def test_history_and_times(self):
        out = status.build_status(FakeClient(DOWN, DOWN[-1]), lambda k: None, CFG)
        self.assertEqual(len(out["history"]), len(DOWN) - 30)
        last = out["history"][-1]
        self.assertEqual(last["close"], DOWN[-1])
        self.assertEqual(last["sma_fast"], out["sma_fast"])
        self.assertEqual(out["last_closed_candle"], out["history"][-1]["date"])
        # Next close is one day after the last closed candle ended.
        last_open = T0 + (len(DOWN) - 1) * DAY
        self.assertEqual(out["next_close_at"],
                         datetime.fromtimestamp(last_open + 2 * DAY,
                                                timezone.utc).isoformat())

    def test_crosses_found_in_history(self):
        closes = ramp(100, 1, 40) + ramp(140, -3, 15) + ramp(95, 4, 30)
        out = status.build_status(FakeClient(closes, closes[-1]), lambda k: None, CFG)
        sides = [c["side"] for c in out["crosses"]]
        self.assertEqual(sides, ["sell", "buy"])

    def test_holding_reports_entry_but_not_volume(self):
        pos = {"volume": 0.0291, "entry": 120.0}
        out = status.build_status(FakeClient(UP, UP[-1]), lambda k: pos, CFG)
        self.assertEqual(out["position"]["entry"], 120.0)
        self.assertNotIn("volume", out["position"])
        self.assertNotIn("0.0291", str(out))
        self.assertEqual(out["next_trade"]["side"], "sell")

    def test_state_key_matches_the_tick(self):
        seen = []
        status.build_status(FakeClient(DOWN, DOWN[-1]),
                            lambda k: seen.append(k), CFG)
        self.assertEqual(seen, ["kraken_bot:ETHUSD"])

    def test_failed_state_read_still_returns_market_data(self):
        def boom(key):
            raise RuntimeError("blob unavailable")
        out = status.build_status(FakeClient(DOWN, DOWN[-1]), boom, CFG)
        self.assertIsNone(out["position"]["holding"])
        self.assertIn("blob unavailable", out["position"]["error"])
        self.assertIsNone(out["next_trade"])  # unknown position: no guess
        self.assertEqual(out["trend"], "down")

    def test_config_matches_tick_defaults_and_modes(self):
        self.assertEqual((CFG["pair"], CFG["fast"], CFG["slow"]), ("ETH/USD", 20, 30))
        self.assertEqual(status.config({"LIVE": "true"})["mode"], "live")
        self.assertEqual(status.config({"VALIDATE": "true"})["mode"], "validate")
        self.assertFalse(status.config({"ENTER_ON_TREND": "false"})["enter_on_trend"])

    def test_status_module_has_no_write_path(self):
        """Guard against a future edit importing the trading/writing helpers."""
        for name in ("save_position", "market_order", "trade_stake", "execute"):
            self.assertNotIn(name, vars(status))

    def test_tick_module_imports(self):
        self.assertEqual(status.tick_module_check(), "ok")


class TestReportText(unittest.TestCase):
    NT = {"side": "buy", "trigger": 2310.5, "distance_pct": 2.7,
          "on_track": False, "near": True}

    def test_heads_up_when_near(self):
        self.assertTrue(tick.heads_up_text(self.NT).startswith("⏳ BUY may be coming"))
        self.assertIn("above $2,310.50", tick.heads_up_text(self.NT))

    def test_no_heads_up_when_far(self):
        self.assertIsNone(tick.heads_up_text({**self.NT, "near": False}))
        self.assertIsNone(tick.heads_up_text(None))

    def test_far_trigger_is_flagged(self):
        """Real case 2026-11-08: buy trigger $4,875.70 with ETH at $2,223."""
        far = {**self.NT, "trigger": 4875.7, "distance_pct": 119.3, "near": False}
        self.assertTrue(tick.next_trade_line(far).endswith("not a one-day move yet"))
        self.assertNotIn("one-day", tick.next_trade_line(self.NT))

    def test_sell_wording(self):
        nt = {**self.NT, "side": "sell", "distance_pct": -1.2}
        self.assertIn("below $2,310.50", tick.heads_up_text(nt))
        self.assertIn("Next sell: daily close below", tick.next_trade_line(nt))
        self.assertIn("-1.2%", tick.next_trade_line(nt))


class TestTickReport(unittest.TestCase):
    """run_tick end to end with stubs: the heartbeat must survive anything."""

    ENV = {"LIVE": "", "VALIDATE": "", "PAIR": "ETH/USD", "SMA_FAST": "20",
           "SMA_SLOW": "30", "ENTER_ON_TREND": "", "DAILY_REPORT": "",
           "HEADS_UP_PCT": "", "TRADE_PCT": "", "USD_PER_TRADE": "50"}

    def run_tick(self, closes, price, position=None, **patches):
        sent = []
        client = FakeClient(closes, price)
        with mock.patch.dict(os.environ, self.ENV), \
                mock.patch.object(tick, "KrakenClient", lambda *a: client), \
                mock.patch.object(tick, "load_position", lambda k: position), \
                mock.patch.object(tick, "save_position", lambda k, v: None), \
                mock.patch.object(tick, "notify", sent.append):
            if patches:
                with mock.patch.multiple(tick, **patches):
                    out = tick.run_tick()
            else:
                out = tick.run_tick()
        return out, sent

    def test_far_from_trigger_keeps_plain_heartbeat_plus_next_line(self):
        trigger = cross_trigger_price(DOWN, 20, 30)
        out, sent = self.run_tick(DOWN, trigger / 1.10)
        self.assertEqual(out["action"], "none")
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0].startswith("📊 ETH/USD"))
        self.assertIn("Next buy: daily close above", sent[0])
        self.assertFalse(out["next_trade"]["near"])

    def test_near_trigger_leads_with_heads_up(self):
        trigger = cross_trigger_price(DOWN, 20, 30)
        out, sent = self.run_tick(DOWN, trigger / 1.02)
        self.assertTrue(sent[0].startswith("⏳ BUY may be coming"))
        self.assertIn("\n📊 ETH/USD", sent[0])

    def test_holding_watches_for_sell(self):
        out, sent = self.run_tick(UP, UP[-1], {"volume": 0.02, "entry": 120.0})
        self.assertEqual(out["action"], "none")
        self.assertIn("Next sell: daily close below", sent[0])

    def test_lookahead_failure_never_drops_the_heartbeat(self):
        def broken(*a, **k):
            raise ValueError("look-ahead bug")
        out, sent = self.run_tick(DOWN, DOWN[-1], next_trade=broken)
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0].startswith("📊 ETH/USD"))
        self.assertIn("look-ahead bug", out["next_trade_error"])

    def test_formatting_failure_never_drops_the_heartbeat(self):
        def broken(nt):
            raise KeyError("trigger")
        out, sent = self.run_tick(DOWN, DOWN[-1], next_trade_line=broken)
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0].startswith("📊 ETH/USD"))
        self.assertIn("next_trade_error", out)

    def test_trading_day_unchanged(self):
        """Flat in an uptrend buys exactly as before, with no look-ahead."""
        out, sent = self.run_tick(UP, UP[-1])
        self.assertTrue(out["action"].startswith("buy"))
        self.assertNotIn("next_trade", out)
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0].startswith("🟢 BOUGHT"))


class TestHandlerRouting(unittest.TestCase):
    """The deployed entrypoint may receive every path: only /api/status may
    skip the CRON_SECRET check, and it must never run a tick."""

    def test_status_path_matching(self):
        for p in ("/api/status", "/api/status/", "/api/status?x=1"):
            self.assertTrue(tick.is_status_path(p), p)
        for p in ("/api/tick", "/", "", None, "/api/status2", "/api/statusx",
                  "/api/tick?next=/api/status", "/status"):
            self.assertFalse(tick.is_status_path(p), p)

    def request(self, path, headers=None):
        """Drive tick.handler.do_GET without a socket."""
        import io
        h = tick.handler.__new__(tick.handler)
        h.path, h.headers, h.wfile = path, headers or {}, io.BytesIO()
        sent = {"code": None, "headers": {}}
        h.send_response = lambda code: sent.__setitem__("code", code)
        h.send_header = lambda k, v: sent["headers"].__setitem__(k, v)
        h.end_headers = lambda: None
        h.do_GET()
        return sent, h.wfile.getvalue()

    def no_tick(self):
        raise AssertionError("run_tick must not run")

    def test_status_route_serves_status_without_running_a_tick(self):
        fake = (200, {"Content-Type": "application/json"}, b'{"ok": true}')
        with mock.patch.object(tick, "run_tick", self.no_tick), \
                mock.patch.object(status, "status_response", lambda: fake), \
                mock.patch.dict(os.environ, {"CRON_SECRET": "s3cret"}):
            sent, body = self.request("/api/status")
        self.assertEqual(sent["code"], 200)
        self.assertEqual(body, b'{"ok": true}')

    def test_status_failure_is_contained(self):
        def broken():
            raise RuntimeError("kraken down")
        with mock.patch.object(tick, "run_tick", self.no_tick), \
                mock.patch.object(status, "status_response", broken):
            sent, body = self.request("/api/status")
        self.assertEqual(sent["code"], 500)
        self.assertIn(b"kraken down", body)

    def test_tick_route_still_requires_the_secret(self):
        with mock.patch.object(tick, "run_tick", self.no_tick), \
                mock.patch.dict(os.environ, {"CRON_SECRET": "s3cret"}):
            sent, _ = self.request("/api/tick")
            self.assertEqual(sent["code"], 401)
            sent, _ = self.request("/api/tick?next=/api/status")
            self.assertEqual(sent["code"], 401)

    def test_tick_route_runs_the_tick_with_the_secret(self):
        with mock.patch.object(tick, "run_tick", lambda: {"action": "none"}), \
                mock.patch.dict(os.environ, {"CRON_SECRET": "s3cret"}):
            sent, body = self.request("/api/tick",
                                      {"Authorization": "Bearer s3cret"})
        self.assertEqual(sent["code"], 200)
        self.assertIn(b'"action": "none"', body)


if __name__ == "__main__":
    unittest.main()
