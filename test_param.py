#!/usr/bin/env python3
"""
Deterministic tests for param_backtest.py. No network.

    python3 -m unittest test_param -v

param_backtest rewrites the rules as fast state machines so it can run 110
settings. These tests pin them to the deployed code: the same trades and
return as pattern_backtest.simulate running kraken_bot's own rules.
"""

import unittest

import param_backtest as pa
import pattern_backtest as pb
from pattern_backtest import DAY
from test_pattern import T0, path_walk


class TestMatchesDeployedRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hourly = path_walk(24 * 500, seed=21, sigma=0.012)
        cls.candles = pa.daily_candles(cls.hourly)
        cls.closes = [c[4] for c in cls.candles]
        cls.i0 = 60

    def reference(self, rule):
        start = self.candles[self.i0][0] + DAY             # close of candle i0
        return pb.simulate(self.hourly, DAY, rule, pa.FEE, start, self.hourly[-1][0])

    def test_sma_matches_kraken_bot_rules(self):
        for fast, slow in ((20, 30), (10, 30), (5, 50)):
            ref = self.reference(pa.lb.Sma(self.candles, fast, slow))
            ret, buys, _, _ = pa.run(self.closes, pa.sma_state(self.closes, fast, slow),
                                     self.i0, len(self.closes) - 1)
            self.assertAlmostEqual(ret, ref["ret"], places=9, msg=(fast, slow))
            self.assertEqual(buys, len(ref["trades"]), msg=(fast, slow))

    def test_supertrend_matches_the_backtest_rule(self):
        for period, mult in ((10, 3.0), (7, 2.0)):
            ref = self.reference(pb.Supertrend("", self.candles, period, mult))
            ret, buys, _, _ = pa.run(self.closes, pa.st_state(self.candles, period, mult),
                                     self.i0, len(self.closes) - 1)
            self.assertAlmostEqual(ret, ref["ret"], places=9)
            self.assertEqual(buys, len(ref["trades"]))

    def test_partial_last_day_is_dropped(self):
        hs = self.hourly[:-5]                               # last day stops at 19:00
        self.assertEqual(len(pa.daily_candles(hs)), len(self.candles) - 1)


class TestWalkForward(unittest.TestCase):
    def test_picks_use_only_earlier_data(self):
        """A pick for year Y must not change when data from Y onwards changes."""
        from datetime import datetime, timezone
        t0 = int(datetime(2016, 1, 1, tzinfo=timezone.utc).timestamp())
        hs = path_walk(24 * 365 * 4, seed=8, t0=t0)
        cut = int(datetime(2019, 1, 1, tzinfo=timezone.utc).timestamp())
        tail = [(t, o * 2, h * 2, l * 2, c * 2, v) if t >= cut else (t, o, h, l, c, v)
                for t, o, h, l, c, v in hs]            # different prices from 2019 on

        def first_pick(path):
            cs = pa.daily_candles(path)
            closes = [c[4] for c in cs]
            states = pa.grids(cs, closes)
            i_test = next(i for i, c in enumerate(cs) if c[0] >= cut)
            _, picks = pa.walk_forward(cs, closes, states, "sma", 2, i_test, len(cs) - 1)
            return picks[0]
        self.assertEqual(first_pick(hs), first_pick(tail))


if __name__ == "__main__":
    unittest.main()
