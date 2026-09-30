"""D5 - FORESIGHT planning dashboard (Streamlit). Run:  streamlit run app.py"""
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from src import pipeline

st.set_page_config(page_title="FORESIGHT | NorthBay Living", page_icon="🔮", layout="wide")

PINK, LAV, AMBER, GREEN, BLUE, TEAL = "#F78FB3", "#9D8DF1", "#FFC75F", "#6FCF97", "#7C83FD", "#5FD3C3"
QCOL = {"Reorder now": PINK, "Markdown / clear": LAV, "Watch / volatile": AMBER, "Healthy": GREEN}
QICON = {"Reorder now": "🛒", "Markdown / clear": "🏷️", "Watch / volatile": "👀", "Healthy": "✅"}

st.markdown("""<style>
.block-container{padding-top:1.5rem}
[data-testid=stMetric]{background:#fff;border-radius:16px;padding:14px 18px;box-shadow:0 2px 10px rgba(124,131,253,.15)}
.big{font-size:2rem;font-weight:700;color:#2D3250;margin-bottom:0}
.sub{color:#6b7194;margin-bottom:1rem}
.tip{background:#EEF0FF;border-left:5px solid #7C83FD;border-radius:10px;padding:12px 16px;color:#2D3250}
</style>""", unsafe_allow_html=True)


def inr(x):
    x = float(x)
    return f"₹{x / 1e5:.1f} L" if abs(x) >= 1e5 else f"₹{x:,.0f}"


# ---------------------------------------------------------------- data
@st.cache_data(show_spinner="Loading data...")
def load():
    with sqlite3.connect(pipeline.DB) as con:
        q = lambda t: pd.read_sql(f"SELECT * FROM {t}", con)
        d = {t: q(t) for t in ["weekly_sales", "forecast", "backtest", "risk", "metrics", "sku_master", "data_quality", "backtest_by_sku"]}
    for t in ("weekly_sales", "forecast", "backtest"):
        d[t]["week_start"] = pd.to_datetime(d[t]["week_start"])
    return d


def check_login(user, pw):
    with sqlite3.connect(pipeline.DB) as con:
        row = con.execute("SELECT salt, password_hash FROM users WHERE username=?", (user.strip().lower(),)).fetchone()
    return bool(row) and pipeline.hash_pw(pw, row[0]) == row[1]


if not pipeline.DB.exists():                       # first start on a fresh server: build everything
    from src.run import run_all
    with st.spinner("First start - building the database (about 30 seconds)..."):
        run_all()

# ---------------------------------------------------------------- login
if not st.session_state.get("user"):
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("<br><br><p class='big' style='text-align:center'>🔮 FORESIGHT</p>"
                    "<p class='sub' style='text-align:center'>Demand & Inventory Intelligence · NorthBay Living</p>", unsafe_allow_html=True)
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            go_ = st.form_submit_button("Log in", use_container_width=True, type="primary")
        if go_:
            if check_login(u, p):
                st.session_state["user"] = u.strip().lower()
                st.rerun()
            else:
                st.error("Wrong username or password. Please try again.")
        st.caption("Demo login → username: **admin**  password: **foresight123**")
    st.stop()

D = load()
risk, fc, wk, bt = D["risk"], D["forecast"], D["weekly_sales"], D["backtest"]
M = dict(zip(D["metrics"].metric, D["metrics"].value))

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown(f"### 🔮 FORESIGHT\nHello, **{st.session_state['user'].title()}** 👋")
    page = st.radio("Go to", ["🏠 Overview", "📈 Forecast", "🎯 Decision grid", "🛒 Action list", "🗄️ Database"])
    cat = st.selectbox("Category", ["All"] + sorted(risk.category.unique()))
    rv = risk if cat == "All" else risk[risk.category == cat]
    prod = st.selectbox("Product", rv["product"].tolist())
    if st.button("Log out", use_container_width=True):
        st.session_state.clear()
        st.rerun()

if rv.empty:
    st.info("No products match this filter.")
    st.stop()

# ---------------------------------------------------------------- pages
if page == "🏠 Overview":
    st.markdown("<p class='big'>Overview</p><p class='sub'>What should we reorder, clear or leave alone? (next 6 weeks)</p>", unsafe_allow_html=True)
    c = st.columns(4)
    c[0].metric("🛒 Products to reorder", int((rv.quadrant == "Reorder now").sum()))
    c[1].metric("🏷️ Products to clear", int((rv.quadrant == "Markdown / clear").sum()))
    c[2].metric("💸 Sales at risk", inr(rv.sales_at_risk.sum()))
    c[3].metric("🔒 Cash locked in stock", inr(rv.locked_capital.sum()))
    a, b = st.columns([1, 1.6])
    with a:
        cnt = rv.quadrant.value_counts().reset_index()
        fig = px.pie(cnt, names="quadrant", values="count", hole=.55, color="quadrant", color_discrete_map=QCOL, title="Stock health of products")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=50, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with b:
        ids = rv.sku_id.tolist()
        h = wk[wk.sku_id.isin(ids)].groupby("week_start").units.sum().tail(26).reset_index()
        f = fc[fc.sku_id.isin(ids)].groupby("week_start").forecast.sum().reset_index()
        fig = go.Figure([go.Scatter(x=h.week_start, y=h.units, name="Actual sales", fill="tozeroy", line=dict(color=BLUE), fillcolor="rgba(124,131,253,.2)"),
                         go.Scatter(x=f.week_start, y=f.forecast, name="Forecast", line=dict(color=PINK, width=3, dash="dash"))])
        fig.update_layout(title="Units sold per week (last 26 weeks + next 6)", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          yaxis_title="Units per week", margin=dict(t=50, b=10), legend=dict(orientation="h", y=-.15))
        st.plotly_chart(fig, use_container_width=True)
    top = rv[rv.quadrant == "Reorder now"].sort_values("sales_at_risk", ascending=False)
    if len(top):
        r = top.iloc[0]
        st.markdown(f"<div class='tip'>💡 <b>Most urgent:</b> reorder <b>{r['product']}</b> — only {r.weeks_of_stock} weeks of stock left and "
                    f"{r.lead_time_days} days to restock. Suggested order: <b>{r.suggested_order_units} units</b> (protects about {inr(r.sales_at_risk)} of sales).</div>", unsafe_allow_html=True)
    st.caption(f"Forecast check: model error (WAPE) {float(M['WAPE - model']):.1%} vs simple baseline {float(M['WAPE - seasonal-naive baseline']):.1%} "
               f"→ {float(M['Improvement vs baseline (%)']):.0f}% more accurate. Lower is better.")

elif page == "📈 Forecast":
    r = risk[risk["product"] == prod].iloc[0]
    sid = r.sku_id
    st.markdown(f"<p class='big'>{prod}</p><p class='sub'>{r.category} · {QICON[r.quadrant]} {r.quadrant}</p>", unsafe_allow_html=True)
    h, f, b = wk[wk.sku_id == sid].tail(40), fc[fc.sku_id == sid], bt[bt.sku_id == sid]
    fig = go.Figure([
        go.Scatter(x=f.week_start, y=f.high, line=dict(width=0), showlegend=False, hoverinfo="skip"),
        go.Scatter(x=f.week_start, y=f.low, fill="tonexty", fillcolor="rgba(247,143,179,.25)", line=dict(width=0), name="Likely range (80%)"),
        go.Scatter(x=h.week_start, y=h.units, name="Actual sales", line=dict(color=BLUE, width=3)),
        go.Scatter(x=b.week_start, y=b.model, name="Model (tested on past)", line=dict(color=TEAL, dash="dot")),
        go.Scatter(x=f.week_start, y=f.forecast, name="Forecast", line=dict(color=PINK, width=3))])
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", yaxis_title="Units per week",
                      legend=dict(orientation="h", y=-.15), margin=dict(t=20))
    st.plotly_chart(fig, use_container_width=True)
    c = st.columns(4)
    c[0].metric("Stock on hand", f"{r.on_hand} units")
    c[1].metric("On order", f"{r.on_order} units")
    c[2].metric("Weeks of stock", r.weeks_of_stock)
    c[3].metric("Next 6 weeks forecast", f"{r.forecast_6wk_units} units")
    st.markdown(f"<div class='tip'>➡️ <b>Recommended action:</b> {r.action}</div>", unsafe_allow_html=True)

elif page == "🎯 Decision grid":
    st.markdown("<p class='big'>Decision grid</p><p class='sub'>Every product in one picture. Bigger bubble = more sales value.</p>", unsafe_allow_html=True)
    fig = px.scatter(rv, x="overstock_score", y="stockout_score", size="forecast_revenue", color="quadrant", color_discrete_map=QCOL,
                     hover_name="product", text="product", size_max=45, range_x=[-.05, 1.05], range_y=[-.05, 1.05],
                     labels={"overstock_score": "Too much stock →", "stockout_score": "Running out →"})
    for x0, y0, col, txt in [(0, .5, PINK, "REORDER NOW"), (.5, .5, AMBER, "WATCH"), (0, 0, GREEN, "HEALTHY"), (.5, 0, LAV, "MARKDOWN / CLEAR")]:
        fig.add_shape(type="rect", x0=x0, x1=x0 + .5, y0=y0, y1=y0 + .5, fillcolor=col, opacity=.12, line_width=0, layer="below")
        fig.add_annotation(x=x0 + .25, y=y0 + .47, text=f"<b>{txt}</b>", showarrow=False, font=dict(color="#6b7194"))
    fig.update_traces(textposition="top center")
    fig.update_layout(height=560, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend_title="")
    st.plotly_chart(fig, use_container_width=True)

elif page == "🛒 Action list":
    st.markdown("<p class='big'>Action list</p><p class='sub'>Most valuable problems first.</p>", unsafe_allow_html=True)
    t1, t2, t3 = st.tabs(["🛒 Reorder now", "🏷️ Markdown / clear", "👀 Watch"])
    cols = {"product": "Product", "on_hand": "In stock", "on_order": "On order", "weeks_of_stock": "Weeks of stock"}
    with t1:
        d = rv[rv.quadrant.isin(["Reorder now", "Watch / volatile"]) & (rv.sales_at_risk > 0)].sort_values("sales_at_risk", ascending=False)
        if d.empty: st.success("Nothing to reorder right now 🎉")
        else: st.dataframe(d[["product", "on_hand", "on_order", "weeks_of_stock", "lead_time_days", "suggested_order_units", "sales_at_risk"]].rename(
            columns={**cols, "lead_time_days": "Days to restock", "suggested_order_units": "Suggested order", "sales_at_risk": "Sales at risk (₹)"}), hide_index=True, use_container_width=True)
    with t2:
        d = rv[rv.locked_capital > 0].sort_values("locked_capital", ascending=False)
        if d.empty: st.success("No overstock 🎉")
        else: st.dataframe(d[["product", "on_hand", "weeks_of_stock", "locked_capital"]].rename(columns={**cols, "locked_capital": "Cash locked (₹)"}), hide_index=True, use_container_width=True)
    with t3:
        d = rv[rv.quadrant == "Watch / volatile"]
        if d.empty: st.success("Nothing to watch 🎉")
        else: st.dataframe(d[["product", "weeks_of_stock", "lead_time_days", "action"]].rename(columns={**cols, "lead_time_days": "Days to restock", "action": "Why"}), hide_index=True, use_container_width=True)
    with st.expander("How are these decided? (plain English)"):
        st.markdown("- **Running out:** we add up the demand we expect while a new order is on its way, plus a safety cushion. If stock + orders are less than that → reorder.\n"
                    "- **Too much stock:** if stock would last more than **6 weeks** at the forecast sales speed → clear it.\n"
                    "- **Both:** long delivery time *and* lots of stock → check manually.")

else:
    st.markdown("<p class='big'>Database</p><p class='sub'>All results live in one SQLite file: <code>foresight.db</code></p>", unsafe_allow_html=True)
    with sqlite3.connect(pipeline.DB) as con:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='users' ORDER BY name")]
        info = pd.DataFrame([(n, con.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0]) for n in names], columns=["Table", "Rows"])
        c1, c2 = st.columns([1, 2])
        c1.dataframe(info, hide_index=True, use_container_width=True)
        sel = c2.selectbox("Look inside a table", names, index=names.index("risk"))
        c2.dataframe(pd.read_sql(f"SELECT * FROM {sel} LIMIT 50", con), hide_index=True, use_container_width=True)
        st.markdown("#### Try a query (SELECT only)")
        sql = st.text_area("SQL", "SELECT product, quadrant, sales_at_risk FROM risk ORDER BY sales_at_risk DESC LIMIT 5", height=70)
        if st.button("Run query"):
            if sql.strip().lower().startswith("select") and "users" not in sql.lower() and ";" not in sql.strip().rstrip(";"):
                try: st.dataframe(pd.read_sql(sql, con), hide_index=True, use_container_width=True)
                except Exception as e: st.error(f"Query problem: {e}")
            else:
                st.warning("Only simple SELECT queries are allowed.")
    st.markdown("#### Data problems found and fixed")
    st.dataframe(D["data_quality"], hide_index=True, use_container_width=True)
