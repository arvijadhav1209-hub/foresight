# 🔮 Project FORESIGHT – Demand & Inventory Intelligence (NorthBay Living)

Tells the operations team, for 12 everyday home products: **how much will sell in the next 6 weeks, which products will run out (reorder), and which are overstocked (clear).**

## Quick start
```bash
pip install -r requirements.txt
python run_pipeline.py        # one command: data -> clean -> forecast -> risk -> foresight.db
streamlit run app.py          # open the dashboard
```
**Demo login:** `admin` / `foresight123` (or `ops` / `northbay2025`). Passwords are stored hashed (PBKDF2) in the `users` table.

## Folder map
| File | What it does |
|---|---|
| `src/generate_data.py` | Makes the small sample CSVs (12 products, 2 years). Replace `data/raw/*.csv` with Zidio's official files if provided. |
| `src/pipeline.py` | D1 – cleaning (duplicates, blanks, messy labels) + saves everything to SQLite |
| `src/forecast.py` | D3 – seasonal-naive baseline vs gradient boosting, rolling-origin backtest, WAPE |
| `src/risk.py` | D4 – stockout / overstock rules, recommended action, ₹ at stake |
| `app.py` | D5 – login + dashboard |

## Database (`foresight.db`)
`sales_daily`, `sku_master`, `calendar`, `inventory_snapshots` (cleaned inputs) → `weekly_sales` → `forecast`, `backtest`, `backtest_by_sku`, `metrics` → `risk`. Plus `data_quality` (issues found) and `users` (login).
Example: `SELECT product, sales_at_risk FROM risk ORDER BY sales_at_risk DESC;`

## Backtest result (seed 42, 6 rolling rounds × 6 weeks)
| | WAPE (lower is better) |
|---|---|
| Seasonal-naive baseline (same week last year) | 18.0% |
| Gradient boosting model | **14.5%** (≈19% better) |

No leakage: each feature uses only data up to the forecast date; promo/holiday plans are known in advance from the calendar. The model is only used if it beats the baseline.

## Risk rules (plain English)
- **Running out:** expected demand during delivery time + safety stock (90% service level) > stock on hand + on order → *Reorder now*.
- **Too much stock:** stock lasts > 6 weeks of forecast sales → *Markdown / clear*. Both true → *Watch*.

## Deploy (free) – Streamlit Community Cloud
Push to GitHub → share.streamlit.io → New app → select repo, main file `app.py`. The database builds itself on first start.

## Assumptions
Sample data is synthetic (Zidio's brief says data is provided; this stands in for it). Lead times and reorder points are assumed accurate.
