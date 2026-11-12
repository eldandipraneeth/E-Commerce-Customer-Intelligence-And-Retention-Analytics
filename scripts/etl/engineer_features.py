"""
engineer_features.py — Feature Engineering Module

Generates feature-rich datasets and a flattened Analytical Master Table (AMT).

Features Engineered:
1. Item-level profitability: gross_profit, gross_margin_pct
2. Order-level temporal: order_month, order_quarter, order_year, order_weekday, is_weekend_order
3. Customer-level RFM & retention: total_orders, total_revenue, first_purchase_date, 
   latest_purchase_date, days_since_last_purchase, customer_tenure_days, 
   purchase_frequency, is_repeat_customer
"""

import os
import pandas as pd
import numpy as np

def engineer_features(processed_dir: str, analytics_dir: str) -> None:
    """Reads processed data, engineers features, and creates the Analytical Master Table."""
    
    os.makedirs(analytics_dir, exist_ok=True)
    
    # ---------------------------------------------------------
    # 1. LOAD PROCESSED DATA
    # ---------------------------------------------------------
    dim_date = pd.read_csv(os.path.join(processed_dir, "dim_date.csv"))
    categories = pd.read_csv(os.path.join(processed_dir, "categories.csv"))
    products = pd.read_csv(os.path.join(processed_dir, "products.csv"))
    customers = pd.read_csv(os.path.join(processed_dir, "customers.csv"))
    orders = pd.read_csv(os.path.join(processed_dir, "orders.csv"))
    order_items = pd.read_csv(os.path.join(processed_dir, "order_items.csv"))

    # Convert dates
    customers["signup_date"] = pd.to_datetime(customers["signup_date"])
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    
    # Define "Analysis Reference Date" as the maximum order_date in the dataset
    ANALYSIS_DATE = orders["order_date"].max()
    print(f"  [info] Analysis Reference Date set to: {ANALYSIS_DATE.date()}")

    # ---------------------------------------------------------
    # 2. ITEM LEVEL: Profitability Features
    # ---------------------------------------------------------
    # gross_profit = line_total - (quantity * unit_cost)
    order_items = order_items.merge(products[["product_id", "unit_cost"]], on="product_id", how="left")
    order_items["gross_profit"] = order_items["line_total"] - (order_items["quantity"] * order_items["unit_cost"])
    order_items["gross_profit"] = order_items["gross_profit"].round(2)
    
    # gross_margin_pct = gross_profit / line_total
    # Use np.where to avoid division by zero (if line_total is exactly 0)
    order_items["gross_margin_pct"] = np.where(
        order_items["line_total"] > 0,
        np.round(order_items["gross_profit"] / order_items["line_total"], 4),
        0.0
    )
    # We no longer need unit_cost in the order_items table
    order_items.drop(columns=["unit_cost"], inplace=True)

    # ---------------------------------------------------------
    # 3. ORDER LEVEL: Temporal Features
    # ---------------------------------------------------------
    # Using dim_date is best practice in data warehousing, but pandas dt accessor is faster here.
    # We will use pandas dt accessor to create order temporal features.
    orders["order_month"] = orders["order_date"].dt.month
    orders["order_quarter"] = orders["order_date"].dt.quarter
    orders["order_year"] = orders["order_date"].dt.year
    orders["order_weekday"] = orders["order_date"].dt.weekday + 1 # 1=Mon, 7=Sun (ISO)
    orders["is_weekend_order"] = orders["order_weekday"].isin([6, 7])

    # ---------------------------------------------------------
    # 4. CUSTOMER LEVEL: Aggregations & Retention Features
    # ---------------------------------------------------------
    # Only consider 'Completed' orders for revenue and purchase dates
    completed_orders = orders[orders["order_status"] == 'Completed']
    
    cust_agg = completed_orders.groupby("customer_id").agg(
        total_orders=("order_id", "count"),
        total_revenue=("total_amount", "sum"),
        first_purchase_date=("order_date", "min"),
        latest_purchase_date=("order_date", "max")
    ).reset_index()

    # Merge aggregations back to customers
    customers_fe = customers.merge(cust_agg, on="customer_id", how="left")
    
    # Fill NAs for customers with no completed orders
    customers_fe["total_orders"] = customers_fe["total_orders"].fillna(0).astype(int)
    customers_fe["total_revenue"] = customers_fe["total_revenue"].fillna(0.0).round(2)
    
    # Retention Features
    customers_fe["is_repeat_customer"] = customers_fe["total_orders"] > 1
    
    customers_fe["days_since_last_purchase"] = (ANALYSIS_DATE - customers_fe["latest_purchase_date"]).dt.days
    customers_fe["customer_tenure_days"] = (ANALYSIS_DATE - customers_fe["signup_date"]).dt.days
    
    # purchase_frequency = total_orders / tenure_days
    # Use np.where to prevent divide by zero for brand new signups
    customers_fe["purchase_frequency"] = np.where(
        customers_fe["customer_tenure_days"] > 0,
        np.round(customers_fe["total_orders"] / customers_fe["customer_tenure_days"], 4),
        customers_fe["total_orders"] # if tenure is 0, freq is just total_orders
    )

    # ---------------------------------------------------------
    # 5. EXPORT FEATURE ENGINEERED CORE TABLES
    # ---------------------------------------------------------
    # Exporting enhanced dimensions and facts if analysts want star-schema access
    order_items.to_csv(os.path.join(analytics_dir, "fact_order_items.csv"), index=False)
    orders.to_csv(os.path.join(analytics_dir, "fact_orders.csv"), index=False)
    customers_fe.to_csv(os.path.join(analytics_dir, "dim_customers_enriched.csv"), index=False)
    
    # ---------------------------------------------------------
    # 6. ANALYTICAL MASTER TABLE (AMT)
    # ---------------------------------------------------------
    print("  [info] Building Analytical Master Table...")
    # Join order_items + orders
    amt = order_items.merge(orders, on="order_id", how="left")
    
    # Join + products & categories
    amt = amt.merge(products, on="product_id", how="left")
    amt = amt.merge(categories, on="category_id", how="left")
    
    # Join + customers_fe
    amt = amt.merge(customers_fe, on="customer_id", how="left")
    
    # Join + dim_date on order_date
    # Convert order_date to string to match full_date string, or use datetime
    amt["order_date_str"] = amt["order_date"].dt.strftime('%Y-%m-%d')
    # Since dim_date is loaded from CSV, full_date is string
    amt = amt.merge(dim_date, left_on="order_date_str", right_on="full_date", how="left")
    amt.drop(columns=["order_date_str", "full_date"], inplace=True)
    
    # Save AMT
    amt_path = os.path.join(analytics_dir, "analytical_master_table.csv")
    amt.to_csv(amt_path, index=False)
    
    print(f"  [OK] Feature engineering complete. AMT saved to: {amt_path} ({len(amt):,} rows)")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    engineer_features(
        processed_dir=os.path.join(base_dir, "data", "processed"),
        analytics_dir=os.path.join(base_dir, "data", "analytics")
    )
