"""
clean_data.py — Data Cleaning Module

1. Check for missing values
2. Check for duplicate rows
3. Enforce and validate data types
4. Validate critical foreign keys
5. Generate Data Quality Report
6. Export cleaned CSVs to data/processed/
"""

import os
import pandas as pd

def clean_data(raw_dir: str, processed_dir: str) -> None:
    """Reads raw data, cleans it, produces a quality report, and exports processed data."""
    
    os.makedirs(processed_dir, exist_ok=True)
    report_path = os.path.join(processed_dir, "data_quality_report.txt")
    
    with open(report_path, "w") as f:
        f.write("==================================================\n")
        f.write("             DATA QUALITY REPORT\n")
        f.write("==================================================\n\n")

        # ---------------------------------------------------------
        # 1. LOAD DATA
        # ---------------------------------------------------------
        try:
            dim_date = pd.read_csv(os.path.join(raw_dir, "dim_date.csv"))
            categories = pd.read_csv(os.path.join(raw_dir, "categories.csv"))
            products = pd.read_csv(os.path.join(raw_dir, "products.csv"))
            customers = pd.read_csv(os.path.join(raw_dir, "customers.csv"))
            orders = pd.read_csv(os.path.join(raw_dir, "orders.csv"))
            order_items = pd.read_csv(os.path.join(raw_dir, "order_items.csv"))
        except FileNotFoundError as e:
            f.write(f"CRITICAL ERROR: Failed to load raw files.\n{str(e)}\n")
            raise

        datasets = {
            "dim_date": dim_date,
            "categories": categories,
            "products": products,
            "customers": customers,
            "orders": orders,
            "order_items": order_items
        }

        # ---------------------------------------------------------
        # 2 & 3. MISSING VALUES & DUPLICATES
        # ---------------------------------------------------------
        f.write("--- Missing Values & Duplicates ---\n")
        for name, df in datasets.items():
            missing = df.isnull().sum().sum()
            dupes = df.duplicated().sum()
            f.write(f"{name:15s} | Missing: {missing:>6,d} | Duplicates: {dupes:>6,d}\n")
            
            if dupes > 0:
                f.write(f"  -> Dropping {dupes} duplicate rows from {name}\n")
                df.drop_duplicates(inplace=True)
                
            # If we had missing values in critical columns, we'd drop/impute them here.
            # Given our synthetically generated dataset, missing values should be 0.
        f.write("\n")

        # ---------------------------------------------------------
        # 4. ENFORCE DATA TYPES
        # ---------------------------------------------------------
        # dim_date
        dim_date["full_date"] = pd.to_datetime(dim_date["full_date"])
        
        # customers
        customers["signup_date"] = pd.to_datetime(customers["signup_date"])
        
        # orders
        orders["order_date"] = pd.to_datetime(orders["order_date"])
        for col in ["discount_amount", "shipping_cost", "total_amount"]:
            orders[col] = orders[col].astype(float)
            
        # products
        for col in ["unit_cost", "list_price"]:
            products[col] = products[col].astype(float)
            
        # order_items
        for col in ["unit_price", "discount_percent", "line_total"]:
            order_items[col] = order_items[col].astype(float)

        f.write("--- Data Types Validated & Casted ---\n")
        f.write("Dates parsed to datetime, financial columns cast to float.\n\n")

        # ---------------------------------------------------------
        # 5. FOREIGN KEY VALIDATION
        # ---------------------------------------------------------
        f.write("--- Foreign Key Validation ---\n")
        
        def check_fk(child_df, child_col, parent_df, parent_col, rel_name):
            orphans = child_df[~child_df[child_col].isin(parent_df[parent_col])]
            if len(orphans) == 0:
                f.write(f"[PASS] {rel_name}\n")
            else:
                f.write(f"[FAIL] {rel_name} - {len(orphans)} orphans found!\n")
                # For ETL, we could drop orphan rows to protect downstream models.
                # However, with clean generation, we expect 0 orphans.
        
        check_fk(products, "category_id", categories, "category_id", "products -> categories")
        check_fk(orders, "customer_id", customers, "customer_id", "orders -> customers")
        check_fk(order_items, "order_id", orders, "order_id", "order_items -> orders")
        check_fk(order_items, "product_id", products, "product_id", "order_items -> products")
        f.write("\n")
        
        # ---------------------------------------------------------
        # 6. EXPORT PROCESSED DATA
        # ---------------------------------------------------------
        f.write("--- Exporting Cleaned Data ---\n")
        for name, df in datasets.items():
            out_path = os.path.join(processed_dir, f"{name}.csv")
            df.to_csv(out_path, index=False)
            rel_path = os.path.join("data", "processed", f"{name}.csv")
            f.write(f"Saved: {rel_path} ({len(df):,} rows)\n")
            
    print(f"  [OK] Data cleaning complete. Report saved to: {report_path}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    clean_data(
        raw_dir=os.path.join(base_dir, "data", "raw"),
        processed_dir=os.path.join(base_dir, "data", "processed")
    )
