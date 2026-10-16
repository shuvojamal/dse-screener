#!/usr/bin/env python3
"""One-time history backfill from DSE Intelligence (stockchartbd.com).

Fetches the last LIMIT daily rows for every main-board share and writes
history/YYYY-MM-DD.json files in the same format screener.py saves, so the
technical signals work without waiting weeks for history to build up.
Existing history files are never overwritten.

The API allows 120 requests per hour, so a full run takes about 3.5 hours.
Responses are cached in backfill_cache/, so an interrupted run can resume.

Usage: python3 backfill.py [--limit 60]
"""
import argparse
import json
import time
import urllib.error
import urllib.request
from collections import defaultdict

from screener import HIST, ROOT, UA, fetch, load_rows

API = "https://stockchartbd.com/api/v1.php?endpoint=history&symbol={}&limit={}"
CACHE = ROOT / "backfill_cache"
DELAY = 31  # seconds between requests: stays under 120/hour


def get_history(code, limit):
    cached = CACHE / f"{code}.json"
    if cached.exists():
        return json.loads(cached.read_text()), False
    url = API.format(urllib.request.quote(code), limit)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("rate limited, waiting 10 min")
            time.sleep(600)
            return get_history(code, limit)
        print(f"{code}: HTTP {e.code}")
        data = {"history": []}
    rows = data.get("history") or []
    cached.write_text(json.dumps(rows))
    return rows, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=60, help="trading days per share")
    args = ap.parse_args()

    CACHE.mkdir(exist_ok=True)
    HIST.mkdir(exist_ok=True)
    meta = {r["code"]: r for r in load_rows(fetch("/api/live/snapshot"))}

    by_date = defaultdict(list)
    for i, (code, m) in enumerate(sorted(meta.items()), 1):
        rows, fetched = get_history(code, args.limit)
        rows = sorted(rows, key=lambda r: r["date"])
        for prev, r in zip(rows, rows[1:]):
            ycp = prev["close"]
            if not ycp or not r["trades"]:
                continue
            by_date[r["date"]].append({
                "code": code, "ltp": r["close"], "ycp": ycp, "open": r["open"],
                "high": r["high"], "low": r["low"], "close": r["close"],
                "volume": r["volume"], "value": r["value_mn"], "trades": r["trades"],
                "percent": (r["close"] - ycp) * 100 / ycp,
                "category": m["category"], "board": m["board"],
                "sector": m["sector"], "assetType": m["assetType"],
            })
        print(f"[{i}/{len(meta)}] {code}: {len(rows)} days", flush=True)
        if fetched:
            time.sleep(DELAY)

    written = 0
    for day, rows in sorted(by_date.items()):
        f = HIST / f"{day}.json"
        if not f.exists():
            f.write_text(json.dumps(rows))
            written += 1
    print(f"wrote {written} history files")


if __name__ == "__main__":
    main()
