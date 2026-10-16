#!/usr/bin/env python3
"""DSE daily screener.

Pulls end-of-day data from the official DSE website API (dse.com.bd),
saves a daily snapshot to history/, and writes a Markdown report to reports/.
It is a research aid only: it flags shares worth a closer look, it does not
predict prices.

Usage: python3 screener.py [--snapshot saved.json] [--force]
"""
import argparse
import datetime as dt
import json
import statistics
import urllib.request
from collections import defaultdict
from pathlib import Path

BASE = "https://www.dse.com.bd"
UA = {"User-Agent": "Mozilla/5.0 (dse-screener)"}
ROOT = Path(__file__).resolve().parent
HIST = ROOT / "history"
REPORTS = ROOT / "reports"
WATCHLIST = ROOT / "watchlist.txt"

MIN_VALUE_MN = 5.0      # ignore thinly traded shares (turnover below Tk 5 mn)
VOL_SPIKE = 3.0         # volume >= 3x its recent average
MA_SHORT, MA_LONG = 5, 20
RSI_PERIOD = 14


def fetch(path):
    req = urllib.request.Request(BASE + path, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def load_rows(snap):
    cols = snap["prices"]["cols"]
    rows = [dict(zip(cols, r)) for r in snap["prices"]["rows"]]
    # Equities and mutual funds on the main board only (skip bonds)
    return [r for r in rows if r["board"] == "PUBLIC" and r["trades"] and r["ycp"]]


def trade_date(snap):
    t = snap["market"]["totals"]["tradeTime"]  # e.g. "Oct 15, 2026 at 5:26 PM"
    return dt.datetime.strptime(t.split(" at ")[0], "%b %d, %Y").date()


def load_history(upto):
    """Return {code: [rows oldest->newest]} from saved snapshots before `upto`."""
    hist = defaultdict(list)
    for f in sorted(HIST.glob("*.json")):
        if f.stem >= upto.isoformat():
            continue
        for r in json.loads(f.read_text()):
            hist[r["code"]].append(r)
    return hist


def rsi(closes, n=RSI_PERIOD):
    if len(closes) <= n:
        return None
    gains = losses = 0.0
    for a, b in zip(closes[-n - 1:-1], closes[-n:]):
        d = b - a
        gains += max(d, 0)
        losses += max(-d, 0)
    if losses == 0:
        return 100.0
    return 100 - 100 / (1 + gains / losses)


def fmt_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out) if rows else "_Kichu pawa jay nai._"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", help="use a saved snapshot JSON instead of fetching")
    ap.add_argument("--force", action="store_true", help="rebuild even if this trading day is done")
    args = ap.parse_args()

    snap = json.loads(Path(args.snapshot).read_text()) if args.snapshot else fetch("/api/live/snapshot")
    day = trade_date(snap)
    rows = load_rows(snap)
    by_code = {r["code"]: r for r in rows}

    HIST.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    if (HIST / f"{day}.json").exists() and not args.force:
        print(f"No new trading day (last: {day})")  # holiday or market closed
        return
    (HIST / f"{day}.json").write_text(json.dumps(rows))
    hist = load_history(day)
    days_of_history = len({f.stem for f in HIST.glob("*.json")})

    m = snap["market"]
    tot, br = m["totals"], m["breadth"]
    dsex = next(i for i in m["indices"] if i["key"] == "DSEX")

    liquid = [r for r in rows if r["value"] >= MIN_VALUE_MN]
    pct = lambda r: f"{r['percent']:+.2f}%"

    # 1. Momentum watch: A-category, strong gain, closed near the day's high, liquid
    momentum = sorted(
        (r for r in liquid if r["category"] == "A" and r["percent"] >= 3
         and r["high"] and r["close"] >= r["high"] * 0.985),
        key=lambda r: -r["value"])[:10]

    # 2. Speculative movers: Z-category or penny shares with big moves
    spec = sorted(
        (r for r in rows if r["percent"] >= 5 and (r["category"] == "Z" or (r["ltp"] < 10 and r["sector"] != "MutFund"))),
        key=lambda r: -r["percent"])[:10]

    # 3. Turnover leaders
    turnover = sorted(rows, key=lambda r: -r["value"])[:10]

    # 4. Sector view
    sec = defaultdict(lambda: {"value": 0.0, "pcts": []})
    for r in rows:
        sec[r["sector"]]["value"] += r["value"]
        sec[r["sector"]]["pcts"].append(r["percent"])
    sectors = sorted(
        ((s, statistics.mean(v["pcts"]), v["value"], len(v["pcts"])) for s, v in sec.items()),
        key=lambda x: -x[2])

    # 5. History-based signals (need saved days)
    spikes, ma_cross, oversold = [], [], []
    for code, r in by_code.items():
        past = hist.get(code, [])
        if len(past) >= 5:
            avg_vol = statistics.mean(p["volume"] for p in past[-20:])
            if avg_vol and r["volume"] >= VOL_SPIKE * avg_vol and r["value"] >= MIN_VALUE_MN:
                spikes.append((r["volume"] / avg_vol, code, r["category"], r["ltp"], pct(r)))
        closes = [p["close"] or p["ltp"] for p in past] + [r["close"] or r["ltp"]]
        if len(closes) > MA_LONG:
            s_now, l_now = statistics.mean(closes[-MA_SHORT:]), statistics.mean(closes[-MA_LONG:])
            s_prev, l_prev = statistics.mean(closes[-MA_SHORT - 1:-1]), statistics.mean(closes[-MA_LONG - 1:-1])
            if s_prev <= l_prev and s_now > l_now and r["category"] == "A":
                ma_cross.append((code, r["ltp"], pct(r), f"{s_now:.2f}", f"{l_now:.2f}"))
        v = rsi(closes)
        if v is not None and v < 30 and r["category"] == "A" and r["value"] >= MIN_VALUE_MN:
            oversold.append((code, r["ltp"], pct(r), f"{v:.0f}"))

    # 6. News for the day
    try:
        news = fetch(f"/api/live/news?from={day}&to={day}")["rows"]
    except Exception:
        news = []
    seen = set()
    news = [n for n in news
            if n["code"] not in ("EXCH", "DSE") and not n["code"].startswith("TB")
            and not n["body"].startswith("(Cont.")
            and not ((n["code"], n["summary"]) in seen or seen.add((n["code"], n["summary"])))]
    dividends = [n for n in news if n["type"] == "Dividend"]
    sensitive = [n for n in news if n["type"] == "Price sensitive"]

    # 7. Watchlist
    watch = []
    if WATCHLIST.exists():
        for code in WATCHLIST.read_text().split():
            r = by_code.get(code.upper())
            if r:
                watch.append((r["code"], r["category"], r["ltp"], pct(r), r["high"], r["low"], f"{r['value']:.1f}"))
            else:
                watch.append((code.upper(), "-", "trade hoy nai", "", "", "", ""))

    md = [f"# DSE Daily Screener: {day:%d %b %Y}",
          "",
          "> ⚠️ Eta research er jonno shortlist, **buy/sell recommendation na**. "
          "Kono share kinar age company er fundamentals, news ar nijer risk nije check koro.",
          "",
          "## Market summary",
          f"- **DSEX:** {dsex['value']:.2f}" + (f" ({dsex['percent']:+.2f}%)" if dsex["percent"] else ""),
          f"- **Turnover:** Tk {tot['turnover']:,.1f} mn | Trades: {tot['trades']:,}",
          f"- **Breadth:** ⬆ {br['advanced']}  ⬇ {br['declined']}  ➖ {br['unchanged']}",
          ""]
    if watch:
        md += ["## Tomar watchlist",
               fmt_table(["Code", "Cat", "LTP", "Change", "High", "Low", "Value (mn)"], watch), ""]
    md += ["## 🟢 Momentum watch (A-category, +3% er beshi, high er kache close, liquid)",
           fmt_table(["Code", "Sector", "LTP", "Change", "Value (mn)"],
                     [(r["code"], r["sector"], r["ltp"], pct(r), f"{r['value']:.1f}") for r in momentum]),
           "",
           "## 🔴 Speculative / risky movers (Z-category ba Tk 10 er niche, +5% er beshi)",
           "_Egulo te manipulation er jhuki beshi. Shabdhan._",
           "",
           fmt_table(["Code", "Cat", "LTP", "Change", "Value (mn)"],
                     [(r["code"], r["category"], r["ltp"], pct(r), f"{r['value']:.1f}") for r in spec]),
           "",
           "## 💰 Turnover leaders",
           fmt_table(["Code", "Cat", "LTP", "Change", "Value (mn)"],
                     [(r["code"], r["category"], r["ltp"], pct(r), f"{r['value']:.1f}") for r in turnover]),
           "",
           "## Sector view",
           fmt_table(["Sector", "Avg change", "Value (mn)", "Shares"],
                     [(s, f"{p:+.2f}%", f"{v:,.1f}", n) for s, p, v, n in sectors]),
           ""]
    md += ["## Technical signals"]
    if days_of_history < 6:
        md += [f"_History jomche ({days_of_history} din). Volume spike er jonno 6 din, "
               f"MA crossover/RSI er jonno {MA_LONG + 1}+ trading din er data lagbe._", ""]
    else:
        md += ["### Volume spike (recent average er 3x+)",
               fmt_table(["Code", "Cat", "LTP", "Change", "Vol ratio"],
                         [(*s[1:], f"{s[0]:.1f}x") for s in sorted(spikes, reverse=True)[:10]]), "",
               f"### MA crossover ({MA_SHORT}-day, {MA_LONG}-day er upore uthlo, A-category)",
               fmt_table(["Code", "LTP", "Change", f"MA{MA_SHORT}", f"MA{MA_LONG}"], ma_cross[:10]), "",
               "### Oversold (RSI < 30, A-category)",
               fmt_table(["Code", "LTP", "Change", "RSI"], oversold[:10]), ""]
    md += ["## 📰 Dividend declarations"]
    md += [f"- **{n['code']}**: {n['body'][:300]}" for n in dividends] or ["_Nai._"]
    md += ["", "## 📰 Price-sensitive news (prothom 15ta)"]
    md += [f"- **{n['code']}**: {n['summary']}" for n in sensitive[:15]] or ["_Nai._"]
    md += ["", f"_Source: dse.com.bd official data, trade time {tot['tradeTime']}._"]

    out = REPORTS / f"{day}.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
