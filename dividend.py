#!/usr/bin/env python3
"""Long-term dividend screener for DSE.

Scores companies on five years of earnings and dividends from DSE Intelligence
(stockchartbd.com), then on today's valuation, and writes reports/dividend.md.
A research shortlist for 2-5 year holding, not a buy recommendation.

The API allows 120 requests per hour, so each company's history is cached in
data/financials/ and refreshed only when older than REFRESH_DAYS.

Usage: python3 dividend.py
"""
import datetime as dt
import json
import time
import urllib.request

from screener import REPORTS, ROOT, UA, fetch, load_fundamentals, load_rows

API = "https://stockchartbd.com/api/v1.php?endpoint=financials&symbol={}"
CACHE = ROOT / "data" / "financials"
REFRESH_DAYS = 30
DELAY = 31          # seconds between API calls: stays under 120/hour
FACE_VALUE = 10.0   # dividend_percent is quoted on Tk 10 face value
MIN_VALUE_MN = 1.0  # skip shares that barely trade


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def financials(code):
    """Yearly rows (newest first), from cache when fresh."""
    f = CACHE / f"{code}.json"
    if f.exists():
        cached = json.loads(f.read_text())
        age = dt.date.today() - dt.date.fromisoformat(cached["fetched"])
        if age.days < REFRESH_DAYS:
            return cached["yearly"], False
    req = urllib.request.Request(API.format(urllib.request.quote(code)), headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            yearly = json.load(r).get("yearly") or []
    except Exception as e:
        print(f"{code}: {e}")
        return [], True
    f.write_text(json.dumps({"fetched": dt.date.today().isoformat(), "yearly": yearly}))
    return yearly, True


def score(years, price):
    """Return (score 0-100, details) from yearly rows (newest first) and today's price."""
    eps = [num(y["eps"]) for y in years]
    div = [num(y["dividend_percent"]) or 0 for y in years]
    n = len(years)
    paid = sum(d > 0 for d in div)
    profitable = sum(e is not None and e > 0 for e in eps)
    # dividend never cut year to year (newest first, so div[i] >= div[i+1])
    steady = sum(div[i] >= div[i + 1] for i in range(n - 1) if div[i + 1] > 0)
    first, last = eps[-1], eps[0]
    growth = ((last / first) ** (1 / (n - 1)) - 1) * 100 if first and last and first > 0 and last > 0 and n > 1 else None
    dps = div[0] / 100 * FACE_VALUE
    yld = dps / price * 100 if price else 0
    payout = dps / last * 100 if last and last > 0 else None
    pe = price / last if last and last > 0 else None

    s = 0
    s += 25 * paid / 5                                   # dividend every year
    s += 15 * profitable / 5                             # profit every year
    s += 10 * steady / 4                                 # dividend not cut
    s += 15 * min(max(growth or 0, 0), 15) / 15          # earnings growth, capped at 15%/yr
    s += 20 * min(yld, 8) / 8                            # yield today, capped at 8%
    s += 10 if payout is not None and payout <= 80 else 0  # dividend covered by earnings
    s += 5 if pe is not None and pe <= 15 else 0         # not expensive
    return round(s), dict(paid=paid, years=n, growth=growth, yld=yld, payout=payout, pe=pe,
                          dps=dps, div_hist=list(reversed(div)))


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    fund = load_fundamentals()
    prices = {r["code"]: r for r in load_rows(fetch("/api/live/snapshot"))}

    candidates = sorted(
        c for c, f in fund.items()
        if f["category"] in ("A", "B") and f["sector"] != "Mutual Funds"
        and (num(f["eps"]) or 0) > 0 and (num(f["dividend_pct"]) or 0) > 0
        and c in prices and prices[c]["value"] >= MIN_VALUE_MN)

    rows = []
    for i, code in enumerate(candidates, 1):
        years, fetched = financials(code)
        if fetched:
            print(f"[{i}/{len(candidates)}] {code}", flush=True)
            time.sleep(DELAY)
        if len(years) < 3:
            continue
        price = prices[code]["close"] or prices[code]["ltp"]
        s, d = score(years[:5], price)
        rows.append((s, code, fund[code], price, d))
    rows.sort(key=lambda r: (-r[0], r[1]))

    def fmt(x, f="{:.1f}", none="-"):
        return none if x is None else f.format(x)

    md = [f"# DSE Long-term Dividend Screener: {dt.date.today():%d %b %Y}", "",
          "> ⚠️ ২-৫ বছর ধরে রাখার জন্য গবেষণার তালিকা, **কেনার পরামর্শ না**। "
          "কেনার আগে কোম্পানির সর্বশেষ রিপোর্ট আর খবর দেখে নাও।", "",
          "## স্কোর কীভাবে (১০০-র মধ্যে)",
          "| বিষয় | পয়েন্ট |", "|---|---|",
          "| ৫ বছরের প্রতি বছর ডিভিডেন্ড | ২৫ |",
          "| ৫ বছরের প্রতি বছর লাভ | ১৫ |",
          "| ডিভিডেন্ড কখনো কমায়নি | ১০ |",
          "| EPS প্রবৃদ্ধি (বছরে ১৫% পর্যন্ত) | ১৫ |",
          "| আজকের দামে dividend yield (৮% পর্যন্ত) | ২০ |",
          "| ডিভিডেন্ড আয়ের ৮০%-এর মধ্যে (টেকসই) | ১০ |",
          "| P/E ১৫ বা কম | ৫ |", "",
          f"## সেরা ৩০টা ({len(rows)}টা কোম্পানির মধ্যে)",
          "| # | কোড | সেক্টর | স্কোর | দাম | Yield | P/E | EPS প্রবৃদ্ধি/বছর | Payout | ডিভিডেন্ড % (পুরনো → নতুন) | Health |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, (s, code, f, price, d) in enumerate(rows[:30], 1):
        hist = " → ".join(f"{x:g}" for x in d["div_hist"])
        md.append(f"| {n} | **{code}** | {f['sector']} | {s} | {price:g} | {d['yld']:.1f}% | {fmt(d['pe'])} | "
                  f"{fmt(d['growth'], '{:+.0f}%')} | {fmt(d['payout'], '{:.0f}%')} | {hist} | {f['health_band'] or '-'} |")
    md += ["",
           "**কীভাবে পড়বে:**",
           "- **Yield:** আজকের দামে কিনলে গত বছরের মতো ডিভিডেন্ড দিলে বছরে কত % পাবে",
           "- **Payout:** লাভের কত % ডিভিডেন্ড দিচ্ছে। ১০০%-এর বেশি হলে ডিভিডেন্ড কমার ঝুঁকি",
           "- **ডিভিডেন্ড %** face value (Tk 10)-এর ওপর। কিছু বছরে এতে বোনাস (স্টক) ডিভিডেন্ডও থাকতে পারে",
           "",
           "_Source: DSE Intelligence (stockchartbd.com), source dsebd.org; দাম dse.com.bd._"]
    out = REPORTS / "dividend.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
