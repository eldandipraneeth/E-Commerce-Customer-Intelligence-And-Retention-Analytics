"""
generate_categories.py — Generate the categories dimension table CSV.

This module creates the product-category lookup table from the hardcoded
list in config.CATEGORIES.  It is intentionally trivial: no randomness,
no distribution logic — just a faithful transcription of the 14-row
reference list into a DataFrame and CSV.

Each row represents a *sub*-category (e.g. "Smartphones") nested under a
top-level category (e.g. "Electronics").  The category_id acts as both the
primary key of this table and the foreign key referenced by the products
table.

Hierarchy (6 top-level → 14 sub-categories):
    Electronics       → Smartphones, Laptops, Headphones
    Clothing          → Men's Wear, Women's Wear, Footwear
    Home & Kitchen    → Cookware, Furniture
    Sports & Outdoors → Fitness Equipment, Camping Gear
    Books             → Fiction, Non-Fiction
    Beauty & Health   → Skincare, Supplements
"""

import os
import pandas as pd

from config import CATEGORIES, OUTPUT_DIR


def generate_categories() -> pd.DataFrame:
    """Return a 14-row DataFrame built from config.CATEGORIES.

    Returns
    -------
    pd.DataFrame
        Columns:
            category_id   – int, sequential starting at 1
            category_name – str, top-level category
            sub_category  – str, sub-category within the parent
    """

    # ── Build DataFrame directly from the config tuple list ────────────
    df = pd.DataFrame(
        CATEGORIES,
        columns=["category_id", "category_name", "sub_category"],
    )

    return df


# ═══════════════════════════════════════════════════════════════════════════
# Standalone execution — write CSV and print diagnostics
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Generate the categories dimension
    categories = generate_categories()

    # Persist to CSV (no pandas index column)
    output_path = os.path.join(OUTPUT_DIR, "categories.csv")
    categories.to_csv(output_path, index=False)

    # ── Diagnostics ────────────────────────────────────────────────────
    print(f"✅  categories written → {output_path}")
    print(f"    Rows: {len(categories)}")
    print()
    print(categories.to_string(index=False))
