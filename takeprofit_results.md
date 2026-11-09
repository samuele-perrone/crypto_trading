# Take-profit backtest (2026-11-09T07:54Z)
SMA 20/30 daily with ENTER_ON_TREND, as deployed. Fee 0.80%/side (taker); a resting take-profit exits at half that (maker). Split at 2024-11-09 as in long_results.md.

<!-- ETH: 91642 hours from 2016-05-18, 70s -->
## ETH: 2016-07-17 -> 2026-11-09 (10.3 years), 0.80%/side

| Rule | Total | CAGR | Max drawdown | Trades/yr | Win rate | Avg win / avg loss | Before 2024-11-09 | After | Years beating no take-profit |
|---|---|---|---|---|---|---|---|---|---|
| No take-profit (deployed) | +45157.0% | +80.9% | -84.0% | 6.8 | 45.7% | +52.0% / -8.6% | +22126.4% | +103.6% | - |
| +3% at the daily tick, re-buy if trend up | +558.6% | +20.1% | -82.0% | 25.9 | 76.8% | +5.5% / -12.8% | +448.4% | +20.1% | 2/11 |
| +5% at the daily tick, re-buy if trend up | +808.5% | +23.9% | -81.5% | 21.8 | 72.9% | +6.9% / -12.7% | +602.0% | +29.4% | 2/11 |
| +10% at the daily tick, re-buy if trend up | +4883.8% | +46.1% | -82.2% | 15.8 | 63.8% | +12.5% / -12.4% | +2626.2% | +82.8% | 3/11 |
| +20% at the daily tick, re-buy if trend up | +6554.9% | +50.2% | -84.3% | 11.8 | 54.9% | +18.5% / -11.4% | +4139.6% | +57.0% | 3/11 |
| +5% resting limit order, re-buy if trend up | +82.8% | +6.0% | -83.3% | 32.1 | 81.6% | +3.8% / -13.8% | +64.0% | +11.5% | 1/11 |
| +10% resting limit order, re-buy if trend up | +2485.1% | +37.1% | -86.2% | 20.2 | 71.6% | +8.5% / -13.4% | +1550.2% | +56.6% | 0/11 |
| +5% at the tick, then wait for a fresh cross | -4.6% | -0.5% | -59.8% | 6.8 | 61.4% | +6.0% / -8.7% | -29.9% | +36.0% | 4/11 |
| +10% at the tick, then wait for a fresh cross | +30.2% | +2.6% | -61.6% | 6.8 | 51.4% | +10.5% / -8.9% | -12.2% | +48.3% | 3/11 |
| Buy and hold | +17487.4% | +65.1% | -94.3% | 0.1 | 100.0% | +17487.4% / +0.0% | +24598.2% | -28.8% | 6/11 |

### ETH by calendar year (2016 and 2026 partial)

| Rule | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| No take-profit (deployed) | -3.8% | +4288.0% | -40.3% | -46.8% | +370.8% | +302.9% | -11.4% | +2.3% | +8.4% | +90.3% | -4.8% |
| +5% at the daily tick, re-buy if trend up | +0.0% | +595.1% | -57.2% | -29.9% | +249.8% | +98.7% | -27.4% | -14.9% | -14.4% | +41.4% | -16.3% |
| +5% resting limit order, re-buy if trend up | -17.8% | +397.9% | -50.9% | -40.0% | +101.7% | +60.4% | -38.7% | -16.8% | -16.5% | +25.6% | -12.4% |
| +5% at the tick, then wait for a fresh cross | -1.4% | +42.8% | -45.4% | -2.6% | +48.2% | +18.4% | +0.4% | -32.4% | -21.5% | +21.2% | +12.2% |
| +20% at the daily tick, re-buy if trend up | +0.2% | +1475.8% | -54.2% | -46.6% | +345.4% | +210.2% | -17.6% | -0.4% | +1.2% | +57.6% | -4.8% |
| Buy and hold | -32.0% | +8984.2% | -82.4% | -1.5% | +473.9% | +398.3% | -67.5% | +90.8% | +46.0% | -10.9% | -28.9% |

### ETH total return by fee

| Rule | 0.00% | 0.26% | 0.40% | 0.80% |
|---|---|---|---|---|
| No take-profit (deployed) | +139232.2% | +96674.8% | +79398.5% | +45157.0% |
| +3% at the daily tick, re-buy if trend up | +47915.7% | +11857.0% | +5547.7% | +558.6% |
| +5% at the daily tick, re-buy if trend up | +33634.4% | +10354.1% | +5456.2% | +808.5% |
| +10% at the daily tick, re-buy if trend up | +68253.3% | +29153.1% | +18405.6% | +4883.8% |
| +20% at the daily tick, re-buy if trend up | +47138.0% | +24927.4% | +17665.2% | +6554.9% |
| +5% resting limit order, re-buy if trend up | +12730.3% | +3133.4% | +1437.4% | +82.8% |
| +10% resting limit order, re-buy if trend up | +41485.3% | +16796.3% | +10294.3% | +2485.1% |
| +5% at the tick, then wait for a fresh cross | +193.6% | +103.9% | +67.5% | -4.6% |
| +10% at the tick, then wait for a fresh cross | +300.9% | +178.4% | +128.7% | +30.2% |
| Buy and hold | +17772.2% | +17679.4% | +17629.5% | +17487.4% |

<!-- BTC: 99051 hours from 2015-07-20, 78s -->
## BTC: 2015-09-19 -> 2026-11-09 (11.1 years), 0.80%/side

| Rule | Total | CAGR | Max drawdown | Trades/yr | Win rate | Avg win / avg loss | Before 2024-11-09 | After | Years beating no take-profit |
|---|---|---|---|---|---|---|---|---|---|
| No take-profit (deployed) | +5174.3% | +42.8% | -67.0% | 6.8 | 42.1% | +35.4% / -8.1% | +5866.5% | -11.6% | - |
| +3% at the daily tick, re-buy if trend up | -51.6% | -6.3% | -86.4% | 23.7 | 74.2% | +3.8% / -10.9% | -15.8% | -42.6% | 0/12 |
| +5% at the daily tick, re-buy if trend up | +106.7% | +6.7% | -78.6% | 19.7 | 69.4% | +5.8% / -10.8% | +199.0% | -30.9% | 1/12 |
| +10% at the daily tick, re-buy if trend up | +607.8% | +19.2% | -67.5% | 13.8 | 61.0% | +9.7% / -10.3% | +729.6% | -14.7% | 2/12 |
| +20% at the daily tick, re-buy if trend up | +1813.5% | +30.3% | -66.7% | 10.6 | 51.7% | +15.9% / -9.6% | +2117.5% | -13.7% | 3/12 |
| +5% resting limit order, re-buy if trend up | +6.3% | +0.5% | -82.8% | 26.7 | 76.5% | +3.7% / -10.8% | +49.6% | -29.0% | 1/12 |
| +10% resting limit order, re-buy if trend up | +591.4% | +19.0% | -68.3% | 16.6 | 65.9% | +8.0% / -10.9% | +744.5% | -18.1% | 2/12 |
| +5% at the tick, then wait for a fresh cross | -17.2% | -1.7% | -68.5% | 6.8 | 60.5% | +5.4% / -8.0% | -26.1% | +12.0% | 4/12 |
| +10% at the tick, then wait for a fresh cross | -30.3% | -3.2% | -80.7% | 6.8 | 47.4% | +9.1% / -8.1% | -2.7% | -28.4% | 2/12 |
| Buy and hold | +31087.6% | +67.4% | -84.2% | 0.1 | 100.0% | +31087.6% / +0.0% | +32082.9% | -3.1% | 9/12 |

### BTC by calendar year (2015 and 2026 partial)

| Rule | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| No take-profit (deployed) | +46.5% | +80.3% | +682.4% | -37.6% | +42.4% | +265.1% | +3.3% | -46.8% | +64.5% | +20.0% | -17.9% | -11.7% |
| +5% at the daily tick, re-buy if trend up | +13.1% | +34.7% | +142.4% | -37.2% | +16.0% | +140.1% | -19.4% | -48.9% | +20.1% | +1.6% | -24.9% | -15.3% |
| +5% resting limit order, re-buy if trend up | +22.7% | +21.3% | +177.1% | -44.5% | -13.8% | +80.4% | -30.9% | -44.4% | +38.4% | -9.8% | -22.1% | -20.2% |
| +5% at the tick, then wait for a fresh cross | +14.2% | +4.5% | +29.6% | -6.5% | -25.5% | +40.7% | -11.3% | -28.0% | -6.8% | -18.1% | -10.4% | +24.9% |
| +20% at the daily tick, re-buy if trend up | +24.6% | +73.6% | +356.0% | -36.9% | +36.7% | +267.7% | -7.2% | -46.8% | +44.9% | +17.8% | -17.9% | -11.7% |
| Buy and hold | +80.9% | +126.2% | +1324.2% | -73.4% | +94.1% | +304.6% | +59.4% | -64.2% | +155.8% | +120.8% | -6.3% | -15.2% |

### BTC total return by fee

| Rule | 0.00% | 0.26% | 0.40% | 0.80% |
|---|---|---|---|---|
| No take-profit (deployed) | +17781.1% | +11937.5% | +9623.3% | +5174.3% |
| +3% at the daily tick, re-buy if trend up | +3259.4% | +749.7% | +304.8% | -51.6% |
| +5% at the daily tick, re-buy if trend up | +6869.8% | +2128.4% | +1104.5% | +106.7% |
| +10% at the daily tick, re-buy if trend up | +8300.1% | +3667.5% | +2344.3% | +607.8% |
| +20% at the daily tick, re-buy if trend up | +12636.9% | +6790.2% | +4846.2% | +1813.5% |
| +5% resting limit order, re-buy if trend up | +5055.8% | +1364.6% | +642.8% | +6.3% |
| +10% resting limit order, re-buy if trend up | +8573.2% | +3720.0% | +2354.5% | +591.4% |
| +5% at the tick, then wait for a fresh cross | +173.4% | +85.0% | +49.9% | -17.2% |
| +10% at the tick, then wait for a fresh cross | +136.2% | +59.0% | +28.5% | -30.3% |
| Buy and hold | +31592.6% | +31428.0% | +31339.6% | +31087.6% |

