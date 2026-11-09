#!/usr/bin/env python3
"""
Deterministic tests for long_backtest.py. No network.

    python3 -m unittest test_long -v

The engine is pattern_backtest.simulate (tested in test_pattern); the risk
here is the bookkeeping on top: the split and the calendar years must chain
back to the total, or the by-year table misattributes returns.
"""

import unittest
from datetime import datetime, timezone

import long_backtest as lb
from test_pattern import path_walk

T0 = int(datetime(2021, 9, 1, tzinfo=timezone.utc).timestamp())
SPLIT = int(datetime(2022, 7, 1, tzinfo=timezone.utc).timestamp())


class TestBookkeeping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hourly = path_walk(24 * 600, seed=5, t0=T0)
        cls.r = lb.evaluate(cls.hourly, split=SPLIT, fees=(0.008, 0.0))

    def test_years_chain_to_the_total(self):
        for key in ("sma_20_30", "st_10_3", "bh"):
            total = 1.0
            for _, v in lb.yearly(self.r[key][0.008], self.r):
                total *= 1 + v
            self.assertAlmostEqual(total - 1, self.r[key][0.008]["ret"], places=9, msg=key)

    def test_split_chains_to_the_total(self):
        before, after = lb.split_returns(self.r["st_10_3"][0.008], self.r)
        self.assertAlmostEqual((1 + before) * (1 + after) - 1,
                               self.r["st_10_3"][0.008]["ret"], places=9)

    def test_years_cover_the_window(self):
        years = [y for y, _ in lb.yearly(self.r["bh"][0.0], self.r)]
        self.assertEqual(years, [2021, 2022, 2023])      # Oct 2021 -> Apr 2023

    def test_trading_starts_after_the_warmup(self):
        self.assertGreaterEqual(self.r["_start"], self.hourly[0][0] + 60 * lb.DAY)

    def test_report_renders(self):
        text = lb.report_coin("ETH", self.r)
        self.assertIn("SMA 20/30 (deployed)", text)
        self.assertIn("calendar years", text)


if __name__ == "__main__":
    unittest.main()
