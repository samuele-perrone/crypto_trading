# Pattern backtest (2026-11-08T22:21Z)
<!-- AAVE: Coinbase, 18951 hours from 2024-09-09, 12s -->
<!-- FET: Coinbase, 18950 hours from 2024-09-09, 12s -->
<!-- DOGE: Coinbase, 18951 hours from 2024-09-09, 12s -->
<!-- SHIB: Coinbase, 18951 hours from 2024-09-09, 12s -->
<!-- TRX: Binance dump, 18939 hours from 2024-09-09, 16s -->
<!-- SPX: KuCoin, 16907 hours from 2024-12-04, 40s -->
<!-- TRUMP: KuCoin, 15823 hours from 2025-01-18, 42s -->
<!-- ETH: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- LINK: Coinbase, 18951 hours from 2024-09-09, 21s -->
<!-- XRP: Coinbase, 18951 hours from 2024-09-09, 22s -->
<!-- BCH: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- BTC: Coinbase, 18951 hours from 2024-09-09, 22s -->
<!-- ALGO: Coinbase, 18950 hours from 2024-09-09, 21s -->
<!-- XLM: Coinbase, 18951 hours from 2024-09-09, 21s -->
<!-- AVAX: Coinbase, 18951 hours from 2024-09-09, 22s -->
<!-- LTC: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- DOT: Coinbase, 18951 hours from 2024-09-09, 22s -->
<!-- UNI: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- POL: Coinbase, 18950 hours from 2024-09-09, 22s -->
<!-- SOL: Coinbase, 18951 hours from 2024-09-09, 22s -->
<!-- ADA: Coinbase, 18951 hours from 2024-09-09, 22s -->
<!-- SUI: Coinbase, 18951 hours from 2024-09-09, 23s -->

Window 2024-11-09 -> 2026-11-08 (730 days), 22 of 22 coins. Fee 0.40%/side (Kraken Pro maker, entry tier, since July 2026) unless stated; the bot paid 0.25% in 2025. Coins listed late start 60 days after their first candle.

Data: Coinbase: AAVE, FET, DOGE, SHIB, ETH, LINK, XRP, BCH, BTC, ALGO, XLM, AVAX, LTC, DOT, UNI, POL, SOL, ADA, SUI; Binance dump: TRX; KuCoin: SPX, TRUMP.

## The PHP bot's live rule

| Rule | Portfolio | Before fees | Year 1 | Year 2 | Beat buy & hold | In profit | Trades/coin/yr | Win rate | Avg trade | $60 stakes |
|---|---|---|---|---|---|---|---|---|---|---|
| PHP live rule, as deployed (forming 4h candles, 3% stop) | -93.3% | -5.8% | +0.0% | -76.1% | 0/22 | 0/22 | 178 | 21.5% | -0.8% | $-3,764 |
| PHP live rule, closed 4h candles (3% stop) | -84.4% | +9.2% | +0.0% | -63.2% | 1/22 | 0/22 | 130 | 25.0% | -0.8% | $-2,552 |
| PHP live rule, closed 4h candles, no stop | -61.9% | +29.7% | +0.0% | -53.5% | 6/22 | 1/22 | 80 | 20.4% | -0.6% | $-1,165 |
| PHP live rule, closed daily candles (3% stop) | -38.9% | +6.3% | +0.0% | -21.4% | 11/22 | 1/22 | 36 | 28.2% | -0.7% | $-676 |
| Buy and hold (benchmark) | -35.1% | -34.6% | +0.0% | -45.2% | 0/22 | 3/22 | 1 | 13.6% | -35.1% | $-464 |
| Deployed bot: SMA 20/30 daily (ENTER_ON_TREND) | -8.5% | +2.1% | +0.0% | -32.2% | 16/22 | 7/22 | 7 | 30.8% | +0.5% | $+95 |

Portfolio = equal split across the coins, no rebalancing (the mean coin return). Year 1/2 = mean coin return in each year. Beat buy & hold and In profit count coins. $60 stakes = the PHP bot's sizing: $60 a trade, P&L summed over every coin and trade.

## Other patterns from the repo

| Rule | Portfolio | Before fees | Year 1 | Year 2 | Beat buy & hold | In profit | Trades/coin/yr | Win rate | Avg trade | $60 stakes |
|---|---|---|---|---|---|---|---|---|---|---|
| MACD above signal, 4h | -75.2% | -3.2% | +0.0% | -65.7% | 2/22 | 0/22 | 86 | 26.5% | -0.6% | $-1,429 |
| MACD above signal, daily | -41.4% | -26.6% | +0.0% | -19.0% | 12/22 | 2/22 | 14 | 27.6% | -0.4% | $-141 |
| Price above EMA50, 4h | -78.8% | -11.6% | +0.0% | -67.3% | 3/22 | 0/22 | 92 | 13.2% | -0.6% | $-1,481 |
| Price above EMA50, daily | -5.2% | +17.2% | +0.0% | -15.4% | 15/22 | 9/22 | 14 | 18.5% | +0.8% | $+277 |
| chatgpt.txt spec (3 closes > EMA50, 2% stop, +5%), 4h | -99.1% | -42.5% | +0.0% | -91.7% | 0/22 | 0/22 | 385 | 24.2% | -0.9% | $-8,764 |
| chatgpt.txt spec (3 closes > EMA50, 2% stop, +5%), daily | -83.8% | -21.8% | +0.0% | -46.0% | 3/22 | 0/22 | 106 | 23.1% | -0.9% | $-2,513 |
| Volume profile alone, 4h | -98.0% | +12.3% | +0.0% | -88.5% | 0/22 | 0/22 | 259 | 21.3% | -0.7% | $-4,908 |
| Volume profile alone, daily | -54.3% | -10.9% | +0.0% | -32.2% | 7/22 | 1/22 | 43 | 22.5% | -0.7% | $-739 |
| Heikin Ashi 3 green / 2 red, 2% stop, 4h | -98.8% | -22.3% | +0.0% | -89.6% | 0/22 | 0/22 | 305 | 22.9% | -0.9% | $-6,833 |
| Heikin Ashi 3 green / 2 red, 2% stop, daily | -74.4% | -17.2% | +0.0% | -46.8% | 5/22 | 0/22 | 77 | 22.9% | -0.9% | $-1,842 |
| Supertrend 10/3, 4h | -34.0% | -0.0% | +0.0% | -44.5% | 10/22 | 4/22 | 26 | 29.0% | -0.2% | $-160 |
| Supertrend 10/3, daily | +8.7% | +16.0% | +0.0% | -16.7% | 20/22 | 9/22 | 4 | 39.1% | +3.4% | $+376 |
| Buy and hold (benchmark) | -35.1% | -34.6% | +0.0% | -45.2% | 0/22 | 3/22 | 1 | 13.6% | -35.1% | $-464 |

## By quarter: average coin return

| Rule | Nov 24 | Feb 25 | May 25 | Aug 25 | Nov 25 | Feb 26 | May 26 | Aug 26 |
|---|---|---|---|---|---|---|---|---|
| PHP rule, as deployed | +0.0% | -29.9% | -27.8% | -31.2% | -24.8% | -33.2% | -33.4% | -29.0% |
| PHP rule, closed 4h | +0.0% | -18.2% | -21.6% | -21.2% | -18.2% | -28.4% | -24.1% | -17.4% |
| Price above EMA50, daily | +0.0% | -2.0% | +11.9% | -22.1% | -11.2% | -1.7% | -11.0% | +10.6% |
| SMA 20/30 daily | +0.0% | +0.7% | +9.7% | -8.8% | -20.7% | -3.9% | -11.3% | -0.6% |
| Buy and hold | +0.0% | -2.2% | +24.7% | -27.2% | -42.6% | +10.1% | -25.0% | +13.9% |

Calendar quarters from the window start. A late-listed coin enters the averages (here and in Year 1/2) from the first quarter it traded in full.

## Fee sensitivity

| Rule | 0.00%/side | 0.25%/side | 0.80%/side | 0.40%/side |
|---|---|---|---|---|
| PHP live rule, as deployed (forming 4h candles, 3% stop) | -5.8% | -82.2% | -99.5% | -93.3% |
| Deployed bot: SMA 20/30 daily (ENTER_ON_TREND) | +2.1% | -4.7% | -18.0% | -8.5% |

The deployed SMA bot uses market orders, so it pays the taker fee (0.80% at the entry tier).

## Per coin: the PHP live rule

| Coin | Window from | As deployed | Closed 4h | Closed 4h, no stop | Trades (deployed) | Buy & hold |
|---|---|---|---|---|---|---|
| AAVE | 2024-11-09 | -97.8% | -95.0% | -80.1% | 390 | -31.9% |
| FET | 2024-11-09 | -97.4% | -92.6% | -78.9% | 401 | -90.4% |
| DOGE | 2024-11-09 | -87.6% | -79.2% | -38.8% | 338 | -66.4% |
| SHIB | 2024-11-09 | -90.7% | -89.4% | -78.5% | 320 | -77.1% |
| TRX | 2024-11-09 | -77.3% | -57.6% | -63.7% | 278 | +98.1% |
| SPX | 2025-02-03 | -99.6% | -98.1% | -84.6% | 521 | -56.7% |
| TRUMP | 2025-03-20 | -92.2% | -67.9% | -57.3% | 293 | -89.8% |
| ETH | 2024-11-09 | -90.4% | -82.4% | -72.3% | 301 | -29.3% |
| LINK | 2024-11-09 | -96.6% | -87.8% | -76.9% | 349 | -24.9% |
| XRP | 2024-11-09 | -83.1% | -56.8% | -9.8% | 333 | +99.2% |
| BCH | 2024-11-09 | -96.7% | -86.3% | -68.7% | 370 | -37.0% |
| BTC | 2024-11-09 | -87.4% | -76.3% | -75.4% | 262 | -4.0% |
| ALGO | 2024-11-09 | -97.6% | -91.2% | -63.4% | 393 | -32.1% |
| XLM | 2024-11-09 | -95.4% | -83.2% | +87.1% | 375 | +40.9% |
| AVAX | 2024-11-09 | -96.8% | -93.6% | -85.1% | 347 | -73.5% |
| LTC | 2024-11-09 | -96.1% | -89.3% | -86.6% | 359 | -31.9% |
| DOT | 2024-11-09 | -93.4% | -88.6% | -56.1% | 338 | -80.4% |
| UNI | 2024-11-09 | -95.8% | -89.7% | -71.7% | 399 | -24.9% |
| POL | 2024-11-09 | -92.1% | -82.8% | -67.8% | 308 | -77.8% |
| SOL | 2024-11-09 | -97.2% | -90.4% | -86.9% | 325 | -57.3% |
| ADA | 2024-11-09 | -95.0% | -88.9% | -68.8% | 347 | -60.9% |
| SUI | 2024-11-09 | -96.4% | -88.8% | -77.0% | 376 | -64.9% |

Assumptions that flatter the strategies: every signal order fills at the decision price (no spread, no unfilled limit orders). Stops fill below the stop by the expected overshoot of a bot checking every 3 minutes (per coin, from its hourly volatility; median 0.12%) or at the open after a gap. On simulated no-edge paths that still leaves stop rules about 0.02% a stop better off than they would really be.
