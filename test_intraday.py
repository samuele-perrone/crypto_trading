#!/usr/bin/env python3
"""
Deterministic tests for intraday_backtest.py. No network.

    python3 -m unittest test_intraday -v

The rule is simple, so the risk is in the bookkeeping: which hour is the
entry, when a take-profit counts as hit, what happens on a day with a gap,
and that fees and compounding are applied the same way as elsewhere.
"""

import unittest

from intraday_backtest import DAY, HOUR, daily_closes, day_trades, stats

D0 = 1_700_006_400 - 1_700_006_400 % DAY   # a UTC midnight
FEE = 0.0026


def flat_day(day, price=100.0, overrides=None):
    """24 hourly candles at a flat price; overrides {hour: (o, h, l, c)}."""
    out = {day + h * HOUR: (price, price, price, price) for h in range(24)}
    for h, c in (overrides or {}).items():
        out[day + h * HOUR] = c
    return out


class TestDayTrades(unittest.TestCase):
    def test_take_profit_fills_at_target(self):
        c = flat_day(D0, overrides={10: (100, 101.5, 99, 100)})
        [(day, m, hit)] = day_trades(c, 0.01, FEE)
        self.assertEqual(day, D0)
        self.assertTrue(hit)
        self.assertAlmostEqual(m, 1.01 * (1 - FEE) ** 2)

    def test_entry_is_the_buy_hour_open(self):
        c = flat_day(D0, overrides={8: (200, 200, 200, 100)})
        [(_d, m, _h)] = day_trades(c, None, 0.0)
        self.assertAlmostEqual(m, 0.5)        # bought at 200, out at 100

    def test_no_hit_sells_at_the_last_hour_close(self):
        c = flat_day(D0, overrides={19: (100, 100.5, 95, 97), 20: (97, 150, 97, 150)})
        [(_d, m, hit)] = day_trades(c, 0.01, 0.0)
        self.assertFalse(hit)                 # 20:00 is after the exit
        self.assertAlmostEqual(m, 0.97)

    def test_spike_before_the_entry_does_not_count(self):
        c = flat_day(D0, overrides={7: (100, 120, 100, 100)})
        [(_d, _m, hit)] = day_trades(c, 0.01, 0.0)
        self.assertFalse(hit)

    def test_day_with_a_gap_is_skipped(self):
        c = flat_day(D0)
        del c[D0 + 12 * HOUR]
        self.assertEqual(day_trades(c, 0.01, FEE), [])

    def test_fees_make_a_flat_day_a_loss(self):
        [(_d, m, _h)] = day_trades(flat_day(D0), None, FEE)
        self.assertLess(m, 1)
        self.assertAlmostEqual(m, (1 - FEE) ** 2)

    def test_first_day_filter(self):
        c = {**flat_day(D0), **flat_day(D0 + DAY)}
        self.assertEqual([d for d, _m, _h in day_trades(c, None, 0, first_day=D0 + DAY)],
                         [D0 + DAY])


class TestStats(unittest.TestCase):
    def test_compounding_and_drawdown(self):
        s = stats([(0, 1.10, True), (1, 0.90, False), (2, 1.0, False)])
        self.assertAlmostEqual(s["return_pct"], (1.1 * 0.9 - 1) * 100)
        self.assertAlmostEqual(s["max_dd"], -10.0)
        self.assertAlmostEqual(s["win_rate"], 100 / 3)
        self.assertAlmostEqual(s["tp_hit"], 100 / 3)
        self.assertAlmostEqual(s["worst"], -10.0)

    def test_since_filter_and_empty(self):
        self.assertEqual(stats([(0, 1.1, True)], since=5), None)
        self.assertEqual(stats([(0, 0.5, False), (9, 1.2, True)], since=5)["trades"], 1)


class TestDailyCloses(unittest.TestCase):
    def test_uses_the_2300_close_and_skips_incomplete_days(self):
        c = flat_day(D0, overrides={23: (100, 100, 100, 123)})
        c.update({D0 + DAY + h * HOUR: (1, 1, 1, 1) for h in range(12)})  # half a day
        self.assertEqual(daily_closes(c), [(D0, 123)])


if __name__ == "__main__":
    unittest.main()
