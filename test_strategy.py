#!/usr/bin/env python3
"""
Deterministic tests for the strategy rules. No network, no API keys.

    python3 -m unittest test_strategy -v
    python3 -m unittest test_strategy.TestSellReason.test_stop_loss_beats_take_profit

These cover the decisions that move money: when to buy, when to sell, and how
much. Every drill against the deployed bot proves one build once; this proves
every build in a second.
"""

import unittest

from kraken_bot import (sma, crossover_signal, sell_reason, buy_volume,
                        affordable_usd, trade_stake, TAKER_FEE)


def ramp(start, step, n):
    """n closes moving by a fixed step - a clean trend with no noise."""
    return [start + step * i for i in range(n)]


class TestSma(unittest.TestCase):
    def test_average_of_last_n(self):
        self.assertEqual(sma([1, 2, 3, 4, 5], 5), 3)
        self.assertEqual(sma([1, 2, 3, 10, 20], 2), 15)

    def test_none_when_not_enough_data(self):
        self.assertIsNone(sma([1, 2], 5))

    def test_ignores_older_candles(self):
        self.assertEqual(sma([999, 1, 1, 1], 3), 1)


class TestCrossoverSignal(unittest.TestCase):
    # A falling series that turns sharply up drags the fast SMA through the
    # slow one from below; the mirror image produces the sell. The signal is
    # read off the last two candles, so the reversal has to land exactly there
    # - with these steps the fast SMA completes the cross on the 3rd candle.
    UP = ramp(100, -1, 40) + ramp(60, 10, 3)
    DOWN = ramp(100, 1, 40) + ramp(140, -10, 3)

    def test_buy_on_cross_up(self):
        self.assertEqual(crossover_signal(self.UP, 3, 10), "buy")

    def test_sell_on_cross_down(self):
        self.assertEqual(crossover_signal(self.DOWN, 3, 10), "sell")

    def test_none_while_trend_continues(self):
        self.assertIsNone(crossover_signal(ramp(100, 1, 60), 3, 10))

    def test_none_when_not_enough_history(self):
        self.assertIsNone(crossover_signal([1, 2, 3], 3, 10))

    def test_signal_fires_once_not_repeatedly(self):
        """The cross is an edge, not a state: holding must not re-buy.

        Without this the bot would re-enter every day of an uptrend.
        """
        self.assertEqual(crossover_signal(self.UP, 3, 10), "buy")
        for extra in range(1, 6):
            closes = self.UP + ramp(self.UP[-1] + 10, 10, extra)
            self.assertIsNone(crossover_signal(closes, 3, 10),
                              f"re-fired {extra} candles after the cross")


class TestSellReason(unittest.TestCase):
    POS = {"volume": 1.0, "entry": 100.0}

    def test_holds_when_nothing_triggers(self):
        self.assertIsNone(sell_reason(self.POS, 105.0, 0, 0, None))

    def test_sells_on_cross_down(self):
        self.assertEqual(sell_reason(self.POS, 105.0, 0, 0, "sell"),
                         "SMA cross down")

    def test_stop_loss(self):
        self.assertEqual(sell_reason(self.POS, 94.0, 5, 0, None), "stop-loss")

    def test_stop_loss_not_triggered_just_above(self):
        self.assertIsNone(sell_reason(self.POS, 95.5, 5, 0, None))

    def test_stop_loss_exactly_at_threshold(self):
        self.assertEqual(sell_reason(self.POS, 95.0, 5, 0, None), "stop-loss")

    def test_take_profit(self):
        self.assertEqual(sell_reason(self.POS, 110.0, 0, 8, None),
                         "take-profit")

    def test_take_profit_exactly_at_threshold(self):
        self.assertEqual(sell_reason(self.POS, 108.0, 0, 8, None),
                         "take-profit")

    def test_stop_loss_beats_take_profit(self):
        """Both thresholds crossed in one candle: assume the worse fill."""
        self.assertEqual(sell_reason(self.POS, 90.0, 5, 8, None), "stop-loss")

    def test_zero_disables_thresholds(self):
        """0 means off - not 'sell at breakeven', which would sell everything."""
        self.assertIsNone(sell_reason(self.POS, 100.0, 0, 0, None))
        self.assertIsNone(sell_reason(self.POS, 50.0, 0, 0, None))
        self.assertIsNone(sell_reason(self.POS, 500.0, 0, 0, None))

    def test_buy_signal_never_closes_a_position(self):
        self.assertIsNone(sell_reason(self.POS, 105.0, 0, 0, "buy"))


class TestBuyVolume(unittest.TestCase):
    def test_rounds_to_lot_precision(self):
        self.assertEqual(buy_volume(100, 2000, 8), 0.05)
        self.assertEqual(buy_volume(100, 3333, 4), 0.03)

    def test_below_exchange_minimum_is_detectable(self):
        """The caller compares against ordermin; make sure it can."""
        self.assertLess(buy_volume(1, 3000, 8), 0.001)

    def test_rounding_never_exceeds_the_stake(self):
        """Rounding up would try to spend more USD than intended."""
        for usd, price in [(100, 2999.99), (50, 1234.56), (10, 987.65)]:
            self.assertLessEqual(buy_volume(usd, price, 4) * price, usd * 1.001)


class TestStakeSizing(unittest.TestCase):
    """Sizing has to survive being raised toward the whole balance."""

    def test_full_balance_stake_is_capped_below_the_balance(self):
        """Spending the balance fails: the fee pushes the cost above it."""
        balance = 65.81
        stake = trade_stake(balance, 0, balance)
        self.assertLess(stake, balance)
        self.assertLessEqual(stake * (1 + TAKER_FEE), balance)

    def test_small_stake_is_left_alone(self):
        self.assertEqual(trade_stake(20, 0, 65.81), 20)

    def test_unknown_balance_uses_the_configured_amount(self):
        """Dry-run without keys cannot see funds; the exchange enforces it."""
        self.assertEqual(trade_stake(20, 0, None), 20)

    def test_percentage_sizing_scales_with_the_balance(self):
        self.assertAlmostEqual(trade_stake(20, 50, 100), 50, places=2)
        self.assertAlmostEqual(trade_stake(20, 50, 200), 100, places=2)

    def test_percentage_sizing_still_capped_by_fees(self):
        stake = trade_stake(20, 100, 65.81)
        self.assertLessEqual(stake * (1 + TAKER_FEE), 65.81)

    def test_affordable_leaves_room_for_the_fee(self):
        for balance in (10, 65.81, 1000):
            self.assertLessEqual(affordable_usd(balance) * (1 + TAKER_FEE), balance)

    def test_stake_never_exceeds_balance_for_any_config(self):
        for configured in (5, 20, 64, 100, 10_000):
            for pct in (0, 10, 50, 100):
                stake = trade_stake(configured, pct, 65.81)
                self.assertLessEqual(stake * (1 + TAKER_FEE), 65.81,
                                     f"configured={configured} pct={pct}")


if __name__ == "__main__":
    unittest.main()
