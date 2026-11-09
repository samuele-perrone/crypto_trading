#!/usr/bin/env python3
"""
Deterministic tests for takeprofit_backtest.py. No network.

    python3 -m unittest test_takeprofit -v

What matters is that each style does what the deployed bot (or the order it
stands for) would do: when the sale happens, at what price and fee, and when
the bot buys back.
"""

import unittest

import pattern_backtest as pb
import takeprofit_backtest as tb
from pattern_backtest import DAY, HOUR
from test_pattern import T0

FEE = 0.008


def daily_path(closes, intraday_high=None):
    """Hourly candles that sit flat at each day's close. `intraday_high`
    maps a day index to a high touched in that day's 12:00 hour."""
    out = []
    for d, c in enumerate(closes):
        for h in range(24):
            t = T0 + d * DAY + h * HOUR
            hi = intraday_high.get(d, c) if intraday_high and h == 12 else c
            out.append((t, c, max(c, hi), c, c, 1.0))
    return out


def run(closes, rule_factory, intraday_high=None, fee=FEE):
    hs = daily_path(closes, intraday_high)
    candles = pb.aggregate(hs, DAY)
    rule = rule_factory(candles)
    res = pb.simulate(hs, DAY, rule, fee, T0, hs[-1][0])
    return res, rule


# 40 flat days then a steady climb: SMA20 crosses above SMA30 on the climb.
CLIMB = [100.0] * 40 + [100.0 * 1.01 ** i for i in range(1, 41)]


class TestStyles(unittest.TestCase):
    def test_no_take_profit_rides_the_whole_climb(self):
        res, _ = run(CLIMB, lambda cs: pb.SmaBot("", cs))
        self.assertEqual(len(res["trades"]), 1)          # liquidated at the end

    def test_tick_style_sells_at_5pct_and_buys_back_next_day(self):
        res, _ = run(CLIMB, lambda cs: tb.SmaTakeProfit(cs, 5, "tick"))
        self.assertGreater(len(res["trades"]), 3)        # sell, re-buy, sell, ...
        closed = res["trades"][:-1]
        # each take-profit closes at the first close >= +5% (1.01^5 = +5.1%)
        for t in closed:
            self.assertAlmostEqual(t, 1.01 ** 5 * (1 - FEE) ** 2 - 1, places=6)

    def test_wait_style_sits_out_the_rest_of_the_trend(self):
        res, _ = run(CLIMB, lambda cs: tb.SmaTakeProfit(cs, 5, "wait"))
        self.assertEqual(len(res["trades"]), 1)          # one take-profit, never back in
        self.assertAlmostEqual(res["trades"][0], 1.01 ** 5 * (1 - FEE) ** 2 - 1, places=6)

    def test_resting_order_fills_at_the_target_at_the_maker_fee(self):
        # the cross comes on day 40; day 45 spikes to 108 at noon and closes flat
        closes = [100.0] * 40 + [101.0, 102.0] + [102.0] * 10
        spike = {45: 108.0}
        res, _ = run(closes, lambda cs: tb.SmaTakeProfit(cs, 5, "rest"), spike)
        # bought at the cross (close 101); sold at exactly +5% inside day 45
        self.assertAlmostEqual(res["trades"][0], 1.05 * (1 - FEE) * (1 - FEE / 2) - 1, places=6)

    def test_tick_style_ignores_an_intraday_spike(self):
        """The deployed check runs once a day on the price at 00:15, so a spike
        that is gone by the close does not sell."""
        closes = [100.0] * 40 + [101.0, 102.0] + [102.0] * 10
        res, _ = run(closes, lambda cs: tb.SmaTakeProfit(cs, 5, "tick"), {45: 108.0})
        self.assertEqual(len(res["trades"]), 1)          # only the end-of-run exit


if __name__ == "__main__":
    unittest.main()
