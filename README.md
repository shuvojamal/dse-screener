# DSE Daily Screener

Protidin DSE market close er por official data (dse.com.bd) theke ekta screener report banay.

> ⚠️ Eta research er jonno shortlist, buy/sell recommendation na.

## Kivabe kaj kore
- GitHub Actions protidin **Sunday-Thursday, 3:45 PM (BD time)** e `screener.py` chalay.
- Sob share er din-sheshe data `history/` e save hoy. Ei data diye volume spike, MA crossover ar RSI hisab hoy.
- Report `reports/YYYY-MM-DD.md` e save hoy, ar ekta GitHub Issue khule (email notification ashe).
- Chhutir din ba market bondho thakle kichu hoy na.

## Watchlist
`watchlist.txt` e tomar share er trading code dao (prottek line e ekta), jemon:
```
GP
SQURPHARMA
```

## Manual chalano
- GitHub e: **Actions → DSE daily screener → Run workflow**
- Local e: `python3 screener.py` (ager report abar banate `--force`)

## Signals
| Section | Ki dekhay |
|---|---|
| Momentum watch | A-category, +3% er beshi, diner high er kache close, Tk 5 mn+ turnover |
| Risky movers | Z-category ba Tk 10 er nicher share e +5% er beshi |
| Volume spike | Volume 20-din average er 3x+ (6 din history lage) |
| MA crossover | 5-day MA 20-day MA er upore uthlo (21+ din history lage) |
| Oversold | RSI(14) < 30, A-category |
