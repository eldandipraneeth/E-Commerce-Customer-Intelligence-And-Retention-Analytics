# E-Commerce Customer Intelligence & Retention Analytics

![Power BI](https://img.shields.io/badge/Power_BI-F2C811?style=for-the-badge&logo=powerbi&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)

An end-to-end, full-stack Business Intelligence project designed to transform raw e-commerce transaction data into highly actionable executive insights. This project showcases the complete data lifecycle: synthetic data generation, ETL processing, advanced SQL window functions, Python-driven cohort analytics, and a Kimball Star Schema Power BI Dashboard.

---

## 🎯 Business Problem

E-Commerce companies frequently struggle with the "One-Time Buyer" problem—where soaring Customer Acquisition Costs (CAC) are not offset by returning revenue. This project was engineered to solve three critical business challenges:
1. **Revenue Concentration Risk:** Are we overly reliant on a small VIP cohort?
2. **Margin Erosion:** Are our highest-volume products actually driving profit, or are they empty-calorie sales?
3. **Churn Identification:** Exactly how many days post-purchase does a customer mathematically "churn"?

---

## 🏗️ Architecture & Data Pipeline

This project employs a robust, modular pipeline:

1. **Synthetic Data Generation (Python):** Generated over 60,000 realistic orders and 150,000 line items modeling real-world Indian e-commerce behavior (incorporating Diwali seasonality spikes and monsoon dips).
2. **ETL Pipeline (Pandas):** Cleaned the raw data, enforced foreign key integrity, and engineered the central `analytical_master_table`.
3. **Database Layer (PostgreSQL):** Imported the data into a strictly typed relational database for high-performance querying.
4. **Analytics Layer (SQL & Python):** Conducted RFM segmentations, Cohort matrices, and Profitability rankings.
5. **Visualization Layer (Power BI):** Ingested the analytical models via Power Query into the VertiPaq engine, applying a Star Schema data model to serve 6 interactive dashboards.

---

## 🧠 Core Analytical Modules

### 1. Customer Intelligence
Utilized data-driven RFM (Recency, Frequency, Monetary) modeling to categorize 20,000+ customers into VIP, Loyal, Regular, and At-Risk segments. 
* **Key Technique:** Calculated the 90th percentile of CLV to define VIPs dynamically, bypassing arbitrary thresholds.

### 2. Retention Analytics
Engineered a classic Month-0 to Month-12 Cohort Retention Matrix based strictly on the user's `first_purchase_date` (post-conversion) rather than `signup_date`.
* **Key Technique:** Deployed Seaborn Heatmaps and SQL `LAG()` window functions to calculate the median days between sequential purchases.

### 3. Advanced SQL Analytics
Translated Python data logic into highly optimized PostgreSQL queries leveraging Common Table Expressions (CTEs), `RANK()`, and `SUM() OVER(PARTITION BY)`.
* **Key Technique:** Calculated Pareto (80/20) Revenue Concentration mathematically within the database engine.

---

## 📊 Power BI Executive Dashboard Suite

The final reporting deliverable is a production-grade, 6-page interactive dashboard suite built in **Power BI Desktop**, backed by an optimized Kimball data model and explicit DAX measures.

### 📐 Architecture & Engineering Highlights
* **Optimized Data Model:** Analytical Master Table integrated with `customer_segments`, `cohort_retention_rates`, and a central `Dim_Date` table.
* **VertiPaq Memory Optimization:** High-cardinality Pareto visual is bounded by `Top N = 500` with a Categorical axis, preventing memory exhaustion when ranking 20,000 customers.
* **Production DAX Library:** Fully explicit measure library housed in `MeasureTable` utilizing `VAR / RETURN` formatting, `DIVIDE()` zero-division guards, and dynamic filter contexts.
* **Interactive Drillthrough UX:** Configured a dedicated, hidden **Customer Detail Table** enabling one-click drillthrough from high-level segment charts directly to individual customer transaction histories.
* **Cohort Retention Heatmap:** Full Month-0 to Month-23 retention triangle matrix with dynamic color-gradient conditional formatting and an accompanying retention decay curve.

### 🧠 Core Production DAX Measures

```dax
// 1. Cohort Retention Rate Calculation
[Cohort Retention %] = 
AVERAGE('cohort_retention_rates'[Retention Rate])

// 2. Cumulative Pareto Revenue Concentration
[Cumulative Revenue] = 
VAR CurrentRank = [Customer Rank by Revenue]
RETURN
CALCULATE(
    [Total Revenue],
    FILTER(
        ALL('customer_segments'[customer_id]),
        [Customer Rank by Revenue] <= CurrentRank
    )
)

[Pareto %] = 
DIVIDE(
    [Cumulative Revenue], 
    CALCULATE([Total Revenue], ALL('customer_segments'[customer_id])), 
    0
)

// 3. Time Intelligence YoY Growth
[Revenue YoY Growth %] = 
VAR CurrentRev = [Total Revenue]
VAR PriorYearRev = CALCULATE([Total Revenue], SAMEPERIODLASTYEAR('Dim_Date'[Date]))
RETURN 
DIVIDE(CurrentRev - PriorYearRev, PriorYearRev, 0)
```

All data model schemas, Power Query M transformation scripts, and DAX measures are documented in [`powerbi_assets/`](powerbi_assets/). The complete report can be viewed in Power BI Desktop (`ecommerce.pbix`).

---

## 💡 Key Business Insights

1. **The Pareto Concentration Risk:** The data definitively proves that the Top 20% of the customer base generates exactly 78.2% of total lifetime revenue, leaving the business highly vulnerable to VIP churn.
2. **The "One-Time" Stickiness Deficit:** ~64% of acquired users purchase once and never return. The median purchase interval for repeaters is extremely short (~35 days). 
    * *Recommendation:* Shift all retargeting ad-spend aggressively into the 15-45 day post-purchase window.
3. **The Margin Paradox:** Electronics dominate the top-line volume but carry drastically thinner gross margins compared to the Beauty/Clothing verticals.
    * *Recommendation:* Implement cross-category bundling algorithms at checkout to cross-pollinate margins.

---

## 📂 Folder Structure

```text
e-commerce/
├── data/
│   ├── raw/                 # Generated synthetic data
│   ├── processed/           # Cleaned ETL outputs
│   └── analytics/           # Final flattened outputs for Power BI
├── notebooks/               # EDA and Jupyter analytical write-ups
├── scripts/
│   ├── config.py            # Global variables and constants
│   ├── generate_*.py        # Python data generation modules
│   ├── etl/                 # Data cleaning and feature engineering
│   └── analytics/           # Python cohort and customer segmentation logic
├── sql/
│   ├── schema/              # DDL scripts for table creation
│   └── analytics/           # Advanced PostgreSQL CTEs and Window Functions
└── README.md
```

---

## 💻 Tech Stack
* **Languages:** Python 3.9, SQL (PostgreSQL), DAX, M Code
* **Libraries:** Pandas, NumPy, Matplotlib, Seaborn, Faker
* **BI & Tools:** Power BI Desktop, Jupyter Notebook

---

## 🚀 Installation & Usage

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/ecommerce-retention-analytics.git
   cd ecommerce-retention-analytics
   ```
2. **Install dependencies:**
   ```bash
   pip install pandas numpy matplotlib seaborn faker
   ```
3. **Run the Data Generation Pipeline:**
   ```bash
   python scripts/generate_all_data.py
   ```
4. **Run the ETL Pipeline:**
   ```bash
   python scripts/etl/clean_data.py
   python scripts/etl/engineer_features.py
   ```
5. **View Analytics:**
   * Open `notebooks/ecommerce_eda.ipynb` for exploratory findings.
   * Open `notebooks/retention_analysis.ipynb` for cohort analytics.
   * Review `sql/analytics/` for the advanced PostgreSQL queries.
