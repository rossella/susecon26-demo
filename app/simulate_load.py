#!/usr/bin/env python3
"""
simulate_load.py – fill the PersistentVolume with session cart files.

Run this inside the container to demonstrate the out-of-disk scenario:

  python simulate_load.py [--sessions N] [--size-kb K]

Each "session" writes a cart file to DATA_DIR containing a repeating payload
of size SIZE_KB kilobytes.  The script prints a progress line for every 10
sessions so you can watch the disk fill up.

To view remaining free space during the run, open the /storage-status page
in your browser.
"""

import argparse
import json
import os
import sys
import time
import uuid

DATA_DIR = os.environ.get("DATA_DIR", "/data")


def main():
    parser = argparse.ArgumentParser(description="Simulate many sessions writing cart files.")
    parser.add_argument("--sessions", type=int, default=200, help="Number of fake sessions (default: 200)")
    parser.add_argument("--size-kb", type=int, default=5, help="Size of each cart file in KB (default: 5)")
    parser.add_argument("--delay", type=float, default=0.05, help="Delay between writes in seconds (default: 0.05)")
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)

    print(f"[simulate_load] Writing {args.sessions} fake session files ({args.size_kb} KB each) to {DATA_DIR}")
    print(f"[simulate_load] Total estimated size: {args.sessions * args.size_kb} KB")
    print()

    padding = "x" * (args.size_kb * 1024 - 200)  # leave room for JSON overhead

    for i in range(1, args.sessions + 1):
        session_id = str(uuid.uuid4())
        cart = [
            {"id": 1, "name": "Geeko Plush Toy", "price": 19.99, "emoji": "🦎", "qty": 1, "_pad": padding}
        ]
        path = os.path.join(DATA_DIR, f"cart_{session_id}.json")
        try:
            with open(path, "w") as fh:
                json.dump(cart, fh)
        except OSError as exc:
            print(f"\n[simulate_load] ⛔  WRITE FAILED at session {i}: {exc}")
            print("[simulate_load] The volume is full – this is the error we wanted to demonstrate!")
            sys.exit(1)

        if i % 10 == 0 or i == args.sessions:
            stat = os.statvfs(DATA_DIR)
            free_mb = (stat.f_bavail * stat.f_frsize) / 1024 / 1024
            print(f"  Session {i:>5}/{args.sessions}  –  free space: {free_mb:.1f} MB")

        time.sleep(args.delay)

    print()
    print(f"[simulate_load] Done. {args.sessions} cart files written to {DATA_DIR}.")
    print("[simulate_load] Reload /storage-status to see the disk usage.")


if __name__ == "__main__":
    main()
