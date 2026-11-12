"""
validate_data.py — Validation script to prove data quality of generated CSVs.

Verifies:
1. Row counts meet targets
2. Foreign key integrity across all files
3. Revenue reconciliation (total_amount = Σline_total - discount_amount + shipping_cost)
4. Temporal integrity (order_date >= signup_date)
5. Customer distribution targets (e.g., segment sizes)
"""

import os
import sys
import pandas as pd
import numpy as np

# Ensure scripts/ is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import OUTPUT_DIR, TARGET_CUSTOMERS, TARGET_ORDERS, TARGET_ORDER_ITEMS_MIN, BEHAVIOR_DIST

def check_fk(child_df, child_col, parent_df, parent_col, name=""):
    """Check that all values in child_col exist in parent_col."""
    orphans = child_df[~child_df[child_col].isin(parent_df[parent_col])]
    if len(orphans) == 0:
        print(f"  [PASS] {name}: All {len(child_df):,} rows valid.")
        return True
    else:
        print(f"  [FAIL] {name}: {len(orphans):,} orphan rows found!")
        return False

def main():
    print("=" * 70)
    print("  E-COMMERCE DATA VALIDATION")
    print("=" * 70)

    # Load data
    try:
        dim_date = pd.read_csv(os.path.join(OUTPUT_DIR, "dim_date.csv"))
        categories = pd.read_csv(os.path.join(OUTPUT_DIR, "categories.csv"))
        products = pd.read_csv(os.path.join(OUTPUT_DIR, "products.csv"))
        customers = pd.read_csv(os.path.join(OUTPUT_DIR, "customers.csv"))
        orders = pd.read_csv(os.path.join(OUTPUT_DIR, "orders.csv"))
        order_items = pd.read_csv(os.path.join(OUTPUT_DIR, "order_items.csv"))
    except FileNotFoundError as e:
        print(f"Error loading files: {e}")
        print("Please run `python generate_all_data.py` first.")
        return

    # ---------------------------------------------------------
    # 1. Row Counts
    # ---------------------------------------------------------
    print("\n1. ROW COUNTS")
    print("-" * 40)
    counts = {
        "dim_date": (len(dim_date), 731, True), # Exact
        "categories": (len(categories), 14, True), # Exact
        "products": (len(products), 500, True), # Exact
        "customers": (len(customers), TARGET_CUSTOMERS, True), # Exact
        "orders": (len(orders), TARGET_ORDERS, False), # Approx
        "order_items": (len(order_items), TARGET_ORDER_ITEMS_MIN, False), # Min
    }
    
    for name, (actual, target, exact) in counts.items():
        if exact:
            status = "PASS" if actual == target else "FAIL"
        elif name == "order_items":
            status = "PASS" if actual >= target else "FAIL"
        else: # orders
            status = "PASS" if abs(actual - target)/target < 0.05 else "FAIL"
            
        print(f"  [{status}] {name:12s} : {actual:>10,d} (Target: {target:>10,d})")

    # ---------------------------------------------------------
    # 2. Foreign Key Integrity
    # ---------------------------------------------------------
    print("\n2. FOREIGN KEY INTEGRITY")
    print("-" * 40)
    
    # products -> categories
    check_fk(products, "category_id", categories, "category_id", "products -> categories")
    
    # orders -> customers
    check_fk(orders, "customer_id", customers, "customer_id", "orders -> customers")
    
    # order_items -> orders
    check_fk(order_items, "order_id", orders, "order_id", "order_items -> orders")
    
    # order_items -> products
    check_fk(order_items, "product_id", products, "product_id", "order_items -> products")
    
    # orders.order_date -> dim_date.full_date
    check_fk(orders, "order_date", dim_date, "full_date", "orders.order_date -> dim_date")
    
    # customers.signup_date -> dim_date.full_date
    check_fk(customers, "signup_date", dim_date, "full_date", "customers.signup_date -> dim_date")

    # ---------------------------------------------------------
    # 3. Revenue Reconciliation
    # ---------------------------------------------------------
    print("\n3. REVENUE RECONCILIATION")
    print("-" * 40)
    
    # line_total = round(quantity * unit_price * (1.0 - discount_percent/100.0), 2)
    calc_line_total = [round(q * p * (1.0 - d / 100.0), 2) for q, p, d in zip(order_items["quantity"], order_items["unit_price"], order_items["discount_percent"])]
    line_diff = np.abs(order_items["line_total"] - calc_line_total)
    bad_lines = (line_diff > 0.01).sum()
    
    if bad_lines == 0:
        print(f"  [PASS] Line item reconciliation: All {len(order_items):,} rows match formula.")
    else:
        print(f"  [FAIL] Line item reconciliation: {bad_lines:,} rows have discrepancies!")

    # total_amount = SUM(line_total) - discount_amount + shipping_cost
    order_sums = order_items.groupby("order_id")["line_total"].sum().reset_index()
    order_sums.rename(columns={"line_total": "sum_line_total"}, inplace=True)
    
    orders_merged = orders.merge(order_sums, on="order_id", how="left")
    # Fill NaN for orders with no items (shouldn't happen, but just in case)
    orders_merged["sum_line_total"] = orders_merged["sum_line_total"].fillna(0)
    
    calc_total = np.round(orders_merged["sum_line_total"] - orders_merged["discount_amount"] + orders_merged["shipping_cost"], 2)
    order_diff = np.abs(orders_merged["total_amount"] - calc_total)
    bad_orders = (order_diff > 0.02).sum()
    
    if bad_orders == 0:
        print(f"  [PASS] Order level reconciliation: All {len(orders):,} rows match formula.")
    else:
        print(f"  [FAIL] Order level reconciliation: {bad_orders:,} rows have discrepancies!")
        
    orphan_orders = orders_merged[orders_merged["sum_line_total"] == 0]
    if len(orphan_orders) == 0:
        print(f"  [PASS] Orphan orders check: 0 orders without line items.")
    else:
        print(f"  [FAIL] Orphan orders check: {len(orphan_orders):,} orders without line items found!")

    # ---------------------------------------------------------
    # 4. Temporal Integrity
    # ---------------------------------------------------------
    print("\n4. TEMPORAL INTEGRITY")
    print("-" * 40)
    
    orders_with_signup = orders.merge(customers[["customer_id", "signup_date"]], on="customer_id")
    
    # Convert to datetime for comparison
    orders_with_signup["order_date_dt"] = pd.to_datetime(orders_with_signup["order_date"])
    orders_with_signup["signup_date_dt"] = pd.to_datetime(orders_with_signup["signup_date"])
    
    invalid_dates = orders_with_signup[orders_with_signup["order_date_dt"] < orders_with_signup["signup_date_dt"]]
    
    if len(invalid_dates) == 0:
        print(f"  [PASS] order_date >= signup_date: True for all {len(orders):,} orders.")
    else:
        print(f"  [FAIL] order_date >= signup_date: {len(invalid_dates):,} violations found!")

    # ---------------------------------------------------------
    # 5. Customer Distribution Targets
    # ---------------------------------------------------------
    print("\n5. CUSTOMER DISTRIBUTION TARGETS")
    print("-" * 40)
    
    orders_per_cust = orders.groupby("customer_id").size().reset_index(name="order_count")
    
    one_time = len(orders_per_cust[orders_per_cust["order_count"] == 1]) / TARGET_CUSTOMERS
    occasional = len(orders_per_cust[(orders_per_cust["order_count"] >= 2) & (orders_per_cust["order_count"] <= 5)]) / TARGET_CUSTOMERS
    regular = len(orders_per_cust[(orders_per_cust["order_count"] >= 6) & (orders_per_cust["order_count"] <= 10)]) / TARGET_CUSTOMERS
    power = len(orders_per_cust[orders_per_cust["order_count"] >= 11]) / TARGET_CUSTOMERS
    
    target_one_time = BEHAVIOR_DIST["one_time"][0]
    target_occasional = BEHAVIOR_DIST["occasional"][0]
    target_regular = BEHAVIOR_DIST["regular"][0]
    target_power = BEHAVIOR_DIST["power"][0]
    
    # 3% tolerance for distribution since it was iteratively tuned
    def check_dist(name, actual, target, tol=0.03):
        status = "PASS" if abs(actual - target) <= tol else "FAIL"
        print(f"  [{status}] {name:15s} : {actual:6.1%} (Target: {target:6.1%})")

    check_dist("One-Time", one_time, target_one_time)
    check_dist("Occasional", occasional, target_occasional)
    check_dist("Regular", regular, target_regular)
    check_dist("Power", power, target_power)
    
    print("\n" + "=" * 70)
    print("  VALIDATION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
