"""
generate_orders.py — Generate ~60,000 order skeleton rows for the e-commerce
analytics platform.

WHAT THIS MODULE DOES
─────────────────────
1. Reads the customers CSV to extract customer_id, signup_date, city, state,
   and region for every customer.
2. Assigns each customer a *behavior segment* (one_time / occasional / regular /
   power) using the distribution in config.BEHAVIOR_DIST.  This controls how
   many orders the customer will place.
3. Generates order dates that respect the TEMPORAL INTEGRITY rule:
       order_date >= signup_date  (always)
   The first order date is offset from signup_date using the probability
   buckets in config.FIRST_ORDER_TIMING.  Subsequent order dates are spaced
   with an exponential inter-purchase gap whose mean depends on the behavior
   segment.
4. Applies config.SEASONALITY multipliers via acceptance-rejection sampling so
   that Diwali gets a realistic spike and the monsoon season gets a dip.
5. Tunes the total order count to hit config.TARGET_ORDERS (60,000) by
   randomly adding or removing orders from non-one-time customers.
6. Sets shipping address (85% same as customer, 15% random different city).
7. Marks is_first_order = True for each customer's chronologically earliest
   completed order (tie-breaker: lowest order_id).

WHAT THIS MODULE DOES *NOT* DO
──────────────────────────────
Financial columns `discount_amount` and `total_amount` are initialized to 0.00.
They are populated later by generate_order_items.py after line items are created.

OUTPUT
──────
Saves `orders.csv` to config.OUTPUT_DIR with index=False.

USAGE
─────
    python generate_orders.py          # standalone — loads customers.csv
    from generate_orders import generate_orders   # called by pipeline
"""

import os
import sys
from datetime import timedelta

import numpy as np
import pandas as pd

# ── project imports ──────────────────────────────────────────────────────────
from config import (
    BEHAVIOR_DIST,
    DATA_END,
    DATA_START,
    FIRST_ORDER_TIMING,
    GEOGRAPHY,
    ORDER_STATUS_DIST,
    OUTPUT_DIR,
    PAYMENT_METHOD_DIST,
    RANDOM_SEED,
    SEASONALITY,
    SHIPPING_COST_OPTIONS,
    TARGET_ORDERS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Seasonality weight for a given date
# ═══════════════════════════════════════════════════════════════════════════════

def _seasonality_weight(d):
    """Return the seasonality multiplier for calendar date *d*.

    Iterates through config.SEASONALITY windows.  If *d* falls within any
    window the corresponding multiplier is returned (first match wins).
    Dates outside all windows default to 1.0 (baseline).
    """
    md = (d.month, d.day)
    for (sm, sd), (em, ed), mult in SEASONALITY:
        start = (sm, sd)
        end = (em, ed)
        if start <= md <= end:
            return mult
    return 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Draw a first-order offset (days after signup)
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_first_order_offset(rng):
    """Sample an offset in days for the first order after signup.

    Uses config.FIRST_ORDER_TIMING which defines probability buckets:
        [ ((min_days, max_days), probability), ... ]
    First a bucket is chosen, then a uniform draw within that bucket.
    """
    buckets = [b for b, _ in FIRST_ORDER_TIMING]
    probs = [p for _, p in FIRST_ORDER_TIMING]
    idx = rng.choice(len(buckets), p=probs)
    lo, hi = buckets[idx]
    return int(rng.randint(lo, hi + 1))


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER: Draw from a categorical distribution dict
# ═══════════════════════════════════════════════════════════════════════════════

def _draw_categorical(dist_dict, rng, size=None):
    """Draw from {label: probability} using *rng*.  Returns label(s)."""
    labels = list(dist_dict.keys())
    probs = np.array(list(dist_dict.values()), dtype=float)
    probs /= probs.sum()  # normalise for safety
    return rng.choice(labels, p=probs, size=size)


# ═══════════════════════════════════════════════════════════════════════════════
# CORE: generate_orders
# ═══════════════════════════════════════════════════════════════════════════════

def generate_orders(customers_df: pd.DataFrame, rng: np.random.RandomState) -> pd.DataFrame:
    """Generate ~60,000 order skeleton rows.

    Parameters
    ----------
    customers_df : pd.DataFrame
        Must contain columns: customer_id, signup_date, city, state, region.
    rng : np.random.RandomState
        Seeded RNG for full reproducibility.

    Returns
    -------
    pd.DataFrame
        Orders dataframe with all columns matching the SQL schema.
        ``discount_amount`` and ``total_amount`` are 0.00 (populated later).
    """

    data_end_date = DATA_END
    data_start_date = DATA_START

    # Ensure signup_date is a Python date for arithmetic
    customers_df = customers_df.copy()
    customers_df["signup_date"] = pd.to_datetime(customers_df["signup_date"]).dt.date

    customer_ids = customers_df["customer_id"].values
    n_customers = len(customer_ids)

    # ------------------------------------------------------------------
    # 1.  BEHAVIOR ASSIGNMENT
    # ------------------------------------------------------------------
    segments = list(BEHAVIOR_DIST.keys())
    seg_probs = np.array([BEHAVIOR_DIST[s][0] for s in segments], dtype=float)
    seg_probs /= seg_probs.sum()

    assigned_segments = rng.choice(segments, size=n_customers, p=seg_probs)

    # Map customer_id → (segment, order_count)
    customer_orders = {}
    for cid, seg in zip(customer_ids, assigned_segments):
        _, lo, hi = BEHAVIOR_DIST[seg]
        count = int(rng.randint(lo, hi + 1))
        customer_orders[cid] = {"segment": seg, "count": count}

    # ------------------------------------------------------------------
    # 2.  ORDER COUNT TUNING
    # ------------------------------------------------------------------
    total = sum(v["count"] for v in customer_orders.values())
    non_one_time = [cid for cid, v in customer_orders.items() if v["segment"] != "one_time"]

    max_iter = 200_000  # safety cap
    iteration = 0
    while total != TARGET_ORDERS and iteration < max_iter:
        iteration += 1
        if not non_one_time:
            break
        cid = rng.choice(non_one_time)
        seg = customer_orders[cid]["segment"]
        _, lo, hi = BEHAVIOR_DIST[seg]
        cur = customer_orders[cid]["count"]

        if total < TARGET_ORDERS and cur < hi:
            customer_orders[cid]["count"] += 1
            total += 1
        elif total > TARGET_ORDERS and cur > lo:
            customer_orders[cid]["count"] -= 1
            total -= 1

    print(f"[orders] Total orders after tuning: {total}  (target {TARGET_ORDERS})")

    # ------------------------------------------------------------------
    # 3.  GEOGRAPHY LOOKUP for shipping address
    # ------------------------------------------------------------------
    geo_cities = [(c, s, r) for c, s, r, _ in GEOGRAPHY]
    geo_weights = np.array([w for _, _, _, w in GEOGRAPHY], dtype=float)
    geo_weights /= geo_weights.sum()

    # Customer geography lookup
    cust_geo = {}
    for _, row in customers_df.iterrows():
        cust_geo[row["customer_id"]] = (row["city"], row["state"], row["region"])

    # Customer signup date lookup
    cust_signup = dict(zip(customers_df["customer_id"], customers_df["signup_date"]))

    # ------------------------------------------------------------------
    # 4.  INTER-PURCHASE GAP MEANS (days) by segment
    # ------------------------------------------------------------------
    gap_means = {
        "occasional": 40.0,
        "regular": 25.0,
        "power": 18.0,
    }

    # ------------------------------------------------------------------
    # 5.  MAX SEASONALITY WEIGHT (for acceptance-rejection)
    # ------------------------------------------------------------------
    max_season = max(m for _, _, m in SEASONALITY)
    max_season = max(max_season, 1.0)  # at least 1.0

    # ------------------------------------------------------------------
    # 6.  GENERATE ORDER ROWS
    # ------------------------------------------------------------------
    rows = []
    for cid in customer_ids:
        info = customer_orders[cid]
        n_orders = info["count"]
        segment = info["segment"]
        signup = cust_signup[cid]

        dates = []
        # --- First order date ---
        for _ in range(500):  # acceptance-rejection retries
            offset = _draw_first_order_offset(rng)
            candidate = signup + timedelta(days=offset)
            if candidate > data_end_date:
                continue
            if candidate < data_start_date:
                candidate = data_start_date
            # acceptance-rejection with seasonality
            w = _seasonality_weight(candidate)
            if rng.random() < w / max_season:
                dates.append(candidate)
                break
        if not dates:
            # fallback: use signup_date or data_start (whichever is later)
            dates.append(max(signup, data_start_date))

        # --- Subsequent order dates ---
        mean_gap = gap_means.get(segment, 40.0)
        for _ in range(1, n_orders):
            generated = False
            for __ in range(50):  # retries
                gap = max(1, int(rng.exponential(mean_gap)))
                candidate = dates[-1] + timedelta(days=gap)
                if candidate > data_end_date:
                    # just pick a random date between first order and end date
                    days_available = (data_end_date - dates[0]).days
                    if days_available > 0:
                        candidate = dates[0] + timedelta(days=rng.randint(0, days_available + 1))
                    else:
                        candidate = dates[0]
                w = _seasonality_weight(candidate)
                if rng.random() < w / max_season:
                    dates.append(candidate)
                    generated = True
                    break
            if not generated:
                # fallback if rejection sampling fails too many times
                days_available = (data_end_date - dates[0]).days
                if days_available > 0:
                    candidate = dates[0] + timedelta(days=rng.randint(0, days_available + 1))
                else:
                    candidate = dates[0]
                dates.append(candidate)

        # Sort chronologically
        dates.sort()

        # --- Build order rows for this customer ---
        for od in dates:
            # Shipping address: 85% same city as customer, 15% random
            if rng.random() < 0.85:
                ship_city, ship_state, ship_region = cust_geo[cid]
            else:
                idx = rng.choice(len(geo_cities), p=geo_weights)
                ship_city, ship_state, ship_region = geo_cities[idx]

            # Order status
            status = _draw_categorical(ORDER_STATUS_DIST, rng)

            # Payment method
            payment = _draw_categorical(PAYMENT_METHOD_DIST, rng)

            # Shipping cost
            sc_vals = [v for v, _ in SHIPPING_COST_OPTIONS]
            sc_probs = np.array([p for _, p in SHIPPING_COST_OPTIONS], dtype=float)
            sc_probs /= sc_probs.sum()
            ship_cost = float(rng.choice(sc_vals, p=sc_probs))

            rows.append({
                "customer_id": int(cid),
                "order_date": od,
                "order_status": status,
                "payment_method": payment,
                "shipping_city": ship_city,
                "shipping_state": ship_state,
                "shipping_region": ship_region,
                "shipping_country": "India",
                "discount_amount": 0.00,
                "shipping_cost": round(ship_cost, 2),
                "total_amount": 0.00,
                "is_first_order": False,
            })

    # ------------------------------------------------------------------
    # 7.  BUILD DATAFRAME & ASSIGN order_id
    # ------------------------------------------------------------------
    orders_df = pd.DataFrame(rows)
    orders_df = orders_df.sample(frac=1.0, random_state=rng).reset_index(drop=True)
    orders_df.insert(0, "order_id", range(1, len(orders_df) + 1))

    # ------------------------------------------------------------------
    # 8.  SET is_first_order
    # ------------------------------------------------------------------
    # For each customer, find the chronologically earliest *completed* order.
    # Tie-breaker: lowest order_id.
    completed = orders_df[orders_df["order_status"] == "Completed"].copy()
    if not completed.empty:
        completed = completed.sort_values(["customer_id", "order_date", "order_id"])
        first_ids = completed.groupby("customer_id")["order_id"].first().values
        orders_df.loc[orders_df["order_id"].isin(first_ids), "is_first_order"] = True

    # ------------------------------------------------------------------
    # 9.  FINAL CLEANUP — ensure no NaN
    # ------------------------------------------------------------------
    orders_df["discount_amount"] = orders_df["discount_amount"].fillna(0.00)
    orders_df["total_amount"] = orders_df["total_amount"].fillna(0.00)
    orders_df["is_first_order"] = orders_df["is_first_order"].fillna(False)

    # Ensure money columns are float rounded to 2 dp
    orders_df["discount_amount"] = orders_df["discount_amount"].round(2)
    orders_df["shipping_cost"] = orders_df["shipping_cost"].round(2)
    orders_df["total_amount"] = orders_df["total_amount"].round(2)

    assert orders_df.isna().sum().sum() == 0, "NaN values detected in orders_df!"

    return orders_df


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    rng = np.random.RandomState(RANDOM_SEED)

    customers_path = os.path.join(OUTPUT_DIR, "customers.csv")
    if not os.path.exists(customers_path):
        print(f"ERROR: customers.csv not found at {customers_path}")
        print("Run generate_customers.py first.")
        sys.exit(1)

    customers_df = pd.read_csv(customers_path)
    print(f"[orders] Loaded {len(customers_df)} customers from {customers_path}")

    orders_df = generate_orders(customers_df, rng)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, "orders.csv")
    orders_df.to_csv(out_path, index=False)

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  ORDERS GENERATION SUMMARY")
    print("=" * 65)
    print(f"  Total orders         : {len(orders_df):,}")
    print(f"  Unique customers     : {orders_df['customer_id'].nunique():,}")
    print(f"  Date range           : {orders_df['order_date'].min()} → {orders_df['order_date'].max()}")
    print(f"  Status distribution  :")
    for s, c in orders_df["order_status"].value_counts().items():
        print(f"    {s:15s} : {c:6,}  ({c / len(orders_df) * 100:.1f}%)")
    print(f"  Payment methods      :")
    for p, c in orders_df["payment_method"].value_counts().items():
        print(f"    {p:15s} : {c:6,}  ({c / len(orders_df) * 100:.1f}%)")
    print(f"  First-order flags    : {orders_df['is_first_order'].sum():,}")
    print(f"  Saved to             : {out_path}")
    print("=" * 65)
