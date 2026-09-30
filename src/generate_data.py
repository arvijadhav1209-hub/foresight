"""Creates a SMALL sample dataset: 12 everyday home products, 2 years of daily sales.
Four CSVs are written to data/raw/ (same 4 tables as the Zidio brief).
A few data problems are added on purpose (duplicates, blanks, messy labels)
so the cleaning step has real work to do. If Zidio gives you the official
files, just drop them into data/raw/ with the same names and re-run."""
import numpy as np
import pandas as pd
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

# id, name, category, subcategory, avg units/day, list price Rs, unit cost Rs, lead days, peak day-of-year, season strength
SKUS = [
    ("SKU01", "Steel Water Bottle", "Kitchen", "Drinkware", 9, 499, 250, 7, 150, .25),
    ("SKU02", "Ceramic Coffee Mug", "Kitchen", "Drinkware", 12, 299, 120, 7, 340, .20),
    ("SKU03", "Non-stick Pan", "Kitchen", "Cookware", 6, 899, 480, 14, 300, .15),
    ("SKU04", "Cotton Bedsheet", "Bedroom", "Bedding", 7, 1199, 600, 14, 355, .35),
    ("SKU05", "Soft Pillow Set", "Bedroom", "Bedding", 5, 799, 380, 14, 20, .30),
    ("SKU06", "Woolen Blanket", "Bedroom", "Bedding", 3, 1999, 1100, 21, 10, .70),
    ("SKU07", "Table Lamp", "Decor", "Lighting", 4, 1299, 650, 14, 300, .30),
    ("SKU08", "Scented Candle", "Decor", "Fragrance", 10, 349, 130, 7, 300, .45),
    ("SKU09", "Wall Clock", "Decor", "Wall Art", 1.5, 999, 480, 14, 180, .05),
    ("SKU10", "Electric Kettle", "Appliances", "Small Appliance", 5, 1499, 800, 28, 300, .15),
    ("SKU11", "Mixer Grinder", "Appliances", "Small Appliance", 3, 3499, 2100, 42, 300, .20),
    ("SKU12", "Room Fan", "Appliances", "Cooling", 3, 2499, 1400, 35, 110, .80),
]
# Latest stock = weeks of demand on hand, weeks of demand on order (designed to give a mix of situations)
STOCK = {"SKU01": (1.0, 0), "SKU02": (3.0, 0), "SKU03": (.8, .3), "SKU04": (9, 0), "SKU05": (3.5, 1),
         "SKU06": (1.2, 0), "SKU07": (4, .5), "SKU08": (2.5, 0), "SKU09": (16, 0), "SKU10": (2, 0),
         "SKU11": (6.3, 0), "SKU12": (10, 0)}

HOLIDAYS = ["2024-01-01", "2024-01-26", "2024-03-25", "2024-08-15", "2024-10-02", "2024-11-01", "2024-12-25",
            "2025-01-01", "2025-01-26", "2025-03-14", "2025-08-15", "2025-10-02", "2025-10-20", "2025-12-25",
            "2026-01-01", "2026-01-26"]
EVENTS = {"Republic Day Sale": [("2024-01-20", "2024-01-26"), ("2025-01-20", "2025-01-26"), ("2026-01-20", "2026-01-26")],
          "Summer Sale": [("2024-05-10", "2024-05-20"), ("2025-05-10", "2025-05-20")],
          "Diwali Sale": [("2024-10-22", "2024-11-01"), ("2025-10-10", "2025-10-20")],
          "Year-End Sale": [("2024-12-20", "2024-12-31"), ("2025-12-20", "2025-12-31")]}
SEASON = lambda m: "Winter" if m in (12, 1, 2) else "Summer" if m in (3, 4, 5) else "Monsoon" if m < 10 else "Festive"


def main(seed=42):
    rng = np.random.default_rng(seed)
    RAW.mkdir(parents=True, exist_ok=True)

    # calendar (runs 6 weeks past the last sales day so promo/holiday plans are known for the forecast)
    cal = pd.DataFrame({"date": pd.date_range("2024-01-01", "2026-02-08")})
    cal["week"] = cal.date.dt.isocalendar().week.astype(int)
    cal["month"] = cal.date.dt.month
    cal["season"] = cal.month.map(SEASON)
    cal["is_holiday"] = cal.date.isin(pd.to_datetime(HOLIDAYS)).astype(int)
    cal["promo_event"] = ""
    for name, spans in EVENTS.items():
        for a, b in spans:
            cal.loc[cal.date.between(a, b), "promo_event"] = name

    # daily sales
    days = cal[cal.date <= "2025-12-28"].reset_index(drop=True)
    promo = (days.promo_event != "").values
    hol = days.is_holiday.values == 1
    wkend = days.date.dt.weekday.values >= 5
    doy = days.date.dt.dayofyear.values
    trend = 1 + 0.2 * np.arange(len(days)) / len(days)
    frames = []
    for sid, _, _, _, base, lp, _, _, peak, amp in SKUS:
        lam = base * (1 + amp * np.cos(2 * np.pi * (doy - peak) / 365)) * trend
        lam = lam * np.where(wkend, 1.25, 1) * np.where(promo, 1.5, 1) * np.where(hol, 1.2, 1)
        units = rng.poisson(lam)
        price = np.where(promo, np.round(lp * 0.9), lp)
        frames.append(pd.DataFrame({"date": days.date, "sku_id": sid, "units_sold": units, "revenue": units * price,
                                    "unit_price": price, "promo_flag": promo.astype(int)}))
    sales = pd.concat(frames, ignore_index=True)

    # inventory snapshots (every Monday)
    pv = sales.pivot(index="date", columns="sku_id", values="units_sold")
    inv = []
    snaps = pd.date_range("2024-01-01", "2025-12-29", freq="7D")
    for d in snaps:
        for sid, _, _, _, base, _, _, lead, _, _ in SKUS:
            past = pv.loc[:d - pd.Timedelta(days=1), sid].tail(56)
            avg_w = past.mean() * 7 if len(past) > 6 else base * 7
            oh_w, oo_w = STOCK[sid] if d == snaps[-1] else (rng.uniform(1.5, 5), rng.choice([0, 1]))
            inv.append({"date": d, "sku_id": sid, "on_hand_units": int(avg_w * oh_w), "on_order_units": int(avg_w * oo_w),
                        "lead_time_days": lead, "reorder_point": int(avg_w * lead / 7 * 1.3)})
    inv = pd.DataFrame(inv)

    # SKU master (with messy labels on purpose)
    sm = pd.DataFrame([{"sku_id": s[0], "product_name": s[1], "category": s[2], "subcategory": s[3],
                        "launch_date": "2023-06-01", "unit_cost": s[6], "list_price": s[5]} for s in SKUS])
    sm.loc[[1, 4, 7], "category"] = ["kitchen ", "BEDROOM", "decor "]

    # deliberate data problems in sales
    sales.loc[rng.choice(len(sales), 25, replace=False), "units_sold"] = np.nan
    sales.loc[rng.choice(len(sales), 15, replace=False), "unit_price"] = np.nan
    sales = pd.concat([sales, sales.sample(30, random_state=1)], ignore_index=True)

    for df in (sales, cal, inv):
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    sales.to_csv(RAW / "sales_daily.csv", index=False)
    sm.to_csv(RAW / "sku_master.csv", index=False)
    cal.to_csv(RAW / "calendar.csv", index=False)
    inv.to_csv(RAW / "inventory_snapshots.csv", index=False)
    print(f"Sample data written to {RAW}")


if __name__ == "__main__":
    main()
