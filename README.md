# DSE Daily Screener

Protidin DSE market close er por official data (dse.com.bd) theke ekta screener report banay.

> ⚠️ Eta research er jonno shortlist, buy/sell recommendation na.

## Kivabe kaj kore
- GitHub Actions protidin **3:45 PM (BD time)** e `screener.py` chalay (special Saturday trading day-o dhora pore).
- Sob share er din-sheshe data `history/` e save hoy. Ei data diye volume spike, MA crossover ar RSI hisab hoy.
- Report `reports/YYYY-MM-DD.md` e save hoy, ar ekta GitHub Issue khule (email notification ashe).
- Chhutir din ba market bondho thakle kichu hoy na.

## Data sources
- **dse.com.bd** (official): protidin er price, volume, category, sector, news
- **DSE Intelligence (stockchartbd.com)**: P/E, EPS, health warning score, ar purono price history (backfill)

## Long-term history (1999 theke aj porjonto)
`python3 longterm.py SQURPHARMA --yearly` chalale `exports/SQURPHARMA.csv` e 1999 theke ajker sob daily price ashe, ar ekta bochor-bhittik summary dekhay.
- 1999 - Apr 2025: "Dhaka Stock Exchange Historical Data (1999-2025)", Mendeley Data, doi:10.17632/5mww8rb9td.1, CC BY 4.0 (`data/dse_1999_2025.csv.gz`)
- Aug 2024 - aj: DSE Intelligence (stockchartbd.com)

⚠️ Price gulo bonus/right share ba face value change er jonno **adjust kora na**. Jemon 2011 e face value Tk 100 theke Tk 10 howay price ~90% kome geche, eta asole crash na.

## History backfill (ekbar-i)
Technical signal er jonno history lage. Ekbar **Actions → History backfill (one-time) → Run workflow** chalale
~60 trading din er history bhore jabe (~3.5 ghonta, API rate limit er karone).

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

Signal table gulote **P/E, EPS ar Health** column thake. ⚠️ mane loss-making (EPS negative) ba high-risk share.
