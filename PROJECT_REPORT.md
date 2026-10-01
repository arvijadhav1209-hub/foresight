# Project FORESIGHT: Demand & Inventory Intelligence Platform
## Comprehensive Internship Project Report

---

### Project Information
- **Project Title:** Project FORESIGHT – Demand & Inventory Intelligence
- **Organization:** Zidio Development Internship Program
- **Client / Domain:** NorthBay Living (Everyday Home Products & Consumer Goods)
- **Candidate Name:** Arati Jadhav
- **Candidate Email:** aratijadhav710@gmail.com
- **GitHub Repository:** [https://github.com/arvijadhav1209-hub/foresight](https://github.com/arvijadhav1209-hub/foresight)
- **Live Deployment URL:** [https://foresight-gctc.onrender.com](https://foresight-gctc.onrender.com)
- **Tech Stack:** Python 3.11+, Scikit-Learn, Pandas, NumPy, SQLite, Streamlit, Plotly, Render PaaS, Git/GitHub

---

## 1. Executive Summary

In omni-channel retail operations, inventory management directly drives business profitability. Retailers consistently grapple with two opposing financial risks:
1. **Stockouts**: Depleted inventory leads to immediate revenue loss, disappointed consumers, and diminished brand equity.
2. **Overstocking**: Excessive inventory ties up critical working capital, inflates warehousing costs, and ultimately necessitates aggressive markdowns that erode margins.

**Project FORESIGHT** is an enterprise-grade demand forecasting and inventory risk intelligence platform engineered for **NorthBay Living**, encompassing 12 core home product SKUs across a 2-year operational history. The platform combines:
- An automated data hygiene and ETL pipeline standardizing disparate daily transactional feeds.
- A machine learning demand forecasting engine using `HistGradientBoostingRegressor`, delivering a **14.5% WAPE** across a 6-week forward horizon (**+19.7% accuracy improvement** over the seasonal-naive baseline).
- An operational risk-scoring matrix quantifying stockout probabilities and excess inventory depth at a 90% service level.
- Financial quantification calculating **₹7.3 Lakhs in sales-at-risk** and **₹2.1 Lakhs in excess locked capital**.
- A secure, role-based interactive planning dashboard built with Streamlit and deployed globally on Render.

---

## 2. Problem Statement & Business Objectives

### 2.1 The Retail Inventory Dilemma
NorthBay Living operates 12 high-velocity everyday home products (Kitchen, Bedding, Home Decor, Small Appliances). Operations managers face distinct challenges:
- **Lead-time vulnerabilities**: Product lead times range from 7 to 30 days. Reordering too late triggers stockouts.
- **Seasonality & Promotions**: Holiday spikes (Diwali, New Year) and flash promotions distort standard moving averages.
- **Capital Inefficiency**: Products like Cotton Bedsheets and Wall Clocks accumulate weeks of excess stock, trapping hundreds of thousands of rupees in unliquidated inventory.

### 2.2 Core Project Objectives
| Milestone | Description | Key Deliverable |
|---|---|---|
| **D1: Data Pipeline & Hygiene** | Ingest 4 disparate CSV sources, resolve dirty data, deduplicate, aggregate weekly, and index in SQLite. | Clean SQLite schema with automated audit logging. |
| **D3: Machine Learning Forecast** | 6-week rolling horizon forecast per SKU using leak-free historical & calendar features. | Backtested model outperforming baseline WAPE. |
| **D4: Inventory Risk Scoring** | Multi-attribute decision rules calculating stockout risk, overstock duration, and ₹ at stake. | 4-Quadrant decision matrix & recommended actions. |
| **D5: Web Application & UI** | Interactive, executive-ready dashboard with authentication and role-based views. | Live Streamlit cloud app deployed on Render. |

---

## 3. System Architecture & Data Pipeline (D1)

### 3.1 Architectural Flow
```
[Raw CSVs: Sales, Master, Calendar, Inventory]
                     │
                     ▼
       [Data Cleaning & Validation (D1)]
   - Deduplication (Date + SKU)
   - Missing Price & Units Recovery
   - Category Normalization
                     │
                     ▼
          [SQLite Database: foresight.db]
   - sales_daily, weekly_sales, sku_master, inventory
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
[ML Forecasting Engine (D3)]  [Risk Decision Matrix (D4)]
- Gradient Boosting            - 90% Service Level Safety Stock
- Rolling-Origin Backtesting   - Cover Ratios & Weeks of Supply
- 80% Confidence Intervals     - ₹ Sales at Risk & Locked Capital
         └───────────┬───────────┘
                     ▼
     [Interactive Streamlit Dashboard (D5)]
- Overview, Forecast Horizon, Decision Grid, Actions
- PBKDF2 Password Hashing & Role-Based Access
                     │
                     ▼
           [Render Cloud Deployment]
```

### 3.2 Data Ingestion & Hygiene Measures
The cleaning module (`src/pipeline.py`) systematically resolves operational data anomalies:
1. **Duplicate Records**: Identified and eliminated duplicate transaction rows sharing identical `(date, sku_id)` keys.
2. **Missing Unit Prices**: Replaced missing unit prices by cross-referencing `sku_master.list_price` and applying promotional discounts (10% discount on promo days).
3. **Missing Units Sold**: Derived missing units through the accounting identity:
   $$\text{units\_sold} = \left\lfloor \frac{\text{revenue}}{\text{unit\_price}} \right\rceil$$
4. **String Normalization**: Trimmed whitespace and converted category labels to title case.
5. **Calendar Alignment**: Grouped daily sales into Monday-aligned weekly aggregation buckets (`weekly_sales`).
6. **SQLite Storage & Indexing**: Normalized tables are indexed on `(sku_id, date)` and `(sku_id, week_start)` for high-throughput query execution.

---

## 4. Machine Learning Demand Forecasting (D3)

### 4.1 Methodology & Forecast Formulation
- **Forecast Horizon ($H$)**: 6 weeks into the future.
- **Primary Algorithm**: `HistGradientBoostingRegressor` (Scikit-Learn).
  - Hyperparameters: `max_iter=200`, `learning_rate=0.05`, `max_depth=4`, `random_state=42`.
- **Baseline Benchmark**: Seasonal-Naive Model (demand from the corresponding week 52 weeks prior).

### 4.2 Leak-Free Feature Engineering
To guarantee zero look-ahead bias, features are computed strictly using data available up to forecast origin date $t$:
- `last1`: Units sold in the immediately preceding week ($t-1$).
- `m4`, `m8`: 4-week and 8-week rolling moving averages of demand.
- `ly`: Demand in the identical week last year ($t-52$).
- `ly3`: 3-week centered moving average around last year's corresponding week ($t-53$ to $t-50$).
- `promo`: Count of promotional days planned in the upcoming week (known from the marketing calendar).
- `hol`: Count of official public holidays in the forecast week.
- `woy`: ISO calendar week of the year (1 to 52) to capture annual seasonality patterns.

### 4.3 Evaluation Metric & Backtest Results
Model evaluation uses **Weighted Absolute Percentage Error (WAPE)**:
$$\text{WAPE} = \frac{\sum_{i=1}^N |y_i - \hat{y}_i|}{\sum_{i=1}^N y_i}$$

A 6-round rolling-origin backtest ($6 \times 6 = 36$ test evaluations per SKU) yielded:

| Evaluation Metric | Seasonal-Naive Baseline | Gradient Boosting Model | Performance Delta |
|---|---|---|---|
| **WAPE (Lower is Better)** | **18.00%** | **14.46%** | **19.70% Relative Improvement** |
| **Forecast Bias** | — | **-0.015** | Near-zero systematic bias |
| **Model Selection Decision** | Discarded | **Selected for Production** | Model strictly selected |

### 4.4 Prediction Confidence Intervals
Forecast uncertainty is quantified through empirical error distribution modeling. By analyzing backtest error ratios:
$$\text{ratio} = \frac{y - \hat{y}}{\hat{y}}$$
The 10th and 90th percentiles are extracted ($q_{10}, q_{90}$) to establish calibrated 80% confidence envelopes:
$$\text{Lower Bound} = \max\left(0, \hat{y} \cdot (1 + q_{10})\right), \quad \text{Upper Bound} = \hat{y} \cdot (1 + q_{90})$$

---

## 5. Inventory Risk & Operational Decision Matrix (D4)

### 5.1 Mathematical Formulations
1. **Demand in Lead Time ($\text{Demand}_{\text{lead}}$)**:
   For lead time $L$ days, converted to fractional weeks $w = L / 7$:
   $$\text{Demand}_{\text{lead}} = \sum_{t=1}^{\lfloor w \rfloor} \hat{y}_t + (w - \lfloor w \rfloor) \cdot \hat{y}_{\lceil w \rceil}$$

2. **Safety Stock ($\text{SS}$)**:
   Calibrated for a **90% Cycle Service Level** ($Z = 1.28$):
   $$\text{SS} = Z \cdot \sigma_{13} \cdot \sqrt{w}$$
   *(where $\sigma_{13}$ is the standard deviation of weekly demand over the prior 13 weeks).*

3. **Total Replenishment Need**:
   $$\text{Need} = \text{Demand}_{\text{lead}} + \text{SS}$$

4. **Supply & Cover Ratio**:
   $$\text{Supply} = \text{Stock on Hand} + \text{Stock on Order}$$
   $$\text{Cover Ratio} = \frac{\text{Supply}}{\max(\text{Need}, 0.1)}$$
   $$\text{Stockout Score} = \text{clip}(1.5 - \text{Cover Ratio}, 0, 1)$$

5. **Weeks of Supply & Overstock Score**:
   $$\text{Weeks of Supply} = \frac{\text{Supply}}{\text{Average Weekly Forecast}}$$
   $$\text{Overstock Score} = \text{clip}\left(\frac{\text{Weeks of Supply} - 2}{8}, 0, 1\right)$$

### 5.2 The 4-Quadrant Operational Decision Matrix
Using a threshold boundary of $0.50$ across Stockout and Overstock scores:

```
          Stockout Score (SO)
               ▲
               │
    Reorder    │    Watch /
      Now      │    Volatile
(SO ≥ 0.5,     │  (SO ≥ 0.5,
 OV < 0.5)     │   OV ≥ 0.5)
───────────────┼───────────────► Overstock Score (OV)
    Healthy    │    Markdown /
(SO < 0.5,     │      Clear
 OV < 0.5)     │  (SO < 0.5,
               │   OV ≥ 0.5)
```

| Quadrant | Condition | Operational Directive | Financial Impact |
|---|---|---|---|
| **🛒 Reorder now** | $\text{SO} \ge 0.5, \text{OV} < 0.5$ | Raise immediate purchase order: $\lceil \max(0, \text{Need} + 2\cdot\bar{y} - \text{Supply}) \rceil$ | Prevents lost revenue ($\text{Sales at Risk}$) |
| **🏷️ Markdown / clear** | $\text{SO} < 0.5, \text{OV} \ge 0.5$ | Initiate promotional pricing or bundle campaigns | Frees trapped working capital |
| **👀 Watch / volatile** | $\text{SO} \ge 0.5, \text{OV} \ge 0.5$ | Manual review: Long lead time or high demand variance | Reduces dual supply-demand risk |
| **✅ Healthy** | $\text{SO} < 0.5, \text{OV} < 0.5$ | Normal operations; inventory within safe buffer bounds | Optimal capital efficiency |

### 5.3 SKU-Level Risk Scoring Results

| Product Name | Category | Weeks of Stock | Cover Ratio | Decision Quadrant | Sales at Risk (₹) | Locked Capital (₹) | Suggested Order |
|---|---|---|---|---|---|---|---|
| **Steel Water Bottle** | Kitchen | 0.9 | 0.64 | **Reorder now** | ₹18,772 | ₹0 | 251 units |
| **Non-stick Pan** | Kitchen | 1.0 | 0.42 | **Reorder now** | ₹98,713 | ₹0 | 179 units |
| **Woolen Blanket** | Bedding | 1.0 | 0.31 | **Reorder now** | ₹2,39,878 | ₹0 | 134 units |
| **Electric Kettle** | Small Appliances | 2.1 | 0.43 | **Reorder now** | ₹2,19,916 | ₹0 | 185 units |
| **Room Fan** | Small Appliances | 4.2 | 0.76 | **Reorder now** | ₹1,10,100 | ₹0 | 85 units |
| **Mixer Grinder** | Small Appliances | 6.5 | 0.95 | **Watch / volatile** | ₹40,186 | ₹37,800 | 47 units |
| **Cotton Bedsheet** | Bedding | 7.9 | 3.40 | **Markdown / clear** | ₹0 | ₹1,20,000 | 0 units |
| **Wall Clock** | Home Decor | 14.1 | 6.00 | **Markdown / clear** | ₹0 | ₹56,256 | 0 units |
| **Ceramic Coffee Mug** | Kitchen | 3.0 | 1.93 | **Healthy** | ₹0 | ₹0 | 0 units |
| **Soft Pillow Set** | Bedding | 3.9 | 1.74 | **Healthy** | ₹0 | ₹0 | 0 units |
| **Table Lamp** | Home Decor | 4.3 | 1.85 | **Healthy** | ₹0 | ₹0 | 0 units |
| **Scented Candle** | Home Decor | 2.8 | 1.77 | **Healthy** | ₹0 | ₹0 | 0 units |
| **TOTAL** | — | — | — | **5 Reorder, 2 Clear** | **₹7,27,565** | **₹2,14,056** | **882 units** |

---

## 6. Interactive Web Dashboard & Security (D5)

### 6.1 User Experience Architecture
The front-end is implemented in **Streamlit** with a tailored corporate theme, glassmorphic styling, and interactive Plotly components:
- **Executive Overview**: High-level KPI cards displaying Reorder Count (5), Clear Count (2), Total Sales at Risk (₹7.3L), and Locked Capital (₹2.1L). Includes a global stock health distribution donut chart.
- **Forecast Horizon**: Detailed time-series visualizer illustrating historical actual sales, ML predictions, and shaded 80% empirical confidence bands for any selected SKU.
- **Decision Grid**: Interactive 4-quadrant scatter chart plotting Stockout Score vs. Overstock Score.
- **Action List**: Operations table generating precise reorder unit quantities and markdown clearance recommendations.
- **Database Explorer**: Full audit visibility into raw tables, data quality logs, and backtest scores.

### 6.2 Security Implementation
- User credentials are encrypted using **PBKDF2-HMAC-SHA256** with 100,000 hash iterations and unique 16-character hexadecimal salts per user.
- Passwords are never stored in plaintext.
- Preconfigured accounts:
  - **Admin**: `admin` / `foresight123`
  - **Operations**: `ops` / `northbay2025`

---

## 7. Cloud Deployment & DevOps

### 7.1 Infrastructure Configuration
- **PaaS Provider**: Render Cloud Application Services.
- **Public Endpoint**: [https://foresight-gctc.onrender.com](https://foresight-gctc.onrender.com)
- **Source Code Repository**: [https://github.com/arvijadhav1209-hub/foresight](https://github.com/arvijadhav1209-hub/foresight)
- **Infrastructure-as-Code (`render.yaml`)**:
  ```yaml
  services:
    - type: web
      name: foresight
      runtime: python
      plan: free
      buildCommand: pip install -r requirements.txt
      startCommand: streamlit run app.py --server.port $PORT --server.address 0.0.0.0
      envVars:
        - key: PYTHON_VERSION
          value: 3.11.9
  ```
- **Process Orchestration (`Procfile`)**:
  ```text
  web: streamlit run app.py --server.port $PORT --server.address 0.0.0.0
  ```
- **Self-Healing Database Initialization**: `app.py` automatically checks for `foresight.db` presence upon container boot. If absent on a clean cloud instance, `src.run.run_all()` triggers automatically to generate data, clean, train models, score risk, and seed the database in under 30 seconds.

---

## 8. Business Impact & Key Takeaways

1. **Revenue Protection**: Quantified and flagged **₹7.28 Lakhs in potential lost sales** across 5 stockout-prone products, preventing customer churn.
2. **Working Capital Optimization**: Identified **₹2.14 Lakhs in surplus capital** trapped in overstocked Bedding and Home Decor inventory, enabling proactive markdowns before product obsolescence.
3. **Accuracy Enhancement**: Delivered a **19.7% reduction in forecasting error (WAPE)** through gradient-boosted regression compared to legacy seasonal-naive heuristics.
4. **Operational Efficiency**: Eliminated manual spreadsheet estimations by providing one-click purchase order recommendations.

---

## 9. Conclusion & Future Roadmap

**Project FORESIGHT** successfully bridges data science, machine learning, and retail supply chain operations into an intuitive, production-deployed solution. Future enhancements include:
- **ERP / EDI Integration**: Direct automated webhook dispatch of purchase orders to supplier APIs.
- **Deep Learning Architectures**: Evaluation of Temporal Fusion Transformers (TFT) and N-BEATS for cross-SKU demand correlation.
- **Dynamic Pricing Engine**: Automated markdown pricing elasticity models to maximize revenue during clearance periods.

---

*Submitted in partial fulfillment of the Internship Requirements at Zidio Development.*  
**Author:** Arati Jadhav  
**Date:** October 2026
