from __future__ import annotations

"""
generate_customers.py — Generate synthetic customer data for the e-commerce analytics project.

Produces a CSV with 20,000 rows conforming to the dim_customers PostgreSQL schema.
All distributions, geography weights, and constants are sourced from config.py
to ensure consistency across the data-generation pipeline.

Usage:
    python generate_customers.py

Output:
    data/raw/customers.csv
"""

import os
import sys

import numpy as np
import pandas as pd
from faker import Faker

# ---------------------------------------------------------------------------
# Ensure the scripts/ directory is on sys.path so config can be imported
# regardless of the working directory.
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import config  # noqa: E402  (must come after sys.path manipulation)


# ============================================================================
# HELPER — weighted date generation with growth trend
# ============================================================================

def _generate_signup_dates(
    n: int,
    rng: np.random.RandomState,
    start_date: "date" = config.DATA_START,
    end_date: "date" = config.SIGNUP_END,
    growth_pct: float = 0.12,
) -> np.ndarray:
    """Return *n* signup dates between *start_date* and *end_date* (inclusive).

    A linear growth trend is applied so that later months receive
    approximately *growth_pct* (10-15 %) more sign-ups than earlier months,
    simulating a growing platform.

    All generated dates are guaranteed to fall within the dim_date range
    (config.DATA_START … config.DATA_END).

    Parameters
    ----------
    n : int
        Number of dates to generate.
    rng : np.random.RandomState
        Seeded random-state for reproducibility.
    start_date : datetime.date
        Earliest possible signup date (inclusive).
    end_date : datetime.date
        Latest possible signup date (inclusive).
    growth_pct : float
        Fractional increase from the first day to the last day.
        0.12 means the last day is ~12 % more likely than the first.

    Returns
    -------
    np.ndarray of datetime.date
        Array of length *n* with signup dates.
    """
    total_days = (end_date - start_date).days + 1  # inclusive

    # Build a linear weight ramp: w(t) = 1 + growth_pct * (t / (T-1))
    day_indices = np.arange(total_days)
    weights = 1.0 + growth_pct * (day_indices / max(total_days - 1, 1))
    weights /= weights.sum()  # normalise to probability distribution

    chosen_offsets = rng.choice(day_indices, size=n, replace=True, p=weights)
    base = np.datetime64(start_date, "D")
    dates_np = base + chosen_offsets.astype("timedelta64[D]")

    # Convert to Python date objects for clean CSV output
    return np.array([d.astype("datetime64[D]").astype(object) for d in dates_np])


# ============================================================================
# HELPER — unique email generator
# ============================================================================

_EMAIL_DOMAINS = [
    ("gmail.com", 0.40),
    ("yahoo.com", 0.20),
    ("outlook.com", 0.15),
    ("hotmail.com", 0.10),
    ("rediffmail.com", 0.10),
    ("company.com", 0.05),
]


def _generate_unique_emails(
    first_names: pd.Series,
    last_names: pd.Series,
    rng: np.random.RandomState,
) -> list[str]:
    """Build unique e-mails in the format ``first_last_XXXX@domain``.

    If a collision is detected the 4-digit suffix is re-rolled until the
    address is unique.  In practice, collisions are rare for 20 k rows.

    Parameters
    ----------
    first_names : pd.Series of str
    last_names  : pd.Series of str
    rng         : np.random.RandomState

    Returns
    -------
    list[str]
        List of unique email addresses, one per customer.
    """
    domains, domain_probs = zip(*_EMAIL_DOMAINS)
    domain_probs = np.array(domain_probs, dtype=float)
    domain_probs /= domain_probs.sum()  # safety normalise

    n = len(first_names)
    chosen_domains = rng.choice(list(domains), size=n, p=domain_probs)

    emails: list[str] = []
    seen: set[str] = set()

    for first, last, domain in zip(first_names, last_names, chosen_domains):
        # Sanitise names: lowercase, strip whitespace, replace spaces/dots
        f = first.lower().strip().replace(" ", "").replace(".", "")
        l = last.lower().strip().replace(" ", "").replace(".", "")

        # Try up to 100 times to get a unique suffix
        for _ in range(100):
            suffix = f"{rng.randint(0, 10_000):04d}"
            email = f"{f}_{l}_{suffix}@{domain}"
            if email not in seen:
                seen.add(email)
                emails.append(email)
                break
        else:
            # Extremely unlikely fallback: extend suffix length
            suffix = f"{rng.randint(0, 1_000_000):06d}"
            email = f"{f}_{l}_{suffix}@{domain}"
            seen.add(email)
            emails.append(email)

    return emails


# ============================================================================
# MAIN GENERATOR
# ============================================================================

def generate_customers(rng: np.random.RandomState) -> pd.DataFrame:
    """Generate a DataFrame of synthetic customers conforming to the PostgreSQL schema.

    All randomness flows through *rng* (and a Faker instance seeded identically)
    to guarantee reproducibility.

    Parameters
    ----------
    rng : np.random.RandomState
        Seeded random-state instance (use ``config.RANDOM_SEED``).

    Returns
    -------
    pd.DataFrame
        DataFrame with columns matching the dim_customers table schema:
        customer_id, first_name, last_name, email, gender, age_group,
        signup_date, city, state, region, country, customer_source,
        customer_segment.
    """
    n = config.TARGET_CUSTOMERS
    fake = Faker("en_IN")
    Faker.seed(config.RANDOM_SEED)

    # ------------------------------------------------------------------
    # 1. Names (Faker only for first_name / last_name)
    # ------------------------------------------------------------------
    first_names = pd.Series([fake.first_name() for _ in range(n)])
    last_names = pd.Series([fake.last_name() for _ in range(n)])

    # ------------------------------------------------------------------
    # 2. Emails (unique, numpy-driven domain selection)
    # ------------------------------------------------------------------
    emails = _generate_unique_emails(first_names, last_names, rng)

    # ------------------------------------------------------------------
    # 3. Gender
    # ------------------------------------------------------------------
    gender_labels = list(config.GENDER_DIST.keys())
    gender_probs = np.array(list(config.GENDER_DIST.values()), dtype=float)
    gender_probs /= gender_probs.sum()
    genders = rng.choice(gender_labels, size=n, p=gender_probs)

    # ------------------------------------------------------------------
    # 4. Age group
    # ------------------------------------------------------------------
    age_labels = list(config.AGE_GROUP_DIST.keys())
    age_probs = np.array(list(config.AGE_GROUP_DIST.values()), dtype=float)
    age_probs /= age_probs.sum()
    age_groups = rng.choice(age_labels, size=n, p=age_probs)

    # ------------------------------------------------------------------
    # 5. Signup dates (with growth trend)
    # ------------------------------------------------------------------
    signup_dates = _generate_signup_dates(n, rng)

    # ------------------------------------------------------------------
    # 6. Geography (city → state → region is a FIXED mapping)
    # ------------------------------------------------------------------
    cities_raw = [g[0] for g in config.GEOGRAPHY]
    states_raw = [g[1] for g in config.GEOGRAPHY]
    regions_raw = [g[2] for g in config.GEOGRAPHY]
    weights_raw = np.array([g[3] for g in config.GEOGRAPHY], dtype=float)
    weights_raw /= weights_raw.sum()  # normalise to sum = 1

    city_indices = rng.choice(len(cities_raw), size=n, p=weights_raw)

    cities = [cities_raw[i] for i in city_indices]
    states = [states_raw[i] for i in city_indices]
    regions = [regions_raw[i] for i in city_indices]

    # ------------------------------------------------------------------
    # 7. Customer source
    # ------------------------------------------------------------------
    source_labels = list(config.SOURCE_DIST.keys())
    source_probs = np.array(list(config.SOURCE_DIST.values()), dtype=float)
    source_probs /= source_probs.sum()
    sources = rng.choice(source_labels, size=n, p=source_probs)

    # ------------------------------------------------------------------
    # 8. Assemble DataFrame
    # ------------------------------------------------------------------
    df = pd.DataFrame(
        {
            "customer_id": np.arange(1, n + 1),
            "first_name": first_names.values,
            "last_name": last_names.values,
            "email": emails,
            "gender": genders,
            "age_group": age_groups,
            "signup_date": signup_dates,
            "city": cities,
            "state": states,
            "region": regions,
            "country": "India",
            "customer_source": sources,
            "customer_segment": "New",
        }
    )

    return df


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

def _print_summary(df: pd.DataFrame) -> None:
    """Print a human-readable summary of the generated customer data."""
    print("=" * 60)
    print("  CUSTOMER DATA GENERATION — SUMMARY")
    print("=" * 60)
    print(f"\n  Total customers : {len(df):,}")
    print(f"  Signup date range : {df['signup_date'].min()} to {df['signup_date'].max()}")
    print(f"  Unique emails     : {df['email'].nunique():,}")

    print("\n  Region Distribution:")
    region_counts = df["region"].value_counts()
    for region in ["North", "South", "East", "West", "Central"]:
        count = region_counts.get(region, 0)
        print(f"    {region:<10s} : {count:>6,}  ({count / len(df) * 100:5.1f}%)")

    print("\n  Gender Distribution:")
    gender_counts = df["gender"].value_counts()
    for gender in ["Male", "Female", "Other"]:
        count = gender_counts.get(gender, 0)
        print(f"    {gender:<10s} : {count:>6,}  ({count / len(df) * 100:5.1f}%)")

    print("\n  Age Group Distribution:")
    age_counts = df["age_group"].value_counts()
    for age in ["18-24", "25-34", "35-44", "45-54", "55+"]:
        count = age_counts.get(age, 0)
        print(f"    {age:<10s} : {count:>6,}  ({count / len(df) * 100:5.1f}%)")

    print("\n  Customer Source Distribution:")
    source_counts = df["customer_source"].value_counts()
    for source in config.SOURCE_DIST:
        count = source_counts.get(source, 0)
        print(f"    {source:<18s} : {count:>6,}  ({count / len(df) * 100:5.1f}%)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    rng = np.random.RandomState(config.RANDOM_SEED)
    customers_df = generate_customers(rng)

    # Ensure output directory exists
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    output_path = os.path.join(config.OUTPUT_DIR, "customers.csv")
    customers_df.to_csv(output_path, index=False)
    print(f"\n  [OK] Saved {len(customers_df):,} customers -> {output_path}\n")

    _print_summary(customers_df)
