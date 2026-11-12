"""
generate_order_items.py — Generate ~150,000+ line items AND finalize order
financials (discount_amount, total_amount) on the orders table.

WHAT THIS MODULE DOES
─────────────────────
1. Assigns each product a *popularity weight* using a Zipf distribution
   (s=1.2) so that the top ~20% of products attract ~65% of purchases.
2. For every order, draws the number of line items from
   config.ITEMS_PER_ORDER_DIST (average ~2.5 items/order).
3. Selects products WITHOUT replacement within each order (no duplicate
   product lines), using popularity-weighted sampling.
4. For each line item:
   - quantity: drawn from config.QUANTITY_DIST
   - unit_price: 70% of items use the product's list_price exactly;
     30% get a promotional price = list_price × uniform(0.80, 0.95)
   - discount_percent: drawn from config.LINE_DISCOUNT_DIST
   - line_total = round(quantity × unit_price × (1 − discount_percent/100), 2)
5. After ALL items for an order are generated, reconciles order-level
   financials:
   - sum_line_totals = Σ line_total
   - discount_amount drawn from config.ORDER_DISCOUNT_TIERS, capped so it
     never exceeds sum_line_totals − 1.0
   - total_amount = round(sum_line_totals − discount_amount + shipping_cost, 2)
   - ASSERT total_amount > 0
   - UPDATES orders_df in-place with the computed values.

REVENUE RECONCILIATION FORMULA (from SQL schema §6.2)
─────────────────────────────────────────────────────
    total_amount = SUM(line_total) − discount_amount + shipping_cost

OUTPUT
──────
Saves `order_items.csv` to config.OUTPUT_DIR with index=False.
Also saves the UPDATED `orders.csv` (with correct discount_amount and
total_amount) back to config.OUTPUT_DIR.

USAGE
─────
    python generate_order_items.py
    from generate_order_items import generate_order_items
"""

import os
import sys

import numpy as np
import pandas as pd

# ── project imports ──────────────────────────────────────────────────────────
from config import (
    FULL_PRICE_FRACTION,
    ITEMS_PER_ORDER_DIST,
    LINE_DISCOUNT_DIST,
    ORDER_DISCOUNT_TIERS,
    OUTPUT_DIR,
    QUANTITY_DIST,
    RANDOM_SEED,
    TARGET_ORDER_ITEMS_MIN,
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Draw from a categorical distribution dict
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_categorical(dist_dict, rng, size=None):
    """Draw from {label: probability} using *rng*.  Returns label(s)."""
    labels = list(dist_dict.keys())
    probs = np.array(list(dist_dict.values()), dtype=float)
    probs /= probs.sum()
    if size is None:
        return rng.choice(labels, p=probs)
    return rng.choice(labels, p=probs, size=size)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Build Zipf popularity weights
# ═══════════════════════════════════════════════════════════════════════════════

def _build_popularity_weights(n_products, rng, s=1.2):
    """Return normalised Zipf popularity weights for *n_products*.

    Products are first shuffled so that rank assignment is random, then
    Zipf weights are applied.  Top ~20% of products will receive ~65%
    of total weight.

    Parameters
    ----------
    n_products : int
    rng : np.random.RandomState
    s : float
        Zipf exponent.  Higher → more skewed.

    Returns
    -------
    np.ndarray  shape (n_products,)
        Normalised probability vector.
    """
    ranks = np.arange(1, n_products + 1)
    rng.shuffle(ranks)               # randomise which products are "popular"
    weights = 1.0 / np.power(ranks, s)
    weights /= weights.sum()
    return weights


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Draw order-level discount
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_order_discount(rng):
    """Return an order-level discount amount from config.ORDER_DISCOUNT_TIERS.

    Each tier is (min_amt, max_amt, probability).  First a tier is chosen,
    then a uniform value is drawn within [min_amt, max_amt].
    """
    tier_probs = np.array([p for _, _, p in ORDER_DISCOUNT_TIERS], dtype=float)
    tier_probs /= tier_probs.sum()
    idx = rng.choice(len(ORDER_DISCOUNT_TIERS), p=tier_probs)
    lo, hi, _ = ORDER_DISCOUNT_TIERS[idx]
    if lo == hi == 0.0:
        return 0.0
    return round(float(rng.uniform(lo, hi)), 2)


# ═══════════════════════════════════════════════════════════════════════════════
# CORE: generate_order_items
# ═══════════════════════════════════════════════════════════════════════════════

def generate_order_items(
    orders_df: pd.DataFrame,
    products_df: pd.DataFrame,
    rng: np.random.RandomState,
) -> tuple:
    """Generate ~150,000+ order-item rows and reconcile order financials.

    Parameters
    ----------
    orders_df : pd.DataFrame
        Must contain: order_id, shipping_cost.  discount_amount and
        total_amount will be OVERWRITTEN.
    products_df : pd.DataFrame
        Must contain: product_id, list_price.
    rng : np.random.RandomState
        Seeded RNG for full reproducibility.

    Returns
    -------
    (order_items_df, updated_orders_df)
        order_items_df : pd.DataFrame with all order_items columns.
        updated_orders_df : orders_df with discount_amount and total_amount
                            correctly populated.
    """

    # ------------------------------------------------------------------
    # 0.  PRODUCT LOOKUP
    # ------------------------------------------------------------------
    product_ids = products_df["product_id"].values
    list_prices = dict(zip(products_df["product_id"], products_df["list_price"]))
    n_products = len(product_ids)

    # ------------------------------------------------------------------
    # 1.  PRODUCT POPULARITY WEIGHTS (Zipf s=1.2)
    # ------------------------------------------------------------------
    pop_weights = _build_popularity_weights(n_products, rng, s=1.2)

    # ------------------------------------------------------------------
    # 2.  PRE-COMPUTE per-order items count
    # ------------------------------------------------------------------
    items_labels = list(ITEMS_PER_ORDER_DIST.keys())
    items_probs = np.array(list(ITEMS_PER_ORDER_DIST.values()), dtype=float)
    items_probs /= items_probs.sum()

    # Draw number of items for every order at once
    n_orders = len(orders_df)
    items_per_order = rng.choice(items_labels, size=n_orders, p=items_probs)

    # Check total — we want >= TARGET_ORDER_ITEMS_MIN
    total_items = int(items_per_order.sum())
    print(f"[order_items] Initial total items: {total_items:,}  (target >= {TARGET_ORDER_ITEMS_MIN:,})")

    # If under target, bump some orders to have more items
    if total_items < TARGET_ORDER_ITEMS_MIN:
        deficit = TARGET_ORDER_ITEMS_MIN - total_items
        max_item_val = max(items_labels)
        candidate_idxs = np.where(items_per_order < max_item_val)[0]
        rng.shuffle(candidate_idxs)
        for ci in candidate_idxs:
            if deficit <= 0:
                break
            bump = min(max_item_val - items_per_order[ci], deficit)
            items_per_order[ci] += bump
            deficit -= bump
        total_items = int(items_per_order.sum())
        print(f"[order_items] Adjusted total items: {total_items:,}")

    # ------------------------------------------------------------------
    # 3.  PRE-COMPUTE quantity and discount distributions
    # ------------------------------------------------------------------
    qty_labels = list(QUANTITY_DIST.keys())
    qty_probs = np.array(list(QUANTITY_DIST.values()), dtype=float)
    qty_probs /= qty_probs.sum()

    disc_labels = list(LINE_DISCOUNT_DIST.keys())
    disc_probs = np.array(list(LINE_DISCOUNT_DIST.values()), dtype=float)
    disc_probs /= disc_probs.sum()

    # ------------------------------------------------------------------
    # 4.  GENERATE LINE ITEMS + ORDER FINANCIALS
    # ------------------------------------------------------------------
    all_items = []
    order_id_col = orders_df["order_id"].values
    shipping_cost_col = orders_df["shipping_cost"].values.astype(float)

    # Prepare columns for discount_amount and total_amount in orders
    discount_amounts = np.zeros(n_orders, dtype=float)
    total_amounts = np.zeros(n_orders, dtype=float)

    for i in range(n_orders):
        oid = int(order_id_col[i])
        n_items = int(items_per_order[i])
        ship_cost = float(shipping_cost_col[i])

        # 4a. Select products (without replacement within order)
        actual_n = min(n_items, n_products)  # cannot exceed product count
        selected_pids = rng.choice(
            product_ids, size=actual_n, replace=False, p=pop_weights
        )

        line_totals = []
        for pid in selected_pids:
            pid = int(pid)

            # 4b. Quantity
            qty = int(rng.choice(qty_labels, p=qty_probs))

            # 4c. Unit price
            lp = float(list_prices[pid])
            if rng.random() < FULL_PRICE_FRACTION:
                up = lp  # full list price
            else:
                # promotional price: 80%-95% of list price
                up = round(lp * float(rng.uniform(0.80, 0.95)), 2)

            # 4d. Discount percent
            dp = float(rng.choice(disc_labels, p=disc_probs))

            # 4e. Line total
            lt = round(qty * up * (1.0 - dp / 100.0), 2)

            # Guard: line_total must be > 0
            if lt <= 0:
                lt = round(up * qty * 0.01, 2)  # fallback 1%
                if lt <= 0:
                    lt = 0.01

            all_items.append({
                "order_id": oid,
                "product_id": pid,
                "quantity": qty,
                "unit_price": round(up, 2),
                "discount_percent": round(dp, 2),
                "line_total": lt,
            })
            line_totals.append(lt)

        # 4f. ORDER FINANCIAL RECONCILIATION
        sum_lt = sum(line_totals)

        # Draw order-level discount
        disc_amt = _draw_order_discount(rng)

        # CAP: discount cannot exceed sum_line_totals - 1.0
        if disc_amt >= sum_lt:
            disc_amt = max(0.0, round(sum_lt - 1.0, 2))

        total_amt = round(sum_lt - disc_amt + ship_cost, 2)

        # ASSERT total_amount > 0
        if total_amt <= 0:
            # Emergency adjustment: reduce discount until positive
            disc_amt = max(0.0, round(sum_lt + ship_cost - 0.01, 2))
            total_amt = round(sum_lt - disc_amt + ship_cost, 2)
            if total_amt <= 0:
                total_amt = 0.01  # absolute floor

        discount_amounts[i] = round(disc_amt, 2)
        total_amounts[i] = round(total_amt, 2)

    # ------------------------------------------------------------------
    # 5.  UPDATE orders_df with computed financials
    # ------------------------------------------------------------------
    orders_df = orders_df.copy()
    orders_df["discount_amount"] = discount_amounts
    orders_df["total_amount"] = total_amounts

    # Ensure rounding
    orders_df["discount_amount"] = orders_df["discount_amount"].round(2)
    orders_df["total_amount"] = orders_df["total_amount"].round(2)

    # ------------------------------------------------------------------
    # 6.  BUILD order_items DataFrame
    # ------------------------------------------------------------------
    order_items_df = pd.DataFrame(all_items)
    order_items_df.insert(0, "order_item_id", range(1, len(order_items_df) + 1))

    # ------------------------------------------------------------------
    # 7.  FINAL VALIDATION — no NaN
    # ------------------------------------------------------------------
    assert order_items_df.isna().sum().sum() == 0, "NaN values in order_items_df!"
    assert orders_df.isna().sum().sum() == 0, "NaN values in updated orders_df!"
    assert (orders_df["total_amount"] > 0).all(), "total_amount <= 0 detected!"

    return order_items_df, orders_df


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    rng = np.random.RandomState(RANDOM_SEED)

    orders_path = os.path.join(OUTPUT_DIR, "orders.csv")
    products_path = os.path.join(OUTPUT_DIR, "products.csv")

    for p, label in [(orders_path, "orders.csv"), (products_path, "products.csv")]:
        if not os.path.exists(p):
            print(f"ERROR: {label} not found at {p}")
            print("Run the upstream generator(s) first.")
            sys.exit(1)

    orders_df = pd.read_csv(orders_path)
    products_df = pd.read_csv(products_path)
    print(f"[order_items] Loaded {len(orders_df):,} orders, {len(products_df):,} products")

    order_items_df, orders_df = generate_order_items(orders_df, products_df, rng)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Save order_items
    items_path = os.path.join(OUTPUT_DIR, "order_items.csv")
    order_items_df.to_csv(items_path, index=False)

    # Save UPDATED orders (with correct financials)
    orders_df.to_csv(orders_path, index=False)

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  ORDER ITEMS GENERATION SUMMARY")
    print("=" * 65)
    print(f"  Total line items     : {len(order_items_df):,}")
    print(f"  Unique orders        : {order_items_df['order_id'].nunique():,}")
    print(f"  Unique products      : {order_items_df['product_id'].nunique():,}")
    print(f"  Avg items/order      : {len(order_items_df) / order_items_df['order_id'].nunique():.2f}")
    print(f"  Quantity distribution:")
    for q, c in order_items_df["quantity"].value_counts().sort_index().items():
        print(f"    qty {q} : {c:7,}  ({c / len(order_items_df) * 100:.1f}%)")
    print(f"  Discount % distribution:")
    for d, c in order_items_df["discount_percent"].value_counts().sort_index().items():
        print(f"    {d:5.1f}% : {c:7,}  ({c / len(order_items_df) * 100:.1f}%)")

    print(f"\n  ORDER FINANCIALS (updated):")
    print(f"    Total revenue      : ₹{orders_df['total_amount'].sum():,.2f}")
    print(f"    Avg order value    : ₹{orders_df['total_amount'].mean():,.2f}")
    print(f"    Total discounts    : ₹{orders_df['discount_amount'].sum():,.2f}")
    print(f"    Total shipping     : ₹{orders_df['shipping_cost'].sum():,.2f}")
    print(f"    Sum line totals    : ₹{order_items_df['line_total'].sum():,.2f}")

    # Reconciliation check
    merged = order_items_df.groupby("order_id")["line_total"].sum().reset_index()
    merged.columns = ["order_id", "sum_line_total"]
    check = orders_df.merge(merged, on="order_id")
    check["expected_total"] = check["sum_line_total"] - check["discount_amount"] + check["shipping_cost"]
    check["diff"] = (check["total_amount"] - check["expected_total"]).abs()
    max_diff = check["diff"].max()
    failed = (check["diff"] > 0.02).sum()
    print(f"\n  RECONCILIATION CHECK:")
    print(f"    Max difference     : ₹{max_diff:.4f}")
    print(f"    Orders failing     : {failed}  (tolerance ₹0.02)")

    print(f"\n  Saved order_items to : {items_path}")
    print(f"  Updated orders at   : {orders_path}")
    print("=" * 65)
