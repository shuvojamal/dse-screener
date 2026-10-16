#!/usr/bin/env python3
"""Full daily price history for one DSE share, 1999 to today.

Joins two free sources:
  - data/dse_1999_2025.csv.gz: "Dhaka Stock Exchange Historical Data (1999-2025)",
    Mendeley Data, doi:10.17632/5mww8rb9td.1, CC BY 4.0 (Jan 1999 - Apr 2025)
  - DSE Intelligence (stockchartbd.com) API for Aug 2024 onwards
Where both have a date, the newer source wins.

Prices are not adjusted for bonus/rights issues, so long-term returns from
raw prices understate what a holder actually earned.

Usage: python3 longterm.py SQURPHARMA            -> writes exports/SQURPHARMA.csv
       python3 longterm.py SQURPHARMA --yearly   -> also prints a yearly summary
"""
import argparse
import csv
import gzip
import json
import urllib.request
from pathlib import Path

from screener import ROOT, UA

ARCHIVE = ROOT / "data" / "dse_1999_2025.csv.gz"
EXPORTS = ROOT / "exports"
API = "https://stockchartbd.com/api/v1.php?endpoint=history&symbol={}&limit=1000"


def archive_rows(code):
    with gzip.open(ARCHIVE, "rt", newline="") as f:
        for r in csv.DictReader(f):
            if r["Trading_Code"] == code:
                yield r["Date"], {k.lower(): float(r[k]) for k in ("Open", "High", "Low", "Close", "Volume")}


def recent_rows(code):
    url = API.format(urllib.request.quote(code))
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            data = json.load(r)
    except Exception as e:
        print(f"recent data unavailable: {e}")
        return
    for h in data.get("history") or []:
        yield h["date"], {k: h[k] for k in ("open", "high", "low", "close", "volume")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code")
    ap.add_argument("--yearly", action="store_true", help="print a yearly summary")
    args = ap.parse_args()
    code = args.code.upper()

    days = dict(archive_rows(code))
    days.update(recent_rows(code))
    if not days:
        raise SystemExit(f"{code}: no data found")

    EXPORTS.mkdir(exist_ok=True)
    out = EXPORTS / f"{code}.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "open", "high", "low", "close", "volume"])
        for d in sorted(days):
            r = days[d]
            w.writerow([d, r["open"], r["high"], r["low"], r["close"], int(r["volume"])])
    first, last = min(days), max(days)
    print(f"{out}: {len(days)} days, {first} to {last}")

    if args.yearly:
        years = {}
        for d in sorted(days):
            y = years.setdefault(d[:4], {"open": days[d]["close"], "high": 0, "low": float("inf")})
            y["close"] = days[d]["close"]
            y["high"] = max(y["high"], days[d]["high"])
            y["low"] = min(y["low"], days[d]["low"] or days[d]["close"])
        print(f"{'Year':<6}{'Close':>10}{'High':>10}{'Low':>10}{'Change':>9}")
        prev = None
        for y, v in years.items():
            base = prev if prev else v["open"]
            chg = f"{(v['close'] - base) * 100 / base:+.0f}%" if base else ""
            print(f"{y:<6}{v['close']:>10.1f}{v['high']:>10.1f}{v['low']:>10.1f}{chg:>9}")
            prev = v["close"]


if __name__ == "__main__":
    main()
