# Day-trading backtest (2026-11-08T21:06Z)

Window 2024-11-08 -> 2026-11-07 (730 days). Day trade: buy 08:00 UTC, sell at the first +X% or at 20:00 UTC. Fee 0.26%/side, full balance compounded. 'No fees' shows the rule's edge before costs.


## BTC/USD

Data: Coinbase; 18,470 hourly candles.

| Rule | Return, full window | Return, no fees | Return, last 12 months | Trades | Win rate | Avg win / avg loss | Worst day | Hit target | Max drawdown |
|---|---|---|---|---|---|---|---|---|---|
| Day trade, take +0.5% | -98.2% | -19.7% | -89.2% | 729 | 0% | +0.00% / -0.54% | -7.4% | 70% | -98.2% |
| Day trade, take +1% | -98.3% | -24.4% | -89.9% | 729 | 49% | +0.45% / -1.51% | -7.4% | 45% | -98.3% |
| Day trade, take +2% | -98.5% | -35.1% | -89.6% | 729 | 37% | +0.97% / -1.48% | -8.2% | 20% | -98.6% |
| Day trade, take +3% | -98.3% | -25.5% | -89.4% | 729 | 36% | +1.12% / -1.48% | -8.2% | 9% | -98.4% |
| Day trade, hold to close | -97.9% | -7.2% | -88.4% | 729 | 35% | +1.28% / -1.48% | -8.2% | 0% | -98.1% |
| Bot's rule, SMA 20/30 daily | +2.4% | | -9.1% | 15 buys | | | | | -34.0% |
| Buy and hold | -1.6% | | -26.3% | 1 | | | | | -53.1% |

## ETH/USD

Data: Coinbase; 18,470 hourly candles.

| Rule | Return, full window | Return, no fees | Return, last 12 months | Trades | Win rate | Avg win / avg loss | Worst day | Hit target | Max drawdown |
|---|---|---|---|---|---|---|---|---|---|
| Day trade, take +0.5% | -98.9% | -52.1% | -89.9% | 729 | 0% | +0.00% / -0.61% | -12.1% | 77% | -98.9% |
| Day trade, take +1% | -99.1% | -59.2% | -90.5% | 729 | 60% | +0.47% / -2.27% | -12.1% | 59% | -99.1% |
| Day trade, take +2% | -98.8% | -48.5% | -91.4% | 729 | 45% | +1.24% / -2.09% | -12.1% | 35% | -98.9% |
| Day trade, take +3% | -99.2% | -62.8% | -91.6% | 729 | 39% | +1.60% / -2.06% | -12.1% | 20% | -99.2% |
| Day trade, hold to close | -98.6% | -36.2% | -88.2% | 729 | 37% | +2.01% / -2.07% | -12.1% | 0% | -98.6% |
| Bot's rule, SMA 20/30 daily | +133.3% | | -3.5% | 14 buys | | | | | -18.2% |
| Buy and hold | -24.9% | | -34.6% | 1 | | | | | -67.6% |

## SOL/USD

Data: Coinbase; 18,470 hourly candles.

| Rule | Return, full window | Return, no fees | Return, last 12 months | Trades | Win rate | Avg win / avg loss | Worst day | Hit target | Max drawdown |
|---|---|---|---|---|---|---|---|---|---|
| Day trade, take +0.5% | -98.8% | -46.1% | -87.4% | 729 | 0% | +0.00% / -0.59% | -13.7% | 81% | -98.8% |
| Day trade, take +1% | -99.3% | -71.1% | -90.9% | 729 | 63% | +0.47% / -2.58% | -13.7% | 62% | -99.4% |
| Day trade, take +2% | -99.1% | -58.8% | -92.1% | 729 | 47% | +1.34% / -2.36% | -13.7% | 41% | -99.1% |
| Day trade, take +3% | -99.2% | -62.8% | -91.7% | 729 | 41% | +1.81% / -2.32% | -13.7% | 25% | -99.2% |
| Day trade, hold to close | -99.2% | -65.0% | -91.9% | 729 | 37% | +2.34% / -2.34% | -13.7% | 0% | -99.2% |
| Bot's rule, SMA 20/30 daily | +8.9% | | -15.8% | 12 buys | | | | | -37.7% |
| Buy and hold | -55.4% | | -43.5% | 1 | | | | | -76.3% |

## XRP/USD

Data: Coinbase; 18,470 hourly candles.

| Rule | Return, full window | Return, no fees | Return, last 12 months | Trades | Win rate | Avg win / avg loss | Worst day | Hit target | Max drawdown |
|---|---|---|---|---|---|---|---|---|---|
| Day trade, take +0.5% | -98.1% | -13.7% | -91.2% | 729 | 0% | +0.00% / -0.53% | -8.7% | 80% | -98.1% |
| Day trade, take +1% | -97.8% | -1.2% | -93.5% | 729 | 64% | +0.47% / -2.21% | -15.7% | 63% | -97.9% |
| Day trade, take +2% | -97.6% | +5.8% | -93.3% | 729 | 48% | +1.29% / -2.13% | -15.7% | 40% | -98.0% |
| Day trade, take +3% | -96.9% | +39.1% | -91.2% | 729 | 43% | +1.78% / -2.12% | -15.7% | 26% | -97.6% |
| Day trade, hold to close | -89.2% | +382.8% | -89.9% | 729 | 40% | +2.63% / -2.13% | -15.7% | 0% | -95.3% |
| Bot's rule, SMA 20/30 daily | +32.2% | | -45.7% | 18 buys | | | | | -66.5% |
| Buy and hold | +108.7% | | -49.4% | 1 | | | | | -72.1% |

## ADA/USD

Data: Coinbase; 18,470 hourly candles.

| Rule | Return, full window | Return, no fees | Return, last 12 months | Trades | Win rate | Avg win / avg loss | Worst day | Hit target | Max drawdown |
|---|---|---|---|---|---|---|---|---|---|
| Day trade, take +0.5% | -98.3% | -25.2% | -90.0% | 729 | 0% | +0.00% / -0.55% | -10.6% | 83% | -98.3% |
| Day trade, take +1% | -99.0% | -54.4% | -89.4% | 729 | 68% | +0.47% / -2.93% | -11.2% | 68% | -99.0% |
| Day trade, take +2% | -99.3% | -67.1% | -93.9% | 729 | 51% | +1.34% / -2.73% | -18.0% | 45% | -99.4% |
| Day trade, take +3% | -99.2% | -64.9% | -92.8% | 729 | 45% | +1.90% / -2.67% | -18.0% | 30% | -99.4% |
| Day trade, hold to close | -99.2% | -63.8% | -91.6% | 729 | 39% | +2.67% / -2.64% | -18.0% | 0% | -99.4% |
| Bot's rule, SMA 20/30 daily | -13.7% | | -30.8% | 15 buys | | | | | -71.1% |
| Buy and hold | -59.4% | | -68.2% | 1 | | | | | -88.3% |

## DOGE/USD

Data: Coinbase; 18,470 hourly candles.

| Rule | Return, full window | Return, no fees | Return, last 12 months | Trades | Win rate | Avg win / avg loss | Worst day | Hit target | Max drawdown |
|---|---|---|---|---|---|---|---|---|---|
| Day trade, take +0.5% | -97.7% | +1.1% | -86.0% | 729 | 0% | +0.00% / -0.51% | -12.0% | 82% | -97.7% |
| Day trade, take +1% | -98.9% | -52.0% | -90.1% | 729 | 65% | +0.47% / -2.57% | -12.0% | 64% | -99.0% |
| Day trade, take +2% | -99.2% | -64.9% | -91.8% | 729 | 49% | +1.30% / -2.48% | -14.1% | 41% | -99.3% |
| Day trade, take +3% | -99.1% | -57.8% | -90.6% | 729 | 43% | +1.80% / -2.43% | -14.1% | 26% | -99.2% |
| Day trade, hold to close | -99.2% | -64.4% | -89.4% | 729 | 38% | +2.36% / -2.45% | -14.1% | 0% | -99.4% |
| Bot's rule, SMA 20/30 daily | -37.9% | | -43.2% | 14 buys | | | | | -73.1% |
| Buy and hold | -64.8% | | -59.6% | 1 | | | | | -85.2% |

## LTC/USD

Data: Coinbase; 18,470 hourly candles.

| Rule | Return, full window | Return, no fees | Return, last 12 months | Trades | Win rate | Avg win / avg loss | Worst day | Hit target | Max drawdown |
|---|---|---|---|---|---|---|---|---|---|
| Day trade, take +0.5% | -97.7% | +3.7% | -84.0% | 729 | 0% | +0.00% / -0.51% | -11.3% | 82% | -97.7% |
| Day trade, take +1% | -98.4% | -27.4% | -86.6% | 729 | 63% | +0.47% / -2.26% | -11.3% | 61% | -98.4% |
| Day trade, take +2% | -97.1% | +27.8% | -84.6% | 729 | 50% | +1.22% / -2.11% | -11.3% | 37% | -97.4% |
| Day trade, take +3% | -97.9% | -5.7% | -87.7% | 729 | 44% | +1.61% / -2.15% | -11.6% | 21% | -98.2% |
| Day trade, hold to close | -98.0% | -12.0% | -88.9% | 729 | 41% | +1.92% / -2.15% | -11.6% | 0% | -98.2% |
| Bot's rule, SMA 20/30 daily | -44.6% | | -36.6% | 18 buys | | | | | -72.6% |
| Buy and hold | -28.8% | | -51.5% | 1 | | | | | -70.2% |

## LINK/USD

Data: Coinbase; 18,470 hourly candles.

| Rule | Return, full window | Return, no fees | Return, last 12 months | Trades | Win rate | Avg win / avg loss | Worst day | Hit target | Max drawdown |
|---|---|---|---|---|---|---|---|---|---|
| Day trade, take +0.5% | -98.4% | -26.8% | -88.1% | 729 | 0% | +0.00% / -0.55% | -11.2% | 83% | -98.4% |
| Day trade, take +1% | -98.4% | -27.8% | -87.8% | 729 | 70% | +0.47% / -2.91% | -11.2% | 69% | -98.4% |
| Day trade, take +2% | -97.8% | -2.0% | -89.2% | 729 | 54% | +1.30% / -2.58% | -11.2% | 45% | -98.2% |
| Day trade, take +3% | -98.1% | -13.9% | -90.5% | 729 | 47% | +1.87% / -2.56% | -11.2% | 30% | -98.5% |
| Day trade, hold to close | -98.5% | -33.3% | -89.3% | 729 | 42% | +2.36% / -2.58% | -11.2% | 0% | -98.7% |
| Bot's rule, SMA 20/30 daily | +23.4% | | -11.7% | 12 buys | | | | | -59.0% |
| Buy and hold | -21.5% | | -30.7% | 1 | | | | | -75.4% |

## AVAX/USD

Data: Coinbase; 18,470 hourly candles.

| Rule | Return, full window | Return, no fees | Return, last 12 months | Trades | Win rate | Avg win / avg loss | Worst day | Hit target | Max drawdown |
|---|---|---|---|---|---|---|---|---|---|
| Day trade, take +0.5% | -99.1% | -61.2% | -90.0% | 729 | 0% | +0.00% / -0.63% | -11.8% | 82% | -99.1% |
| Day trade, take +1% | -99.2% | -63.5% | -90.4% | 729 | 66% | +0.47% / -2.80% | -12.7% | 65% | -99.2% |
| Day trade, take +2% | -99.4% | -73.3% | -93.6% | 729 | 50% | +1.29% / -2.65% | -12.7% | 42% | -99.5% |
| Day trade, take +3% | -99.3% | -67.0% | -92.0% | 729 | 44% | +1.84% / -2.55% | -12.7% | 29% | -99.4% |
| Day trade, hold to close | -99.4% | -75.0% | -91.6% | 729 | 39% | +2.34% / -2.54% | -12.7% | 0% | -99.5% |
| Bot's rule, SMA 20/30 daily | -14.4% | | -27.2% | 14 buys | | | | | -63.8% |
| Buy and hold | -71.6% | | -53.3% | 1 | | | | | -89.1% |

## DOT/USD

Data: Coinbase; 18,470 hourly candles.

| Rule | Return, full window | Return, no fees | Return, last 12 months | Trades | Win rate | Avg win / avg loss | Worst day | Hit target | Max drawdown |
|---|---|---|---|---|---|---|---|---|---|
| Day trade, take +0.5% | -98.3% | -23.0% | -86.0% | 729 | 0% | +0.00% / -0.54% | -10.2% | 83% | -98.3% |
| Day trade, take +1% | -98.5% | -33.7% | -89.2% | 729 | 68% | +0.47% / -2.72% | -10.2% | 67% | -98.6% |
| Day trade, take +2% | -98.7% | -40.9% | -91.7% | 729 | 51% | +1.34% / -2.52% | -10.2% | 44% | -98.8% |
| Day trade, take +3% | -99.0% | -54.4% | -93.6% | 729 | 44% | +1.82% / -2.49% | -10.2% | 27% | -99.1% |
| Day trade, hold to close | -98.7% | -40.6% | -91.0% | 729 | 40% | +2.40% / -2.45% | -10.2% | 0% | -98.9% |
| Bot's rule, SMA 20/30 daily | -8.1% | | -11.3% | 13 buys | | | | | -69.7% |
| Buy and hold | -79.4% | | -72.5% | 1 | | | | | -93.0% |

## Summary, full window, after fees

| Coin | Best day-trade variant | Its return | Bot's SMA 20/30 | Buy and hold |
|---|---|---|---|---|
| BTC | hold to close | -97.9% | +2.4% | -1.6% |
| ETH | hold to close | -98.6% | +133.3% | -24.9% |
| SOL | take +0.5% | -98.8% | +8.9% | -55.4% |
| XRP | hold to close | -89.2% | +32.2% | +108.7% |
| ADA | take +0.5% | -98.3% | -13.7% | -59.4% |
| DOGE | take +0.5% | -97.7% | -37.9% | -64.8% |
| LTC | take +2% | -97.1% | -44.6% | -28.8% |
| LINK | take +2% | -97.8% | +23.4% | -21.5% |
| AVAX | take +0.5% | -99.1% | -14.4% | -71.6% |
| DOT | take +0.5% | -98.3% | -8.1% | -79.4% |
