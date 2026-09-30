"""One function that runs everything: data -> clean -> forecast -> risk -> database."""
import sqlite3
from src import generate_data, pipeline, forecast, risk


def run_all(regenerate_data=True):
    if regenerate_data or not all((pipeline.RAW / f"{t}.csv").exists() for t in pipeline.TABLES):
        generate_data.main()
    tables, quality = pipeline.clean()
    fc, bt, per_sku, metrics = forecast.run_forecast(tables["weekly_sales"], tables["calendar"], tables["sku_master"])
    risk_df = risk.score_risk(fc, tables["weekly_sales"], tables["inventory_snapshots"], tables["sku_master"])
    tables.update(data_quality=quality, forecast=fc, backtest=bt, backtest_by_sku=per_sku, metrics=metrics,
                  risk=risk_df, users=pipeline.make_users())
    tables["forecast"]["week_start"] = tables["forecast"].week_start.astype("datetime64[ns]")
    tables["backtest"]["week_start"] = tables["backtest"].week_start.astype("datetime64[ns]")
    pipeline.save_db(tables)
    print(metrics.to_string(index=False))
    print(risk_df[["product", "weeks_of_stock", "cover_ratio", "quadrant", "sales_at_risk", "locked_capital"]].to_string(index=False))
    print(f"\nDatabase ready: {pipeline.DB}")
