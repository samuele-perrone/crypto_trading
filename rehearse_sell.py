#!/usr/bin/env python3
"""
Rehearse a sell end-to-end, without waiting for the market and without
touching production state.

Seeds a position in an isolated Blob namespace, forces a take-profit, and runs
the real `run_tick()` from api/tick.py -- the same code the cron runs. Proves
the whole sell path: realized P&L, cleared state, and the push of that cleared
state to Blob.

    python3 rehearse_sell.py                # silent rehearsal
    python3 rehearse_sell.py --notify       # also send the Telegram alerts
    python3 rehearse_sell.py --validate     # round-trip the order through
                                            # Kraken with validate=true

--validate needs KRAKEN_API_KEY / KRAKEN_API_SECRET and exercises real auth,
signing and volume checks. Nothing is ever placed. Note Kraken's validate does
not check your balance, so "insufficient funds" still only appears when live.

Requires BLOB_READ_WRITE_TOKEN (load it from .env.local first).
"""

import argparse
import os
import sys
import time

# Unique per run. Blob writes are eventually consistent, and a pathname that
# was recently deleted can keep 404-ing for a while; a fresh name sidesteps
# both, and the object is deleted again at the end.
PATHNAME = f"development/rehearsal-{int(time.time())}.db"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", default=os.environ.get("PAIR") or "ETH/USD")
    p.add_argument("--gain", type=float, default=5.0,
                   help="simulated unrealized %% at rehearsal time (default 5)")
    p.add_argument("--notify", action="store_true",
                   help="send the real Telegram alerts (off by default)")
    p.add_argument("--validate", action="store_true",
                   help="send the order to Kraken with validate=true")
    args = p.parse_args()

    # Isolate before importing anything that reads these.
    os.environ["BOT_BLOB_PATHNAME"] = PATHNAME
    os.environ["BOT_DB_PATH"] = "/tmp/rehearsal.db"
    os.environ["TAKE_PROFIT_PCT"] = str(max(args.gain - 2, 0.5))
    os.environ["PAIR"] = args.pair
    os.environ.pop("LIVE", None)          # never place a real order from here
    os.environ["DAILY_REPORT"] = "false"
    os.environ["VALIDATE"] = "true" if args.validate else ""
    if not args.notify:
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        os.environ.pop("TELEGRAM_CHAT_ID", None)

    if os.environ["BOT_BLOB_PATHNAME"].startswith("production"):
        sys.exit("refusing to rehearse against production state")
    if os.path.exists(os.environ["BOT_DB_PATH"]):
        os.remove(os.environ["BOT_DB_PATH"])

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "api"))
    from kraken_bot import KrakenClient
    from state_store import (load_position, save_position, state_location,
                             delete_blob)
    from tick import run_tick

    client = KrakenClient()
    pair = client.resolve_pair(args.pair)
    price = client.ticker_price(pair["name"])
    entry = price / (1 + args.gain / 100)
    key = f"kraken_bot:{pair['altname']}"

    print(f"state      : {state_location()}")
    print(f"seeding    : entry ${entry:,.2f}, price now ${price:,.2f} "
          f"(+{args.gain:.1f}%), take-profit {os.environ['TAKE_PROFIT_PCT']}%")
    save_position(key, {"volume": round(100 / entry, pair["lot_decimals"]),
                        "entry": entry})

    # Blob is read-after-write eventually consistent. Production never reads
    # its own write (it saves at the end of a tick and reads a day later), but
    # this script does, so wait for the seed to become visible rather than
    # mistaking the lag for a broken sell path.
    for attempt in range(10):
        if load_position(key) is not None:
            break
        time.sleep(1)
    else:
        sys.exit("seed never became visible in Blob; aborting rehearsal")

    print("running the real tick...\n")
    out = run_tick()
    for k in ("mode", "action", "unrealized_pct", "realized_pct", "validated"):
        if k in out:
            print(f"  {k:<15}= {out[k]}")

    print()
    ok = True
    if not out["action"].startswith("sell"):
        print(f"  FAIL: expected a sell, got {out['action']!r}")
        ok = False
    if load_position(key) is not None:
        print("  FAIL: position still present after the sell")
        ok = False
    if "realized_pct" not in out:
        print("  FAIL: no realized_pct reported")
        ok = False
    if args.validate and "validated" not in out:
        print("  FAIL: validate mode did not reach Kraken")
        ok = False
    print("  sell path OK" if ok else "  sell path BROKEN")

    # Leave no rehearsal state behind.
    try:
        delete_blob()
        print(f"\ncleanup    : deleted {PATHNAME}")
    except Exception as e:
        print(f"\ncleanup    : could not delete {PATHNAME} ({e}) - remove it with "
              f"`vercel blob del {PATHNAME} --rw-token $BLOB_READ_WRITE_TOKEN`")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
