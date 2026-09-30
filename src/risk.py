"""D4 - Risk scoring. Plain rules anyone can explain:

STOCKOUT  : need = forecast demand during lead time + safety stock
            cover = (on hand + on order) / need      -> cover < 1 means "we will run out"
OVERSTOCK : weeks of cover = (on hand + on order) / average forecast weekly demand
            more than 6 weeks of cover means "too much stock"
Both scores are 0-1; 0.5 is the boundary used by the 4-box decision grid."""
import numpy as np
import pandas as pd

Z = 1.28            # 90% service level
TARGET_WEEKS = 6    # more than this many weeks of stock = overstock


def score_risk(fc, weekly, inv, sku):
    last = inv.sort_values("date").groupby("sku_id").tail(1).set_index("sku_id")
    rows = []
    for _, m in sku.iterrows():
        sid = m.sku_id
        f = fc[fc.sku_id == sid].sort_values("week_start").forecast.values
        inv_row = last.loc[sid]
        lead_w = min(inv_row.lead_time_days / 7, len(f))
        full = int(lead_w)
        demand_lead = f[:full].sum() + (lead_w - full) * (f[full] if full < len(f) else 0)
        sigma = weekly[weekly.sku_id == sid].units.tail(13).std()          # how much weekly demand jumps around
        safety = Z * sigma * np.sqrt(lead_w)
        need = demand_lead + safety
        supply = inv_row.on_hand_units + inv_row.on_order_units
        avg = max(f.mean(), 0.1)
        cover, weeks_cover = supply / max(need, 0.1), supply / avg
        so, ov = float(np.clip(1.5 - cover, 0, 1)), float(np.clip((weeks_cover - 2) / 8, 0, 1))
        if so >= .5 and ov >= .5:
            quad, action = "Watch / volatile", "Investigate - long lead time or erratic demand; review manually"
        elif so >= .5:
            quad, action = "Reorder now", "Raise a replenishment order before stock runs out"
        elif ov >= .5:
            quad, action = "Markdown / clear", "Promote or discount to free up cash"
        else:
            quad, action = "Healthy", "No action needed"
        rows.append(dict(
            sku_id=sid, product=m.product_name, category=m.category, on_hand=int(inv_row.on_hand_units),
            on_order=int(inv_row.on_order_units), lead_time_days=int(inv_row.lead_time_days),
            forecast_6wk_units=round(f.sum()), avg_weekly_forecast=round(avg, 1), demand_in_lead_time=round(demand_lead, 1),
            safety_stock=round(safety, 1), cover_ratio=round(cover, 2), weeks_of_stock=round(weeks_cover, 1),
            stockout_score=round(so, 2), overstock_score=round(ov, 2), quadrant=quad, action=action,
            suggested_order_units=int(np.ceil(max(0, need + 2 * avg - supply))) if so >= .5 else 0,
            sales_at_risk=round(max(0, need - supply) * m.list_price),
            locked_capital=round(max(0, supply - TARGET_WEEKS * avg) * m.unit_cost),
            forecast_revenue=round(f.sum() * m.list_price)))
    return pd.DataFrame(rows)
