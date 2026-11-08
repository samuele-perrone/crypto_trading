#!/usr/bin/env python3
"""
Deterministic tests for pattern_backtest.py. No network.

    python3 -m unittest test_pattern -v

The point of the backtest is a faithful port of the PHP bot, so the risk is
in two places: indicators that differ from the PHP by a seed or an off-by-one,
and bookkeeping (which candle a decision sees, where a stop fills, fees).
"""

import math
import random
import statistics
import unittest

import pattern_backtest as pb
from pattern_backtest import DAY, H4, HOUR

T0 = 1_700_006_400 - 1_700_006_400 % DAY   # a UTC midnight


def hours(prices, t0=T0, vol=1.0):
    """Flat hourly candles at each price: (t, o, h, l, c, v)."""
    return [(t0 + i * HOUR, p, p, p, p, vol) for i, p in enumerate(prices)]


def walk(n, seed=1, start=100.0):
    rnd = random.Random(seed)
    out, p = [], start
    for i in range(n):
        o = p
        p = max(1.0, p * (1 + rnd.gauss(0, 0.01)))
        hi, lo = max(o, p) * (1 + abs(rnd.gauss(0, 0.003))), min(o, p) * (1 - abs(rnd.gauss(0, 0.003)))
        out.append((T0 + i * HOUR, o, hi, lo, p, rnd.uniform(1, 10)))
    return out


def path_walk(n_hours, seed, sub=20, sigma=0.01, t0=T0):
    """Hourly bars cut from a finer random walk (a martingale: no edge), so
    highs and lows include touch-and-recover wicks as real candles do."""
    rnd, p, out = random.Random(seed), 100.0, []
    s = sigma / math.sqrt(sub)
    for i in range(n_hours):
        o = hi = lo = p
        for _ in range(sub):
            p *= math.exp(rnd.gauss(-s * s / 2, s))
            hi, lo = max(hi, p), min(lo, p)
        out.append((t0 + i * HOUR, o, hi, lo, p, 1.0))
    return out


class TestIndicators(unittest.TestCase):
    def test_ema_is_seeded_with_the_sma(self):
        e = pb.ema([1, 2, 3, 4, 5], 3)
        self.assertEqual(e[:2], [None, None])
        self.assertAlmostEqual(e[2], 2.0)              # SMA of 1, 2, 3
        self.assertAlmostEqual(e[3], 4 * 0.5 + 2.0 * 0.5)

    def test_macd_signal_starts_after_slow_plus_signal_warmup(self):
        closes = [100 + i for i in range(60)]
        _, _, m, s, h = pb.macd(closes)
        self.assertIsNone(m[24])
        self.assertIsNotNone(m[25])                    # EMA26 live at index 25
        self.assertIsNone(s[32])
        self.assertIsNotNone(s[33])                    # 9 MACD values later
        self.assertAlmostEqual(h[40], m[40] - s[40])

    def test_forming_step_matches_rebuilding_the_series(self):
        """decide_forming() extends the closed series by one EMA step. It must
        equal recomputing everything with the forming close appended - what the
        PHP did every 30 minutes."""
        closes = [c[4] for c in pb.aggregate(walk(2000), H4)]
        nxt = closes[-1] * 1.013
        full_ef, full_es, full_m, full_s, full_h = pb.macd(closes + [nxt])
        ef, es, _m, s, _h = pb.macd(closes)
        m = pb.step(ef[-1], nxt, 12) - pb.step(es[-1], nxt, 26)
        self.assertAlmostEqual(m, full_m[-1], places=9)
        self.assertAlmostEqual(pb.step(s[-1], m, 9), full_s[-1], places=9)
        self.assertAlmostEqual(pb.step(pb.ema(closes, 50)[-1], nxt, 50),
                               pb.ema(closes + [nxt], 50)[-1], places=9)

    def test_volume_profile_buys_a_strong_green_volume_candle(self):
        flat = [(T0 + i * H4, 100, 100.5, 99.5, 100, 10.0) for i in range(19)]
        strong = (T0 + 19 * H4, 100, 103.1, 99.9, 103, 40.0)
        self.assertEqual(pb.volume_profile(flat + [strong]), "BUY")
        self.assertEqual(pb.volume_profile(flat + [flat[-1]]), "HOLD")

    def test_volume_profile_sells_only_with_a_position(self):
        """The PHP called getSignal($ohlc) without the position, so its SELL
        branch could never fire in the live bot."""
        flat = [(T0 + i * H4, 100, 100.5, 99.5, 100, 10.0) for i in range(19)]
        dump = (T0 + 19 * H4, 100, 100.1, 96.9, 97, 40.0)
        self.assertEqual(pb.volume_profile(flat + [dump], holding=False), "HOLD")
        self.assertEqual(pb.volume_profile(flat + [dump], holding=True), "SELL")

    def test_heikin_ashi_runs_count_like_backtest_ha(self):
        up = [(T0 + i * H4, 100 + i, 101 + i, 99 + i, 100.8 + i, 1) for i in range(5)]
        green, red = pb.heikin_ashi_runs(up)
        # The first HA candle opens at (o+c)/2 = 100.4 and closes at the OHLC
        # average 100.2: red. From then on HA opens lag below the closes.
        self.assertEqual(green, [0, 1, 2, 3, 4])
        self.assertEqual(red, [1, 0, 0, 0, 0])

    def test_supertrend_follows_a_trend(self):
        up = [(T0 + i * H4, 100 + i, 100.5 + i, 99.5 + i, 100 + i, 1) for i in range(40)]
        down = [(T0 + (40 + i) * H4, 140 - 3 * i, 140.5 - 3 * i, 139.5 - 3 * i, 140 - 3 * i, 1)
                for i in range(20)]
        st = pb.supertrend_up(up + down)
        self.assertIsNone(st[0])
        self.assertTrue(st[39])
        self.assertFalse(st[-1])


class TestData(unittest.TestCase):
    def test_four_hour_buckets_align_to_utc(self):
        hs = hours([1, 2, 3, 4, 5, 6], t0=T0 + 2 * HOUR)
        c = pb.aggregate(hs, H4)
        self.assertEqual([x[0] for x in c], [T0, T0 + H4])
        self.assertEqual(c[0][1:5], (1, 2, 1, 2))           # 02:00 and 03:00
        self.assertEqual(c[1][4], 6)

    def test_binance_timestamps_in_ms_and_microseconds(self):
        self.assertEqual(pb.to_seconds(1_735_689_600_000), 1_735_689_600)
        self.assertEqual(pb.to_seconds(1_735_689_600_000_000), 1_735_689_600)
        csv = "open_time,open,high,low,close,volume\n1735689600000000,1,2,0.5,1.5,10,x\n"
        self.assertEqual(pb.parse_binance_csv(csv), {1_735_689_600: (1, 2, 0.5, 1.5, 10)})


class Spy(pb.Rule):
    """Buys on the first decision and records what it saw."""

    def __init__(self, candles, forming=False, trail=None, target=None, act="buy"):
        super().__init__("spy", candles, trail=trail, target=target)
        self.forming, self.seen, self.act = forming, [], act

    def decide(self, i, holding):
        self.seen.append(("closed", i, self.candles[i]))
        return None if holding else self.act

    def decide_forming(self, last, part, holding):
        self.seen.append(("forming", last, part))
        return None if holding else self.act


class TestSimulate(unittest.TestCase):
    def test_round_trip_at_a_flat_price_costs_two_fees(self):
        hs = hours([100.0] * 48)
        res = pb.simulate(hs, H4, Spy(pb.aggregate(hs, H4)), 0.004, T0, T0 + 48 * HOUR)
        self.assertAlmostEqual(res["ret"], (1 - 0.004) ** 2 - 1)
        self.assertEqual(len(res["trades"]), 1)               # liquidated at the end

    def test_closed_decision_sees_only_closed_candles(self):
        hs = hours([100.0 + i for i in range(12)])
        spy = Spy(pb.aggregate(hs, H4), act=None)
        pb.simulate(hs, H4, spy, 0.0, T0, T0 + 12 * HOUR)
        # candles 0 and 1 close at 04:00 and 08:00; candle 2 (08-12) closes at
        # the end of the data and is never decided on.
        self.assertEqual([s[1] for s in spy.seen], [0, 1])
        self.assertEqual(spy.seen[0][2][4], 103.0)            # close of 03:00 hour

    def test_forming_decision_sees_the_partial_candle(self):
        hs = hours([100.0 + i for i in range(6)], vol=2.0)
        spy = Spy(pb.aggregate(hs, H4), forming=True, act=None)
        pb.simulate(hs, H4, spy, 0.0, T0, T0 + 6 * HOUR)
        kind, last, part = spy.seen[1]                        # check at 02:00
        self.assertEqual((kind, last), ("forming", -1))
        self.assertEqual(part[1:], (100.0, 101.0, 100.0, 101.0, 4.0))
        _, last, part = spy.seen[3]                           # check at 04:00
        self.assertEqual(last, 0)                             # 00-04 just closed
        self.assertEqual(part[1:], (103.0, 103.0, 103.0, 103.0, 0.0))

    def test_trailing_stop_fills_at_the_stop_less_slip(self):
        hs = hours([100.0] * 5) + [(T0 + 5 * HOUR, 100, 110, 100, 110, 1),
                                   (T0 + 6 * HOUR, 110, 110, 105, 106, 1)]
        res = pb.simulate(hs, H4, Spy(pb.aggregate(hs, H4), trail=0.03), 0.0, T0, T0 + 7 * HOUR,
                          slip=0.001)
        self.assertAlmostEqual(res["trades"][0], 110 * 0.97 * 0.999 / 100 - 1)

    def test_stop_fills_at_the_open_after_a_gap(self):
        hs = hours([100.0] * 5) + [(T0 + 5 * HOUR, 90, 90, 89, 89, 1)]
        res = pb.simulate(hs, H4, Spy(pb.aggregate(hs, H4), trail=0.03), 0.0, T0, T0 + 6 * HOUR)
        self.assertAlmostEqual(res["trades"][0], 90 / 100 - 1)

    def test_stop_wins_when_target_and_stop_share_an_hour(self):
        hs = hours([100.0] * 5) + [(T0 + 5 * HOUR, 100, 106, 96, 100, 1)]
        res = pb.simulate(hs, H4, Spy(pb.aggregate(hs, H4), trail=0.02, target=0.05),
                          0.0, T0, T0 + 6 * HOUR)
        self.assertAlmostEqual(res["trades"][0], 98 / 100 - 1)

    def test_buy_and_hold_is_the_price_change_less_fees(self):
        hs = hours([100.0, 120.0, 150.0])
        res = pb.buy_and_hold(hs, 0.004, T0, T0 + 3 * HOUR)
        self.assertAlmostEqual(res["ret"], 1.5 * 0.996 ** 2 - 1)


class Always(pb.Rule):
    def decide(self, i, holding):
        return None if holding else "buy"


class TestStopsDoNotCreateEdge(unittest.TestCase):
    """On a path with no edge, a trailing stop must not beat buy and hold.
    Filling stops at exactly the stop price did - by ~30% over 200 days -
    because a bot that checks periodically sells after the price has already
    crossed. stop_slip() charges that overshoot."""

    def excess(self, slip_minutes):
        vals = []
        for seed in range(20):
            hs = path_walk(24 * 120, 500 + seed)
            slip = pb.stop_slip(hs, slip_minutes) if slip_minutes else 0.0
            start = T0 + 10 * DAY
            r = pb.simulate(hs, H4, Always("a", pb.aggregate(hs, H4), trail=0.03), 0.0,
                            start, hs[-1][0], slip=slip)
            b = pb.buy_and_hold(hs, 0.0, start, hs[-1][0])
            vals.append(math.log(1 + r["ret"]) - math.log(1 + b["ret"]))
        return statistics.mean(vals)

    def test_slip_removes_most_of_the_phantom_edge(self):
        # path_walk takes 20 steps an hour: one step = 3 minutes, the PHP
        # bot's check interval. Over 100 seeds the slipped excess measured
        # +0.05 +/- 0.02 (log, 120 days) against +0.30 unslipped: a small
        # residual flattery remains, noted in the report. These 20 seeds give
        # 0.41 and 0.14.
        exact, slipped = self.excess(None), self.excess(3)
        self.assertGreater(exact, 0.25)
        self.assertLess(slipped, exact / 2)


class TestWindow(unittest.TestCase):
    def test_full_history_coin_is_active_from_the_first_quarter(self):
        """Regression: the shared start was rounded down to midnight while a
        coin's own start (first candle + warm-up, rounded up) landed a day
        later, so no coin counted in the first quarter or Year 1."""
        hs = path_walk(24 * 200, seed=3, t0=T0 + 21 * HOUR)       # starts 21:00
        start = hs[0][0] + pb.WARMUP_DAYS * DAY
        r = pb.evaluate_coin(hs, 0.004, start, hs[-1][0], specs=pb.rule_specs()[:1])
        self.assertEqual(r["_start"], pb.ceil_day(start))
        self.assertTrue(r["_active"][0])


class TestEndToEnd(unittest.TestCase):
    def test_every_rule_runs_and_the_report_renders(self):
        hs = path_walk(24 * 200, seed=7)
        r = pb.evaluate_coin(hs, 0.004, T0 + 70 * DAY, hs[-1][0],
                             extra_fees=(pb.FEE_MAKER_2025, pb.FEE_TAKER_NOW))
        for key, *_ in pb.rule_specs():
            self.assertIn(key, r)
            self.assertGreater(-1, -2 + r[key][0.0]["ret"])      # finite, > -100%
        text = pb.report({"AAA": r}, {"AAA": "test"}, 0.004, r["_start"], hs[-1][0], [],
                         (pb.FEE_MAKER_2025, pb.FEE_TAKER_NOW))
        self.assertIn("## The PHP bot's live rule", text)
        self.assertIn("| AAA |", text)


if __name__ == "__main__":
    unittest.main()
