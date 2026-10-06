# Option Dashboard

Personal option-selling research portal for NSE index and Nifty 50 stock options
(modelled on the workflow of club.profitsfirst.in): pick instruments from an RSI
signal grid → analyse the chart setup → build a Bear Call / Bull Put / Iron
Condor on the option chain → track positions.

## Run

```bash
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
python master.py                 # http://127.0.0.1:8050
python master.py --refresh       # one data refresh from the CLI
```

UI development with hot reload: run `python master.py`, then `cd frontend && npm run dev`
and open http://localhost:5173 (API calls are proxied to 8050).

## Configuration

| File | What |
|---|---|
| `config/watchlist.yaml` | Indices and stocks to track. Only `enabled` entries are fetched. |
| `config/settings.yaml` | RSI thresholds (40/60), refresh interval, capital (₹1,00,000), margin cap. |
| `.env` | Optional: Angel One SmartAPI keys for live prices and exact margins (copy `.env.example`). |

Default data is free and needs no account: Yahoo Finance for stock/NIFTY/BANKNIFTY candles (~15 min delay)
and NSE (nseindia.com JSON endpoints) for option chains, lot sizes, expiries, FINNIFTY/MIDCPNIFTY and sector
index history, and corporate events. NSE blocks most datacenter IPs — re-test before moving to a VPS.

## Architecture

- **Backend**: Python, FastAPI, SQLite (`data/optiondash.db`, WAL mode). A background
  thread refreshes every 15 min during market hours plus once after the close; the
  "Refresh now" button returns cached data if the last refresh is under 2 min old.
- **Data**: Yahoo Finance + NSE (free, default); Angel One SmartAPI optional (TOTP auto-login).
  Greeks and POP are computed locally (Black-Scholes on NSE IV); margin is estimated unless Angel is set up.
- **Frontend**: React + Vite + TypeScript + Tailwind, built to `frontend/dist` and served by FastAPI.

## Signal rule

Daily RSI(14) zone triggers, weekly RSI(14) must not oppose:

| Daily | Weekly | Signal |
|---|---|---|
| < 40 | < 60 | Bear Call |
| > 60 | > 40 | Bull Put |
| 40–60 | 40–60 | Iron Condor |
| otherwise | | Wait for confirmation |

Matches the reference site on all 24 cards compared (4 Oct 2026).

## Phases

1. **Done** — data layer (Angel/Yahoo, SQLite, scheduler), events, signal grid dashboard
   (filters by event/signal/sector/watchlist, bookmarks, selection → Analyse).
2. **Done** — analysis page: chart summary (RSI zones, weekly/daily Bollinger Bands, prev-month H/L,
   confluence x/3), RSI charts (3Y weekly, 2Y daily), reversal confluence (BB exhaustion,
   RSI divergence ≤20 bars, candlestick pattern ≤10 days, TTM squeeze), sector context
   (monthly sector index + BB), S/R chart (swing levels merged across D/W/M, ≥2 touches,
   within 12%, gaps ≥1.5%, 5–12% zone), notes, save as PDF. Strike lines come with phase 3.
   Checked against the reference on RELIANCE: weekly BB, prev-month H/L, confluence 0/3 and
   weekly squeeze match exactly; 15 of their 20 S/R levels match within 0.3%.
3. **Done** — option chain + position builder (NSE chain, Greeks via Black-Scholes on NSE IV):
   chain table (OI, ΔOI, IV, Δ, LTP, S/B buttons, 5–12% zone + ITM shading, ATM ±15 / all),
   expiry picker, "Validate as" Bear Call / Bull Put / Iron Condor, "Suggest strikes" (just past the
   nearest S/R level in the 5–12% zone, Δ ≤ 0.30, hedge two strikes out), legs editor, net credit,
   max profit/loss, breakevens, POP (lognormal on short-strike IV), margin estimate vs 20% cap,
   payoff chart, validation checklist (signal, structure, zone, delta, S/R cover, margin, events),
   strikes drawn on the S/R chart; OI analytics tab (PCR OI/volume, max pain, ATM IV, call/put
   walls, OI / ΔOI by strike with build-up). Draft legs persist per symbol for phase 4.
4. **Done** — positions (`/positions/real`, `/positions/paper`): record form (prefilled from the
   builder via "Record position →" / "Paper trade →", or manual with NSE expiries + lot size),
   stop rules 1×/2×/3× credit or strike breach (0.5% buffer), risk-budget check; open cards with
   live P&L from the NSE chain, % of stop used, POP now vs entry, breakevens, spot move since
   entry, nearest short strike; Close (realised P&L), Close legs (credit/max loss/stop recomputed),
   Edit entry, Delete; monthly + annual ROI on margin; closed list; LIVE / AS OF CLOSE /
   AT PREV CLOSE freshness tag. Tables: `positions`, `legs`.
   **Guide** (`/guide`, `frontend/src/pages/GuidePage.tsx`): user manual — workflow, every screen, signal
   rule, strategy playbook, risk rules, routine, data limits, glossary, FAQ. PDF export in
   `docs/Option_Dashboard_User_Guide.pdf` (regenerate via the page's Save as PDF after edits).
5. **Telegram alerts done** (`backend/alerts.py`, `/alerts` page): 09:20 / 15:35 weekday summaries
   (open positions per book, P&L, stop used, POP, month ROI, signal grid), stop alerts at 95% / 100%
   checked every 5 min in market hours (once per level, re-armed 10 points below), test / send-now
   buttons, message log. Token + chat id in `.env`, switches in `settings.yaml` `alerts:`.
   Analyse (payoff vs target price/date) on position cards and the record form.
   **Pending** — VPS deploy (Docker + nginx + HTTPS, India region).
