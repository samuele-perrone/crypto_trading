# Pattern backtest (2026-11-08T22:31Z)
<!-- AAVE: Coinbase, 18951 hours from 2024-09-09, 22s -->
<!-- FET: Coinbase, 18950 hours from 2024-09-09, 23s -->
<!-- DOGE: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- SHIB: Coinbase, 18951 hours from 2024-09-09, 22s -->
<!-- TRX: Binance dump, 18939 hours from 2024-09-09, 15s -->
<!-- SPX: KuCoin, 16907 hours from 2024-12-04, 45s -->
<!-- TRUMP: KuCoin, 15823 hours from 2025-01-18, 37s -->
<!-- ETH: Coinbase, 18951 hours from 2024-09-09, 24s -->
<!-- LINK: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- XRP: Coinbase, 18951 hours from 2024-09-09, 24s -->
<!-- BCH: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- BTC: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- ALGO: Coinbase, 18950 hours from 2024-09-09, 22s -->
<!-- XLM: Coinbase, 18951 hours from 2024-09-09, 24s -->
<!-- AVAX: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- LTC: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- DOT: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- UNI: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- POL: Coinbase, 18950 hours from 2024-09-09, 23s -->
<!-- SOL: Coinbase, 18951 hours from 2024-09-09, 24s -->
<!-- ADA: Coinbase, 18951 hours from 2024-09-09, 23s -->
<!-- SUI: Coinbase, 18951 hours from 2024-09-09, 24s -->

Window 2024-11-09 -> 2026-11-08 (730 days), 22 of 22 coins. Fee 0.40%/side (Kraken Pro maker, entry tier, since July 2026) unless stated; the bot paid 0.25% in 2025. Coins listed late start 60 days after their first candle.

Data: Coinbase: AAVE, FET, DOGE, SHIB, ETH, LINK, XRP, BCH, BTC, ALGO, XLM, AVAX, LTC, DOT, UNI, POL, SOL, ADA, SUI; Binance dump: TRX; KuCoin: SPX, TRUMP.

## The PHP bot's live rule

| Rule | Portfolio | Before fees | Year 1 | Year 2 | Beat buy & hold | In profit | Trades/coin/yr | Win rate | Avg trade | $60 stakes |
|---|---|---|---|---|---|---|---|---|---|---|
| PHP live rule, as deployed (forming 4h candles, 3% stop) | -93.3% | -5.8% | -74.5% | -76.0% | 0/22 | 0/22 | 178 | 21.5% | -0.8% | $-3,764 |
| PHP live rule, closed 4h candles (3% stop) | -84.4% | +9.2% | -61.4% | -62.9% | 1/22 | 0/22 | 130 | 25.0% | -0.8% | $-2,552 |
| PHP live rule, closed 4h candles, no stop | -61.9% | +29.7% | -23.3% | -52.5% | 6/22 | 1/22 | 80 | 20.4% | -0.6% | $-1,165 |
| PHP live rule, closed daily candles (3% stop) | -38.9% | +6.3% | -23.2% | -21.3% | 11/22 | 1/22 | 36 | 28.2% | -0.7% | $-676 |
| Buy and hold (benchmark) | -35.1% | -34.6% | +20.7% | -51.3% | 0/22 | 3/22 | 1 | 13.6% | -35.1% | $-464 |
| Deployed bot: SMA 20/30 daily (ENTER_ON_TREND) | -8.5% | +2.1% | +36.6% | -31.9% | 16/22 | 7/22 | 7 | 30.8% | +0.5% | $+95 |

Portfolio = equal split across the coins, no rebalancing (the mean coin return). Year 1/2 = mean coin return in each year. Beat buy & hold and In profit count coins. $60 stakes = the PHP bot's sizing: $60 a trade, P&L summed over every coin and trade.

## Other patterns from the repo

| Rule | Portfolio | Before fees | Year 1 | Year 2 | Beat buy & hold | In profit | Trades/coin/yr | Win rate | Avg trade | $60 stakes |
|---|---|---|---|---|---|---|---|---|---|---|
| MACD above signal, 4h | -75.2% | -3.2% | -29.1% | -65.5% | 2/22 | 0/22 | 86 | 26.5% | -0.6% | $-1,429 |
| MACD above signal, daily | -41.4% | -26.6% | -17.7% | -18.9% | 12/22 | 2/22 | 14 | 27.6% | -0.4% | $-141 |
| Price above EMA50, 4h | -78.8% | -11.6% | -33.9% | -66.5% | 3/22 | 0/22 | 92 | 13.2% | -0.6% | $-1,481 |
| Price above EMA50, daily | -5.2% | +17.2% | +15.0% | -15.4% | 15/22 | 9/22 | 14 | 18.5% | +0.8% | $+277 |
| chatgpt.txt spec (3 closes > EMA50, 2% stop, +5%), 4h | -99.1% | -42.5% | -95.8% | -91.6% | 0/22 | 0/22 | 385 | 24.2% | -0.9% | $-8,764 |
| chatgpt.txt spec (3 closes > EMA50, 2% stop, +5%), daily | -83.8% | -21.8% | -73.3% | -45.9% | 3/22 | 0/22 | 106 | 23.1% | -0.9% | $-2,513 |
| Volume profile alone, 4h | -98.0% | +12.3% | -84.3% | -88.2% | 0/22 | 0/22 | 259 | 21.3% | -0.7% | $-4,908 |
| Volume profile alone, daily | -54.3% | -10.9% | -28.4% | -31.9% | 7/22 | 1/22 | 43 | 22.5% | -0.7% | $-739 |
| Heikin Ashi 3 green / 2 red, 2% stop, 4h | -98.8% | -22.3% | -91.8% | -89.4% | 0/22 | 0/22 | 305 | 22.9% | -0.9% | $-6,833 |
| Heikin Ashi 3 green / 2 red, 2% stop, daily | -74.4% | -17.2% | -53.3% | -46.7% | 5/22 | 0/22 | 77 | 22.9% | -0.9% | $-1,842 |
| Supertrend 10/3, 4h | -34.0% | -0.0% | +17.7% | -43.1% | 10/22 | 4/22 | 26 | 29.0% | -0.2% | $-160 |
| Supertrend 10/3, daily | +8.7% | +16.0% | +33.9% | -16.0% | 20/22 | 9/22 | 4 | 39.1% | +3.4% | $+376 |
| Buy and hold (benchmark) | -35.1% | -34.6% | +20.7% | -51.3% | 0/22 | 3/22 | 1 | 13.6% | -35.1% | $-464 |

## Are the best daily results robust?

17 rules were tested, so the best one is partly luck. Neighbouring parameters show whether it is an effect or a fluke.

| Rule | Portfolio | Before fees | Year 1 | Year 2 | Beat buy & hold | In profit | Trades/coin/yr | Win rate | Avg trade | $60 stakes |
|---|---|---|---|---|---|---|---|---|---|---|
| Supertrend 10/3, daily | +8.7% | +16.0% | +33.9% | -16.0% | 20/22 | 9/22 | 4 | 39.1% | +3.4% | $+376 |
| Supertrend 7/3, daily | +5.1% | +12.1% | +31.6% | -17.7% | 19/22 | 11/22 | 4 | 38.1% | +3.2% | $+347 |
| Supertrend 14/3, daily | +16.0% | +23.5% | +39.6% | -13.8% | 19/22 | 12/22 | 4 | 39.0% | +4.8% | $+508 |
| Supertrend 10/2, daily | +0.8% | +13.2% | +20.0% | -12.5% | 20/22 | 10/22 | 7 | 36.9% | +2.7% | $+515 |
| Supertrend 10/4, daily | -8.6% | -4.4% | +18.2% | -21.5% | 20/22 | 10/22 | 3 | 35.2% | +1.1% | $+82 |
| Price above EMA50, daily | -5.2% | +17.2% | +15.0% | -15.4% | 15/22 | 9/22 | 14 | 18.5% | +0.8% | $+277 |
| Price above EMA30, daily | -11.0% | +17.4% | +16.9% | -21.7% | 14/22 | 5/22 | 18 | 19.2% | +0.4% | $+206 |
| Price above EMA100, daily | -49.9% | -42.6% | -41.5% | -16.4% | 12/22 | 0/22 | 9 | 13.2% | -3.6% | $-832 |
| Deployed bot: SMA 20/30 daily (ENTER_ON_TREND) | -8.5% | +2.1% | +36.6% | -31.9% | 16/22 | 7/22 | 7 | 30.8% | +0.5% | $+95 |
| Buy and hold (benchmark) | -35.1% | -34.6% | +20.7% | -51.3% | 0/22 | 3/22 | 1 | 13.6% | -35.1% | $-464 |

## By quarter: average coin return

| Rule | Nov 24 | Feb 25 | May 25 | Aug 25 | Nov 25 | Feb 26 | May 26 | Aug 26 |
|---|---|---|---|---|---|---|---|---|
| PHP rule, as deployed | -32.7% | -29.7% | -27.3% | -31.9% | -24.5% | -33.3% | -33.8% | -28.5% |
| PHP rule, closed 4h | -26.3% | -18.2% | -21.3% | -22.3% | -17.5% | -28.7% | -24.3% | -16.7% |
| Price above EMA50, daily | +47.4% | +2.1% | +9.5% | -23.6% | -11.0% | +0.1% | -12.6% | +10.4% |
| Supertrend 10/3, daily | +55.3% | +6.9% | -3.2% | -11.7% | -16.2% | +0.5% | -13.6% | +16.2% |
| SMA 20/30 daily | +39.8% | +5.5% | +6.9% | -10.3% | -20.3% | -3.2% | -12.1% | -0.3% |
| Buy and hold | +39.9% | +2.6% | +22.2% | -30.5% | -39.7% | +10.0% | -26.6% | +0.0% |

Calendar quarters from the window start. A late-listed coin enters the averages (here and in Year 1/2) from the first quarter it traded in full.

## Fee sensitivity

| Rule | 0.00%/side | 0.25%/side | 0.40%/side | 0.80%/side |
|---|---|---|---|---|
| PHP live rule, as deployed (forming 4h candles, 3% stop) | -5.8% | -82.2% | -93.3% | -99.5% |
| Deployed bot: SMA 20/30 daily (ENTER_ON_TREND) | +2.1% | -4.7% | -8.5% | -18.0% |
| Price above EMA50, daily | +17.2% | +2.6% | -5.2% | -23.3% |
| Supertrend 10/3, daily | +16.0% | +11.4% | +8.7% | +1.9% |

0.25% = the maker fee the PHP bot paid in 2025; 0.40% / 0.80% = maker / taker at Kraken's entry tier since July 2026. The deployed SMA bot uses market orders, so it pays 0.80%.

## Per coin: the PHP live rule

| Coin | Window from | As deployed | Closed 4h | Closed 4h, no stop | Trades (deployed) | Supertrend 10/3 daily | SMA 20/30 daily | Buy & hold |
|---|---|---|---|---|---|---|---|---|
| AAVE | 2024-11-09 | -97.8% | -95.0% | -80.1% | 390 | +83.7% | -20.9% | -31.9% |
| FET | 2024-11-09 | -97.4% | -92.6% | -78.9% | 401 | -39.9% | -60.7% | -90.4% |
| DOGE | 2024-11-09 | -87.6% | -79.2% | -38.8% | 338 | -10.8% | -40.3% | -66.4% |
| SHIB | 2024-11-09 | -90.7% | -89.4% | -78.5% | 320 | -52.2% | -70.4% | -77.1% |
| TRX | 2024-11-09 | -77.3% | -57.6% | -63.7% | 278 | +54.9% | +136.7% | +98.1% |
| SPX | 2025-02-03 | -99.6% | -98.1% | -84.6% | 521 | -47.5% | -70.9% | -56.7% |
| TRUMP | 2025-03-20 | -92.2% | -67.9% | -57.3% | 293 | -84.3% | -66.0% | -89.8% |
| ETH | 2024-11-09 | -90.4% | -82.4% | -72.3% | 301 | +53.6% | +124.3% | -29.3% |
| LINK | 2024-11-09 | -96.6% | -87.8% | -76.9% | 349 | -7.9% | +19.3% | -24.9% |
| XRP | 2024-11-09 | -83.1% | -56.8% | -9.8% | 333 | +180.7% | +25.7% | +99.2% |
| BCH | 2024-11-09 | -96.7% | -86.3% | -68.7% | 370 | -5.3% | -43.8% | -37.0% |
| BTC | 2024-11-09 | -87.4% | -76.3% | -75.4% | 262 | -13.4% | -1.8% | -4.0% |
| ALGO | 2024-11-09 | -97.6% | -91.2% | -63.4% | 393 | +27.6% | +71.0% | -32.1% |
| XLM | 2024-11-09 | -95.4% | -83.2% | +87.1% | 375 | +65.6% | -11.8% | +40.9% |
| AVAX | 2024-11-09 | -96.8% | -93.6% | -85.1% | 347 | +0.1% | -17.7% | -73.5% |
| LTC | 2024-11-09 | -96.1% | -89.3% | -86.6% | 359 | -24.9% | -47.3% | -31.9% |
| DOT | 2024-11-09 | -93.4% | -88.6% | -56.1% | 338 | -51.2% | -11.4% | -80.4% |
| UNI | 2024-11-09 | -95.8% | -89.7% | -71.7% | 399 | +133.5% | +31.1% | -24.9% |
| POL | 2024-11-09 | -92.1% | -82.8% | -67.8% | 308 | +0.8% | -53.6% | -77.8% |
| SOL | 2024-11-09 | -97.2% | -90.4% | -86.9% | 325 | -12.3% | +5.3% | -57.3% |
| ADA | 2024-11-09 | -95.0% | -88.9% | -68.8% | 347 | -56.1% | -17.2% | -60.9% |
| SUI | 2024-11-09 | -96.4% | -88.8% | -77.0% | 376 | -2.6% | -66.5% | -64.9% |

Assumptions that flatter the strategies: every signal order fills at the decision price (no spread, no unfilled limit orders). Stops fill below the stop by the expected overshoot of a bot checking every 3 minutes (per coin, from its hourly volatility; median 0.12%) or at the open after a gap. On simulated no-edge paths that still leaves stop rules about 0.02% a stop better off than they would really be.
