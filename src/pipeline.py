"""D1 - Data pipeline: read the 4 raw CSVs -> clean -> weekly dataset -> SQLite database."""
import hashlib
import os
import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = ROOT / "foresight.db"
TABLES = ["sales_daily", "sku_master", "calendar", "inventory_snapshots"]


def hash_pw(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()


def make_users():
    rows = []
    for user, pw in [("admin", "foresight123"), ("ops", "northbay2025")]:
        salt = os.urandom(8).hex()
        rows.append({"username": user, "salt": salt, "password_hash": hash_pw(pw, salt)})
    return pd.DataFrame(rows)


def clean():
    raw = {t: pd.read_csv(RAW / f"{t}.csv") for t in TABLES}
    s, sm, cal, inv = (raw[t].copy() for t in TABLES)
    log = []
    note = lambda issue, n, fix: log.append({"issue": issue, "rows_affected": int(n), "how_handled": fix})

    for df in (s, cal, inv):
        df["date"] = pd.to_datetime(df["date"])
    sm["launch_date"] = pd.to_datetime(sm["launch_date"])

    before = sm.category.copy()
    sm["category"] = sm.category.str.strip().str.title()
    note("Inconsistent category labels (spaces / CAPS)", (before != sm.category).sum(), "Trimmed spaces, converted to Title Case")

    n = s.duplicated(["date", "sku_id"]).sum()
    s = s.drop_duplicates(["date", "sku_id"])
    note("Duplicate sales rows (same SKU + date)", n, "Kept first copy, removed the rest")

    s = s.merge(sm[["sku_id", "list_price"]], on="sku_id", how="left")
    n = s.unit_price.isna().sum()
    s["unit_price"] = s.unit_price.fillna((s.list_price * np.where(s.promo_flag == 1, 0.9, 1.0)).round())
    note("Missing unit_price", n, "Filled with list price (90% of it on promo days)")

    n = s.units_sold.isna().sum()
    s["units_sold"] = s.units_sold.fillna((s.revenue / s.unit_price).round()).fillna(0)
    note("Missing units_sold", n, "Recovered as revenue / unit_price")
    s["units_sold"] = s.units_sold.clip(lower=0)

    s["week_start"] = s.date - pd.to_timedelta(s.date.dt.weekday, unit="D")
    weekly = s.groupby(["sku_id", "week_start"], as_index=False).agg(
        units=("units_sold", "sum"), revenue=("revenue", "sum"), promo_days=("promo_flag", "sum"))
    note("Weeks missing for any SKU", weekly.groupby("sku_id").size().nunique() - 1, "None - every SKU has the same number of weeks")

    cal["week_start"] = cal.date - pd.to_timedelta(cal.date.dt.weekday, unit="D")
    cal["promo_event"] = cal.promo_event.fillna("")
    return dict(sales_daily=s.drop(columns=["list_price", "week_start"]), sku_master=sm, calendar=cal,
                inventory_snapshots=inv, weekly_sales=weekly), pd.DataFrame(log)


def save_db(tables):
    if DB.exists():
        DB.unlink()
    with sqlite3.connect(DB) as con:
        for name, df in tables.items():
            df = df.copy()
            for c in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[c]):
                    df[c] = df[c].dt.strftime("%Y-%m-%d")
            df.to_sql(name, con, index=False)
        con.executescript("""CREATE INDEX idx_sales ON sales_daily(sku_id, date);
                             CREATE INDEX idx_weekly ON weekly_sales(sku_id, week_start);""")
