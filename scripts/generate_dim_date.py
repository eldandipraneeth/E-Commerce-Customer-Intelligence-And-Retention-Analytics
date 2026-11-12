"""
generate_dim_date.py — Generate the dim_date dimension table CSV.

This module creates a date dimension covering every calendar day from
config.DATA_START (2024-01-01) to config.DATA_END (2025-12-31), producing
exactly 731 rows (366 for leap-year 2024 + 365 for 2025).

The date dimension is a standard analytics artefact that lets downstream
queries join on date_key (an integer surrogate in YYYYMMDD form) while
exposing human-readable calendar attributes such as month name, quarter,
ISO week number, and weekend flag.

Generation logic:
    1. Build a DatetimeIndex from DATA_START to DATA_END (inclusive).
    2. Derive every column from the pandas Timestamp — no randomness, no
       external data.  ISO-8601 conventions are used for week_of_year
       (isocalendar().week) and day_of_week (Monday=1 … Sunday=7).
    3. is_weekend is True when day_of_week ∈ {6, 7} (Saturday or Sunday).

Currency / locale: not applicable (pure calendar table).
"""

import os
import pandas as pd

from config import DATA_START, DATA_END, OUTPUT_DIR


def generate_dim_date() -> pd.DataFrame:
    """Return a DataFrame with one row per calendar day between DATA_START
    and DATA_END (both inclusive).

    Returns
    -------
    pd.DataFrame
        Columns:
            date_key      – int, YYYYMMDD (e.g. 20240115)
            full_date     – str, 'YYYY-MM-DD'
            day_of_month  – int, 1–31
            month_number  – int, 1–12
            month_name    – str, e.g. 'January'
            quarter       – int, 1–4
            year          – int, e.g. 2024
            week_of_year  – int, ISO week 1–53
            day_of_week   – int, ISO day-of-week (1=Monday … 7=Sunday)
            day_name      – str, e.g. 'Monday'
            is_weekend    – bool, True for Saturday (6) and Sunday (7)
    """

    # ── 1. Create a continuous range of dates ──────────────────────────
    dates = pd.date_range(start=DATA_START, end=DATA_END, freq="D")

    # ── 2. Build the DataFrame from calendar attributes ────────────────
    df = pd.DataFrame(
        {
            # Surrogate integer key in YYYYMMDD format
            "date_key": dates.strftime("%Y%m%d").astype(int),
            # ISO-formatted date string
            "full_date": dates.strftime("%Y-%m-%d"),
            # Day within the month (1-31)
            "day_of_month": dates.day,
            # Calendar month number (1-12)
            "month_number": dates.month,
            # Full English month name
            "month_name": dates.strftime("%B"),
            # Calendar quarter (1-4)
            "quarter": dates.quarter,
            # Calendar year
            "year": dates.year,
            # ISO-8601 week number (1-53); note isocalendar is needed for
            # the correct ISO semantics (week starts on Monday, and the
            # week containing the year's first Thursday is week 1).
            "week_of_year": dates.isocalendar().week.astype(int),
            # ISO day-of-week: Monday=1 … Sunday=7
            # pandas .dayofweek returns 0=Mon..6=Sun, so we add 1.
            "day_of_week": dates.dayofweek + 1,
            # Full English weekday name
            "day_name": dates.strftime("%A"),
            # Weekend flag (Saturday=6, Sunday=7 in ISO)
            "is_weekend": (dates.dayofweek + 1).isin([6, 7]),
        }
    )

    return df


# ═══════════════════════════════════════════════════════════════════════════
# Standalone execution — write CSV and print diagnostics
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Generate the date dimension
    dim_date = generate_dim_date()

    # Persist to CSV (no pandas index column)
    output_path = os.path.join(OUTPUT_DIR, "dim_date.csv")
    dim_date.to_csv(output_path, index=False)

    # ── Diagnostics ────────────────────────────────────────────────────
    print(f"✅  dim_date written → {output_path}")
    print(f"    Rows : {len(dim_date)}")
    print(f"    Range: {dim_date['full_date'].iloc[0]}  →  "
          f"{dim_date['full_date'].iloc[-1]}")
    print("\n── First 5 rows ──")
    print(dim_date.head().to_string(index=False))
    print("\n── Last 5 rows ──")
    print(dim_date.tail().to_string(index=False))
