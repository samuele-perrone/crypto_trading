#!/usr/bin/env python3
"""
Place one real minimum-size round trip on Kraken, to prove the parts of the
live path that validate mode cannot reach: balance sufficiency, an actual
fill, a real txid, and any account-level restriction.

    python3 smoke_trade.py            # preview only, places nothing
    python3 smoke_trade.py --yes      # places REAL orders

Buys the pair's minimum volume at market, waits for it to land, then sells the
same amount straight back. At Kraken's 0.001 ETH minimum that is roughly $2.50
of exposure for a few seconds and about 1.3 cents in fees.

Safety rails: the volume is always the exchange minimum, never a configured
trade size, and the script aborts if that minimum would cost more than
MAX_COST_USD.
"""

import argparse
import os
import sys
import time

from kraken_bot import KrakenClient

MAX_COST_USD = 10.0      # refuse to "smoke test" anything larger than this
FILL_TIMEOUT = 30        # seconds to wait for the buy to show up in balances


def eth_balance(client, asset):
    return float(client.private("Balance").get(asset, 0.0))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", default=os.environ.get("PAIR") or "ETH/USD")
    p.add_argument("--yes", action="store_true",
                   help="actually place the orders (otherwise preview only)")
    args = p.parse_args()

    client = KrakenClient(os.environ.get("KRAKEN_API_KEY"),
                          os.environ.get("KRAKEN_API_SECRET"))
    pair = client.resolve_pair(args.pair)
    price = client.ticker_price(pair["name"])
    volume = pair["ordermin"]
    cost = volume * price

    print(f"pair        : {args.pair} ({pair['name']})")
    print(f"price       : ${price:,.2f}")
    print(f"volume      : {volume} (exchange minimum)")
    print(f"cost        : ~${cost:.2f}  +  ~${cost * 0.0026 * 2:.3f} fees round trip")

    if cost > MAX_COST_USD:
        sys.exit(f"aborting: ${cost:.2f} exceeds MAX_COST_USD (${MAX_COST_USD:.2f})")

    balances = client.private("Balance")
    usd = float(balances.get("ZUSD", balances.get("USD", 0.0)))
    base = pair["base"]
    before = float(balances.get(base, 0.0))
    print(f"USD before  : ${usd:.2f}")
    print(f"{base} before : {before}")

    if usd < cost:
        sys.exit(f"aborting: ${usd:.2f} will not cover a ${cost:.2f} buy")

    if not args.yes:
        print("\npreview only - nothing placed. Re-run with --yes to trade for real.")
        return

    print("\n--- BUY ---")
    result = client.market_order(pair["name"], "buy", volume)
    buy_txid = result.get("txid")
    print(f"txid        : {buy_txid}")
    print(f"descr       : {result.get('descr')}")

    deadline = time.time() + FILL_TIMEOUT
    while time.time() < deadline:
        held = eth_balance(client, base)
        if held >= before + volume * 0.999:
            print(f"filled      : {base} balance {before} -> {held}")
            break
        time.sleep(2)
    else:
        sys.exit(f"buy did not appear in balances within {FILL_TIMEOUT}s - "
                 f"check Kraken before running the sell leg manually")

    # Sell back exactly what arrived, never more than we bought.
    held = eth_balance(client, base)
    sell_volume = min(volume, held)
    print("\n--- SELL ---")
    # Freshly bought coin is not immediately tradable. Selling at exactly the
    # exchange minimum moments after the buy was rejected with "volume minimum
    # not met" -- the settled balance was briefly under the minimum even though
    # Balance already reported the full amount. Retry until it settles.
    for attempt in range(6):
        try:
            result = client.market_order(pair["name"], "sell", sell_volume)
            break
        except RuntimeError as e:
            if "minimum" not in str(e) and "funds" not in str(e):
                raise
            print(f"  not settled yet ({str(e)[-40:]}), retrying...")
            time.sleep(5)
    else:
        sys.exit(f"could not sell {sell_volume} {base} - sell it manually on Kraken")
    print(f"txid        : {result.get('txid')}")
    print(f"descr       : {result.get('descr')}")

    time.sleep(5)
    final = client.private("Balance")
    usd_after = float(final.get("ZUSD", final.get("USD", 0.0)))
    print(f"\nUSD  {usd:.4f} -> {usd_after:.4f}  ({usd_after - usd:+.4f}, "
          f"the round-trip cost)")
    print(f"{base} {before} -> {float(final.get(base, 0.0))}")
    print("\nlive order path verified: placement, fill, and balance movement.")


if __name__ == "__main__":
    main()
