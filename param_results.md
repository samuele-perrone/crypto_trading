# Parameter walk-forward backtest (2026-11-09T08:11Z)
Daily candles, 0.80%/side. Walk-forward re-picks the best setting every 1 January using only data before it.

<!-- ETH: 91643 hours from 2016-05-18, 61s -->
## ETH: test window 2019-01-01 -> 2026-11-08 (7.9 years), 0.80%/side

| Strategy | Total | CAGR | Max drawdown | Buys/yr |
|---|---|---|---|---|
| Hindsight best SMA: SMA 10/40 (not tradable) | +4293.7% | +61.9% | -51.6% | 5.1 |
| Hindsight best Supertrend: Supertrend 5/3.5 (not tradable) | +3585.5% | +58.3% | -49.2% | 3.2 |
| Walk-forward SMA, re-picked yearly on previous 2 years | +249.8% | +17.3% | -74.6% | 6.4 |
| Walk-forward SMA, re-picked yearly on all history so far | +233.2% | +16.6% | -74.9% | 4.3 |
| Walk-forward Supertrend, re-picked yearly on previous 2 years | +1324.3% | +40.3% | -59.3% | 4.1 |
| Walk-forward Supertrend, re-picked yearly on all history so far | +1304.2% | +40.0% | -52.7% | 5.9 |
| Fixed SMA 20/30 (deployed) | +1549.6% | +42.9% | -61.6% | 7.1 |
| Fixed SMA 10/30 | +1227.1% | +39.0% | -56.6% | 6.4 |
| Fixed Supertrend 10/3 | +1432.2% | +41.6% | -49.7% | 3.9 |
| Buy and hold | +1396.6% | +41.1% | - | - |

All 61 SMA settings over the test window: median +1096.3%, worst +120.6%, best +4293.7%; 12/61 beat buy and hold. SMA 20/30 ranks 9 of 61.

All 49 Supertrend settings over the test window: median +987.2%, worst -39.3%, best +3585.5%; 14/49 beat buy and hold. Supertrend 10/3 ranks 14 of 49.

### ETH: what walk-forward picked each year (and the lookback return that won it)

| Year | SMA, previous 2 yrs | SMA, all history | Supertrend, previous 2 yrs | Supertrend, all history |
|---|---|---|---|---|
| 2019 | SMA 5/30 (+9324.8%) | SMA 15/20 (+6016.5%) | Supertrend 5/2 (+14473.7%) | Supertrend 5/2 (+12355.1%) |
| 2020 | SMA 40/75 (+58.3%) | SMA 20/150 (+7874.3%) | Supertrend 50/4 (+81.3%) | Supertrend 5/2 (+11976.4%) |
| 2021 | SMA 10/20 (+762.4%) | SMA 15/20 (+52857.9%) | Supertrend 50/4 (+594.4%) | Supertrend 5/2.5 (+49039.4%) |
| 2022 | SMA 15/40 (+2212.4%) | SMA 10/150 (+85400.2%) | Supertrend 20/2.5 (+3168.5%) | Supertrend 5/2.5 (+209922.7%) |
| 2023 | SMA 20/30 (+254.5%) | SMA 10/150 (+62284.2%) | Supertrend 20/2.5 (+374.7%) | Supertrend 5/2.5 (+130760.5%) |
| 2024 | SMA 25/30 (+20.0%) | SMA 10/150 (+82334.7%) | Supertrend 5/3.5 (+13.0%) | Supertrend 5/2.5 (+189194.9%) |
| 2025 | SMA 50/60 (+150.3%) | SMA 10/150 (+98550.5%) | Supertrend 5/4 (+111.9%) | Supertrend 5/2.5 (+193530.6%) |
| 2026 | SMA 50/60 (+136.4%) | SMA 10/150 (+107918.7%) | Supertrend 5/5 (+77.0%) | Supertrend 5/2.5 (+203972.1%) |

### ETH: every SMA setting over the test window (rows fast, columns slow)

| fast \ slow | 20 | 30 | 40 | 50 | 60 | 75 | 100 | 150 | 200 |
|---|---|---|---|---|---|---|---|---|---|
| 5 | +276.6% | +653.7% | +1237.6% | +1231.3% | +2084.1% | +547.2% | +1625.8% | +1547.9% | +1027.1% |
| 10 | +730.1% | +1227.1% | +4293.7% | +1723.5% | +1137.5% | +1723.4% | +1305.1% | +1510.8% | +1086.1% |
| 15 | +408.0% | +1096.3% | +1207.8% | +2059.5% | +1617.4% | +1473.8% | +883.1% | +1141.8% | +821.4% |
| 20 |  | +1549.6% | +953.2% | +1110.0% | +1129.6% | +880.8% | +1099.3% | +1318.5% | +577.4% |
| 25 |  | +1310.2% | +1053.0% | +968.5% | +1136.4% | +743.8% | +727.4% | +1167.2% | +348.5% |
| 30 |  |  | +658.4% | +487.4% | +1074.8% | +1026.6% | +577.5% | +1261.3% | +373.7% |
| 40 |  |  |  | +120.6% | +1290.1% | +1189.4% | +393.3% | +1252.2% | +284.7% |
| 50 |  |  |  |  | +2035.0% | +583.5% | +299.8% | +637.4% | +428.7% |

### ETH: every Supertrend setting over the test window (rows period, columns multiplier)

| period \ mult | 1.5 | 2 | 2.5 | 3 | 3.5 | 4 | 5 |
|---|---|---|---|---|---|---|---|
| 5 | +582.0% | +716.1% | +3030.0% | +2591.8% | +3585.5% | +911.1% | +772.2% |
| 7 | +751.7% | +1122.5% | +2041.4% | +1485.8% | +2096.9% | +1051.5% | +733.4% |
| 10 | +463.0% | +672.7% | +2304.1% | +1432.2% | +1610.2% | +975.5% | +450.1% |
| 14 | +337.9% | +496.3% | +1281.4% | +1352.1% | +1465.5% | +1002.1% | +990.0% |
| 20 | +132.7% | +299.4% | +1374.7% | +987.2% | +1183.1% | +846.3% | +837.9% |
| 30 | +109.5% | +26.9% | +378.3% | +1147.2% | +1004.2% | +834.1% | +1638.0% |
| 50 | +3.3% | -39.3% | +476.8% | +976.0% | +1934.1% | +1633.6% | +1491.5% |

<!-- BTC: 99052 hours from 2015-07-20, 69s -->
## BTC: test window 2019-01-01 -> 2026-11-08 (7.9 years), 0.80%/side

| Strategy | Total | CAGR | Max drawdown | Buys/yr |
|---|---|---|---|---|
| Hindsight best SMA: SMA 5/100 (not tradable) | +2807.8% | +53.6% | -43.6% | 2.5 |
| Hindsight best Supertrend: Supertrend 5/5 (not tradable) | +1960.2% | +47.0% | -52.5% | 1.9 |
| Walk-forward SMA, re-picked yearly on previous 2 years | +91.9% | +8.7% | -72.8% | 4.7 |
| Walk-forward SMA, re-picked yearly on all history so far | +1696.4% | +44.5% | -60.4% | 2.8 |
| Walk-forward Supertrend, re-picked yearly on previous 2 years | +272.2% | +18.2% | -67.2% | 4.6 |
| Walk-forward Supertrend, re-picked yearly on all history so far | +504.1% | +25.7% | -58.8% | 7.4 |
| Fixed SMA 20/30 (deployed) | +294.6% | +19.1% | -66.4% | 7.1 |
| Fixed SMA 10/30 | +416.6% | +23.3% | -70.3% | 7.4 |
| Fixed Supertrend 10/3 | +464.5% | +24.7% | -60.2% | 4.3 |
| Buy and hold | +1822.7% | +45.7% | - | - |

All 61 SMA settings over the test window: median +707.5%, worst +174.5%, best +2807.8%; 2/61 beat buy and hold. SMA 20/30 ranks 58 of 61.

All 49 Supertrend settings over the test window: median +692.2%, worst +111.1%, best +1960.2%; 1/49 beat buy and hold. Supertrend 10/3 ranks 34 of 49.

### BTC: what walk-forward picked each year (and the lookback return that won it)

| Year | SMA, previous 2 yrs | SMA, all history | Supertrend, previous 2 yrs | Supertrend, all history |
|---|---|---|---|---|
| 2019 | SMA 50/150 (+1033.0%) | SMA 40/100 (+2339.5%) | Supertrend 7/2 (+1198.1%) | Supertrend 7/2 (+3762.0%) |
| 2020 | SMA 40/100 (+65.2%) | SMA 40/100 (+6142.3%) | Supertrend 5/3.5 (+69.5%) | Supertrend 7/2 (+5457.7%) |
| 2021 | SMA 15/20 (+791.8%) | SMA 10/40 (+12734.5%) | Supertrend 20/3 (+683.5%) | Supertrend 7/2 (+21584.0%) |
| 2022 | SMA 25/40 (+632.6%) | SMA 5/100 (+25258.7%) | Supertrend 5/3.5 (+687.4%) | Supertrend 7/2 (+24194.7%) |
| 2023 | SMA 5/150 (+55.0%) | SMA 5/100 (+19743.0%) | Supertrend 14/4 (+47.3%) | Supertrend 7/2 (+14212.3%) |
| 2024 | SMA 5/200 (+86.9%) | SMA 5/100 (+31194.1%) | Supertrend 5/5 (+52.9%) | Supertrend 7/2 (+23064.7%) |
| 2025 | SMA 5/40 (+279.6%) | SMA 5/100 (+56386.1%) | Supertrend 5/2.5 (+265.1%) | Supertrend 7/2 (+36904.6%) |
| 2026 | SMA 25/100 (+105.9%) | SMA 5/100 (+57344.3%) | Supertrend 5/5 (+82.6%) | Supertrend 7/2 (+25268.1%) |

### BTC: every SMA setting over the test window (rows fast, columns slow)

| fast \ slow | 20 | 30 | 40 | 50 | 60 | 75 | 100 | 150 | 200 |
|---|---|---|---|---|---|---|---|---|---|
| 5 | +255.9% | +473.8% | +1813.6% | +1297.3% | +1603.0% | +1146.7% | +2807.8% | +2056.1% | +623.9% |
| 10 | +189.6% | +416.6% | +1556.1% | +1120.2% | +1233.2% | +1340.6% | +958.3% | +1034.5% | +760.5% |
| 15 | +174.5% | +506.9% | +1031.0% | +838.0% | +1069.4% | +1164.7% | +1093.9% | +822.2% | +710.2% |
| 20 |  | +294.6% | +531.2% | +679.9% | +1414.5% | +601.6% | +864.4% | +656.6% | +520.9% |
| 25 |  | +621.6% | +1354.5% | +940.3% | +1610.4% | +876.2% | +1578.4% | +478.9% | +475.4% |
| 30 |  |  | +617.6% | +1137.7% | +782.3% | +433.2% | +1097.1% | +455.0% | +443.3% |
| 40 |  |  |  | +620.3% | +587.2% | +611.2% | +568.8% | +479.3% | +582.1% |
| 50 |  |  |  |  | +707.5% | +511.2% | +519.9% | +374.9% | +501.2% |

### BTC: every Supertrend setting over the test window (rows period, columns multiplier)

| period \ mult | 1.5 | 2 | 2.5 | 3 | 3.5 | 4 | 5 |
|---|---|---|---|---|---|---|---|
| 5 | +350.8% | +487.5% | +1101.6% | +1227.5% | +1217.6% | +1039.0% | +1960.2% |
| 7 | +269.0% | +504.1% | +1078.3% | +961.2% | +748.8% | +1029.9% | +1640.4% |
| 10 | +183.1% | +543.3% | +867.7% | +464.5% | +919.0% | +1050.0% | +1291.3% |
| 14 | +261.9% | +427.5% | +864.7% | +414.9% | +692.2% | +1653.8% | +1007.8% |
| 20 | +130.1% | +270.3% | +658.5% | +577.8% | +571.9% | +1123.5% | +713.9% |
| 30 | +160.3% | +111.1% | +563.1% | +461.3% | +963.6% | +798.1% | +722.3% |
| 50 | +118.4% | +229.5% | +242.0% | +447.8% | +856.9% | +661.5% | +990.2% |

