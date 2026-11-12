"""
generate_all_data.py — Master orchestrator for the e-commerce data generation
pipeline.

Calls each generator module in dependency order, saves all CSVs, and prints
a comprehensive summary report.

DEPENDENCY ORDER
────────────────
  ① dim_date      (no deps)
  ② categories    (no deps)
  ③ products      (needs categories)
  ④ customers     (no deps)
  ⑤ orders        (needs customers)
  ⑥ order_items   (needs orders + products → updates orders financials)

USAGE
─────
    cd e-commerce/scripts
    python generate_all_data.py

OUTPUT
──────
    data/raw/dim_date.csv       (731 rows)
    data/raw/categories.csv     (14 rows)
    data/raw/products.csv       (500 rows)
    data/raw/customers.csv      (20,000 rows)
    data/raw/orders.csv         (~60,000 rows)
    data/raw/order_items.csv    (~150,000+ rows)
"""

import os
import sys
import time

import numpy as np
import pandas as pd

# ── Ensure scripts/ is on the path so config can be imported ─────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import RANDOM_SEED, OUTPUT_DIR, TARGET_CUSTOMERS, TARGET_ORDERS, TARGET_ORDER_ITEMS_MIN

# ── Import all generators ────────────────────────────────────────────────────
from generate_dim_date import generate_dim_date
from generate_categories import generate_categories
from generate_products import generate_products
from generate_customers import generate_customers
from generate_orders import generate_orders
from generate_order_items import generate_order_items


def _divider(title: str):
    """Print a visual section divider."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def main():
    """Run the full data generation pipeline."""

    pipeline_start = time.time()
    print("=" * 70)
    print("  E-COMMERCE DATA GENERATION PIPELINE")
    print(f"  Seed: {RANDOM_SEED} | Output: {OUTPUT_DIR}")
    print("=" * 70)

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Initialize the shared numpy random state
    rng = np.random.RandomState(RANDOM_SEED)

    # ── STEP 1: dim_date ─────────────────────────────────────────────────────
    _divider("1. Generating dim_date")
    t0 = time.time()
    dim_date_df = generate_dim_date()
    dim_date_df.to_csv(os.path.join(OUTPUT_DIR, "dim_date.csv"), index=False)
    print(f"   [OK] {len(dim_date_df):,} rows  |  {time.time()-t0:.1f}s")
    print(f"   Date range: {dim_date_df['full_date'].min()} -> {dim_date_df['full_date'].max()}")

    # ── STEP 2: categories ───────────────────────────────────────────────────
    _divider("2. Generating categories")
    t0 = time.time()
    categories_df = generate_categories()
    categories_df.to_csv(os.path.join(OUTPUT_DIR, "categories.csv"), index=False)
    print(f"   [OK] {len(categories_df):,} rows  |  {time.time()-t0:.1f}s")
    for _, row in categories_df.iterrows():
        print(f"     {row['category_id']:2d}. {row['category_name']} -> {row['sub_category']}")

    # ── STEP 3: products ─────────────────────────────────────────────────────
    _divider("3. Generating products")
    t0 = time.time()
    products_df = generate_products(rng)
    products_df.to_csv(os.path.join(OUTPUT_DIR, "products.csv"), index=False)
    print(f"   [OK] {len(products_df):,} rows  |  {time.time()-t0:.1f}s")
    print(f"   Price range: INR {products_df['list_price'].min():,.2f} - INR {products_df['list_price'].max():,.2f}")
    print(f"   Avg margin:  {((products_df['list_price'] - products_df['unit_cost']) / products_df['list_price']).mean():.1%}")
    print(f"   Unique brands: {products_df['brand'].nunique()}")

    # ── STEP 4: customers ────────────────────────────────────────────────────
    _divider("4. Generating customers")
    t0 = time.time()
    customers_df = generate_customers(rng)
    customers_df.to_csv(os.path.join(OUTPUT_DIR, "customers.csv"), index=False)
    print(f"   [OK] {len(customers_df):,} rows  |  {time.time()-t0:.1f}s")
    print(f"   Signup range: {customers_df['signup_date'].min()} -> {customers_df['signup_date'].max()}")
    print(f"\n   Region distribution:")
    for region, count in customers_df['region'].value_counts().items():
        pct = count / len(customers_df) * 100
        print(f"     {region:8s}: {count:6,d} ({pct:5.1f}%)")

    # ── STEP 5: orders ───────────────────────────────────────────────────────
    _divider("5. Generating orders")
    t0 = time.time()
    orders_df = generate_orders(customers_df, rng)
    # NOTE: orders.csv is saved AFTER step 6 updates financial columns
    print(f"   [OK] {len(orders_df):,} order skeletons  |  {time.time()-t0:.1f}s")
    print(f"   Date range: {orders_df['order_date'].min()} -> {orders_df['order_date'].max()}")
    print(f"\n   Status distribution:")
    for status, count in orders_df['order_status'].value_counts().items():
        pct = count / len(orders_df) * 100
        print(f"     {status:12s}: {count:6,d} ({pct:5.1f}%)")
    print(f"\n   Payment methods:")
    for method, count in orders_df['payment_method'].value_counts().items():
        pct = count / len(orders_df) * 100
        print(f"     {method:12s}: {count:6,d} ({pct:5.1f}%)")

    # ── STEP 6: order_items + finalize order financials ───────────────────────
    _divider("6. Generating order_items + finalizing order financials")
    t0 = time.time()
    order_items_df, orders_df = generate_order_items(orders_df, products_df, rng)
    # Save BOTH the finalized orders and order_items
    orders_df.to_csv(os.path.join(OUTPUT_DIR, "orders.csv"), index=False)
    order_items_df.to_csv(os.path.join(OUTPUT_DIR, "order_items.csv"), index=False)
    print(f"   [OK] {len(order_items_df):,} line items  |  {time.time()-t0:.1f}s")
    print(f"   Avg items/order: {len(order_items_df)/len(orders_df):.2f}")

    # ══════════════════════════════════════════════════════════════════════════
    #  PIPELINE SUMMARY
    # ══════════════════════════════════════════════════════════════════════════
    elapsed = time.time() - pipeline_start
    _divider("PIPELINE SUMMARY")

    # Row counts
    tables = {
        "dim_date":    dim_date_df,
        "categories":  categories_df,
        "products":    products_df,
        "customers":   customers_df,
        "orders":      orders_df,
        "order_items": order_items_df,
    }
    print(f"\n   {'Table':<15s} {'Rows':>10s}  {'Target':>10s}  Status")
    print(f"   {'-'*15} {'-'*10}  {'-'*10}  {'-'*8}")
    targets = {
        "dim_date":    731,
        "categories":  14,
        "products":    500,
        "customers":   TARGET_CUSTOMERS,
        "orders":      TARGET_ORDERS,
        "order_items": TARGET_ORDER_ITEMS_MIN,
    }
    for name, df in tables.items():
        target = targets[name]
        actual = len(df)
        if name == "order_items":
            status = "[OK]" if actual >= target else "[FAIL]"
        else:
            # Allow ±2% tolerance for orders (tuning is approximate)
            if name == "orders":
                status = "[OK]" if abs(actual - target) / target < 0.03 else "[FAIL]"
            else:
                status = "[OK]" if actual == target else "[FAIL]"
        print(f"   {name:<15s} {actual:>10,d}  {target:>10,d}  {status}")

    # Revenue summary (completed orders only)
    completed = orders_df[orders_df['order_status'] == 'Completed']
    print(f"\n   Revenue Summary (Completed orders only):")
    print(f"     Total Revenue:      INR {completed['total_amount'].sum():>15,.2f}")
    print(f"     Avg Order Value:    INR {completed['total_amount'].mean():>15,.2f}")
    print(f"     Total Discounts:    INR {completed['discount_amount'].sum():>15,.2f}")
    print(f"     Total Shipping:     INR {completed['shipping_cost'].sum():>15,.2f}")

    # Customer behavior
    orders_per_customer = orders_df.groupby('customer_id').size()
    print(f"\n   Customer Behavior:")
    print(f"     One-time (1 order):    {(orders_per_customer == 1).sum():,d}"
          f" ({(orders_per_customer == 1).mean():.1%})")
    print(f"     Occasional (2-5):      {((orders_per_customer >= 2) & (orders_per_customer <= 5)).sum():,d}"
          f" ({((orders_per_customer >= 2) & (orders_per_customer <= 5)).mean():.1%})")
    print(f"     Regular (6-10):        {((orders_per_customer >= 6) & (orders_per_customer <= 10)).sum():,d}"
          f" ({((orders_per_customer >= 6) & (orders_per_customer <= 10)).mean():.1%})")
    print(f"     Power (11+):           {(orders_per_customer >= 11).sum():,d}"
          f" ({(orders_per_customer >= 11).mean():.1%})")

    # Pareto check
    product_revenue = (
        order_items_df
        .merge(orders_df[orders_df['order_status'] == 'Completed'][['order_id']], on='order_id')
        .groupby('product_id')['line_total'].sum()
        .sort_values(ascending=False)
    )
    top_20pct_count = int(len(product_revenue) * 0.20)
    top_20pct_revenue = product_revenue.head(top_20pct_count).sum()
    total_revenue = product_revenue.sum()
    print(f"\n   Pareto Check:")
    print(f"     Top 20% products ({top_20pct_count} products) -> "
          f"{top_20pct_revenue/total_revenue:.1%} of line-item revenue")

    # is_first_order check
    first_order_count = orders_df['is_first_order'].sum()
    customers_with_completed = orders_df[orders_df['order_status'] == 'Completed']['customer_id'].nunique()
    print(f"\n   is_first_order: {first_order_count:,d} flagged "
          f"(expect ~ {customers_with_completed:,d} customers with completed orders)")

    # File sizes
    print(f"\n   Output files:")
    for name in tables:
        fpath = os.path.join(OUTPUT_DIR, f"{name}.csv")
        size_mb = os.path.getsize(fpath) / (1024 * 1024)
        print(f"     {name}.csv -> {size_mb:.1f} MB")

    print(f"\n   Total pipeline time: {elapsed:.1f}s")
    print(f"\n   [!] Run 'python validate_data.py' to verify data quality.\n")


if __name__ == "__main__":
    main()
