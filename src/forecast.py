"""D3 - Weekly demand forecast for the next 6 weeks, per SKU.
Baseline : seasonal-naive  (same week last year).
Model    : gradient boosting using only information known at the forecast date.
Test     : rolling-origin backtest (train on the past, predict the next 6 weeks, repeat 6 times).
Rule     : the model is only used if it beats the baseline on the backtest (WAPE)."""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

H = 6            # forecast horizon (weeks)
N_FOLDS = 6      # number of backtest rounds
FEATURES = ["sku", "h", "last1", "m4", "m8", "ly", "ly3", "promo", "hol", "woy"]


def wape(actual, pred):
    return float(np.abs(actual - pred).sum() / max(actual.sum(), 1e-9))


def _matrices(weekly, cal):
    skus = sorted(weekly.sku_id.unique())
    U = weekly.pivot(index="week_start", columns="sku_id", values="units")[skus]
    n = len(U)
    weeks = pd.date_range(U.index[0], periods=n + H, freq="7D")
    U = U.reindex(weeks)                                 # future weeks = NaN (unknown)
    cw = cal.groupby("week_start").agg(promo=("promo_event", lambda x: (x != "").sum()),
                                       hol=("is_holiday", "sum")).reindex(weeks)
    return skus, U.values.astype(float), weeks, cw.promo.values, cw.hol.values, n


def _rows(U, weeks, promo, hol, n, origin, j):
    out = []
    hist = U[:origin + 1, j]                             # only data up to the forecast date
    for h in range(1, H + 1):
        t = origin + h
        ly = U[t - 52, j] if t >= 52 else np.nan         # same week last year (always in the past)
        ly3 = np.nanmean(U[t - 53:t - 50, j]) if t >= 53 else np.nan
        y = U[t, j] if t < n else np.nan
        out.append(dict(sku=j, origin=origin, h=h, t=t, last1=hist[-1], m4=hist[-4:].mean(), m8=hist[-8:].mean(),
                        ly=ly, ly3=ly3, promo=promo[t], hol=hol[t], woy=weeks[t].isocalendar().week, y=y))
    return out


def _fit(train):
    m = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_depth=4, random_state=42)
    return m.fit(train[FEATURES], train.y)


def run_forecast(weekly, cal, skus_master):
    skus, U, weeks, promo, hol, n = _matrices(weekly, cal)
    rows = []
    for origin in range(8, n):
        for j in range(len(skus)):
            rows += _rows(U, weeks, promo, hol, n, origin, j)
    data = pd.DataFrame(rows)

    # ---- rolling-origin backtest
    origins = [n - 1 - H - H * k for k in range(N_FOLDS)][::-1]
    bt = []
    for o in origins:
        train = data[(data.t <= o) & data.y.notna()]                 # targets must already be known at origin o
        test = data[(data.origin == o) & (data.t < n)].copy()
        test["model"] = np.clip(_fit(train).predict(test[FEATURES]), 0, None)
        test["baseline"] = test.ly
        bt.append(test)
    bt = pd.concat(bt)
    bt["sku_id"] = bt.sku.map(dict(enumerate(skus)))
    bt["week_start"] = bt.t.map(dict(enumerate(weeks)))

    wm, wb = wape(bt.y, bt.model), wape(bt.y, bt.baseline)
    use_model = wm < wb
    metrics = pd.DataFrame([
        ("WAPE - model", wm), ("WAPE - seasonal-naive baseline", wb),
        ("Improvement vs baseline (%)", (wb - wm) / wb * 100),
        ("Bias - model (+ = over-forecast)", float((bt.model - bt.y).sum() / bt.y.sum())),
        ("Model used", "gradient boosting" if use_model else "seasonal-naive baseline")], columns=["metric", "value"])
    metrics["value"] = metrics.value.astype(str)
    per_sku = bt.groupby("sku_id").apply(lambda g: pd.Series(
        {"wape_model": wape(g.y, g.model), "wape_baseline": wape(g.y, g.baseline)}), include_groups=False).reset_index()

    # ---- final forecast: train on everything known, predict next 6 weeks
    final = data[(data.t <= n - 1) & data.y.notna()]
    model = _fit(final)
    fut = pd.DataFrame([r for j in range(len(skus)) for r in _rows(U, weeks, promo, hol, n, n - 1, j)])
    pred = np.clip(model.predict(fut[FEATURES]), 0, None) if use_model else fut.ly.values
    ratio = ((bt.y - bt.model) / bt.model.clip(lower=1)).values               # typical % miss -> 80% interval
    q10, q90 = np.quantile(ratio, [.1, .9])
    fc = pd.DataFrame({"sku_id": fut.sku.map(dict(enumerate(skus))), "week_start": fut.t.map(dict(enumerate(weeks))),
                       "forecast": pred, "low": np.clip(pred * (1 + q10), 0, None), "high": pred * (1 + q90),
                       "baseline": fut.ly.values})
    bt_out = bt[["sku_id", "week_start", "y", "model", "baseline"]].rename(columns={"y": "actual"})
    for df, d in ((fc, 1), (bt_out, 1)):
        num = df.select_dtypes("number").columns
        df[num] = df[num].round(d)
    return fc, bt_out, per_sku.round(3), metrics
