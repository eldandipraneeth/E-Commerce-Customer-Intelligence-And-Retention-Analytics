"""
generate_products.py — Generate the products dimension table CSV.

This module creates 500 synthetic products distributed across the 14
sub-categories defined in config.CATEGORIES.  The per-subcategory counts
are governed by config.PRODUCTS_PER_SUBCATEGORY (which sums to 500).

Product-name generation:
    1. For each subcategory, pick templates from config.PRODUCT_TEMPLATES
       and brands from config.BRANDS (both cycled as needed).
    2. Combine as "{brand} {template} {variant}" where the variant suffix
       (colour, size, edition, etc.) provides uniqueness when the same
       brand+template combination would otherwise repeat.
    3. A final uniqueness check guarantees no duplicate product_name values.

Pricing logic (all amounts in INR):
    • list_price — Drawn from a log-normal distribution and then clipped to
      the subcategory's [min_price, max_price] range from config.PRICING_CONFIG.
      The log-normal's μ and σ are derived so that the distribution's median
      falls at the geometric mean of the range endpoints.
    • unit_cost  — Computed as list_price × (1 − margin) where margin is
      sampled uniformly from the subcategory's [min_margin, max_margin].
      This guarantees unit_cost ≤ list_price.

Reproducibility:
    All randomness flows through a numpy RandomState seeded with
    config.RANDOM_SEED (42).
"""

import os
import numpy as np
import pandas as pd

from config import (
    RANDOM_SEED,
    CATEGORIES,
    PRODUCTS_PER_SUBCATEGORY,
    PRICING_CONFIG,
    BRANDS,
    PRODUCT_TEMPLATES,
    OUTPUT_DIR,
)


# ────────────────────────────────────────────────────────────────────────────
# Variant suffixes used to differentiate products when template+brand combos
# are exhausted.  Grouped by "flavour" so names read naturally.
# ────────────────────────────────────────────────────────────────────────────
_COLOUR_VARIANTS = [
    "Black", "White", "Silver", "Gold", "Blue", "Red", "Green",
    "Grey", "Rose Gold", "Midnight", "Navy", "Ivory", "Charcoal",
    "Coral", "Lavender", "Teal", "Copper", "Bronze",
]

_EDITION_VARIANTS = [
    "Pro", "Lite", "Plus", "Max", "Ultra", "SE", "Elite",
    "Deluxe", "Classic", "Premium", "Sport", "Eco", "Turbo",
]

_SIZE_VARIANTS = [
    "S", "M", "L", "XL", "XXL", "Mini", "Compact", "Standard",
    "Large", "King", "Regular",
]

# Merged list — the generator cycles through these as needed.
_ALL_VARIANTS = _COLOUR_VARIANTS + _EDITION_VARIANTS + _SIZE_VARIANTS


def generate_products(rng: np.random.RandomState) -> pd.DataFrame:
    """Generate 500 products with unique names, brands, and realistic pricing.

    Parameters
    ----------
    rng : np.random.RandomState
        Seeded random state for reproducibility.

    Returns
    -------
    pd.DataFrame
        Columns:
            product_id   – int, sequential starting at 1
            category_id  – int, FK to categories (1-14)
            product_name – str, unique descriptive name (≤ 150 chars)
            brand        – str, brand name from config.BRANDS
            unit_cost    – float, rounded to 2 decimals, ≤ list_price
            list_price   – float, rounded to 2 decimals
    """

    rows: list[dict] = []
    seen_names: set[str] = set()
    product_id = 1

    for cat_id, _cat_name, _sub_cat in CATEGORIES:
        n_products = PRODUCTS_PER_SUBCATEGORY[cat_id]
        templates = PRODUCT_TEMPLATES[cat_id]
        brands = BRANDS[cat_id]
        min_price, max_price, min_margin, max_margin = PRICING_CONFIG[cat_id]

        # ── Log-normal parameters ──────────────────────────────────────
        # We want the median of the distribution ≈ geometric mean of the
        # price range, because the median of a log-normal is exp(μ).
        #   median = sqrt(min_price * max_price)
        #   μ      = ln(median)
        #   σ      = chosen so that ≈95 % of raw draws fall within the range.
        #            Using σ = ln(max/min) / 4 works well in practice.
        geo_mean = np.sqrt(min_price * max_price)
        mu = np.log(geo_mean)
        sigma = np.log(max_price / min_price) / 4.0

        # ── Variant index tracks how many times we've cycled ───────────
        variant_idx = 0

        for i in range(n_products):
            # Cycle through templates and brands independently
            template = templates[i % len(templates)]
            brand = brands[i % len(brands)]

            # ── Build a unique product name ────────────────────────────
            base_name = f"{brand} {template}"
            if base_name not in seen_names:
                name = base_name
            else:
                # Append a variant suffix until the name is unique
                while True:
                    suffix = _ALL_VARIANTS[variant_idx % len(_ALL_VARIANTS)]
                    candidate = f"{base_name} {suffix}"
                    variant_idx += 1
                    if candidate not in seen_names:
                        name = candidate
                        break
            seen_names.add(name)

            # ── Price from log-normal, clipped to configured range ─────
            raw_price = rng.lognormal(mean=mu, sigma=sigma)
            list_price = round(float(np.clip(raw_price, min_price, max_price)), 2)

            # ── Cost derived from a random margin within the range ─────
            margin = rng.uniform(min_margin, max_margin)
            unit_cost = round(list_price * (1.0 - margin), 2)

            rows.append(
                {
                    "product_id": product_id,
                    "category_id": cat_id,
                    "product_name": name,
                    "brand": brand,
                    "unit_cost": unit_cost,
                    "list_price": list_price,
                }
            )
            product_id += 1

    df = pd.DataFrame(rows)

    # ── Final assertion: every product_name must be unique ─────────────
    assert df["product_name"].is_unique, (
        "Duplicate product names detected — review variant generation logic."
    )

    return df


# ═══════════════════════════════════════════════════════════════════════════
# Standalone execution — write CSV and print diagnostics
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Seed the random state from config
    rng = np.random.RandomState(RANDOM_SEED)

    # Generate the products dimension
    products = generate_products(rng)

    # Persist to CSV (no pandas index column)
    output_path = os.path.join(OUTPUT_DIR, "products.csv")
    products.to_csv(output_path, index=False)

    # ── Diagnostics ────────────────────────────────────────────────────
    print(f"✅  products written → {output_path}")
    print(f"    Rows          : {len(products)}")
    print(f"    Unique names  : {products['product_name'].nunique()}")
    print(f"    Categories    : {products['category_id'].nunique()}")
    print(f"    Price range   : ₹{products['list_price'].min():,.2f} – "
          f"₹{products['list_price'].max():,.2f}")
    print(f"    Cost range    : ₹{products['unit_cost'].min():,.2f} – "
          f"₹{products['unit_cost'].max():,.2f}")

    # Products per subcategory
    print("\n── Products per subcategory ──")
    print(products.groupby("category_id").size().to_string())

    # Sample rows
    print("\n── Sample rows ──")
    print(products.head(10).to_string(index=False))
