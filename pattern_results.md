# Pattern backtest (2026-11-08T22:16Z)
<!-- AAVE: Coinbase, 18951 hours from 2024-09-09, 22s -->
<!-- FET: Coinbase, 18950 hours from 2024-09-09, 22s -->
<!-- DOGE: Coinbase, 18951 hours from 2024-09-09, 21s -->
<!-- SHIB: Coinbase, 18951 hours from 2024-09-09, 21s -->
<!-- TRX: Binance dump, 18939 hours from 2024-09-09, 16s -->
Traceback (most recent call last):
  File "/home/runner/work/crypto_trading/crypto_trading/pattern_backtest.py", line 912, in <module>
    main()
  File "/home/runner/work/crypto_trading/crypto_trading/pattern_backtest.py", line 894, in main
    src, hourly = fetch_hourly(coin, start - WARMUP_DAYS * DAY, end, session)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/runner/work/crypto_trading/crypto_trading/pattern_backtest.py", line 224, in fetch_hourly
    got = fn(coin, start, end, s) or {}
          ^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/runner/work/crypto_trading/crypto_trading/pattern_backtest.py", line 186, in fetch_binance_dump
    out.update(got)
TypeError: 'NoneType' object is not iterable
