# Advanced SQL Analytics Module

This directory contains highly optimized, production-ready PostgreSQL queries designed to compute advanced e-commerce metrics natively within the database engine.

## File Purpose & Categories

The queries have been logically grouped into the following files:

1. **`customer_analytics.sql`**: Focuses on user-level economics. Includes Customer Lifetime Value (CLV), 80/20 Pareto revenue concentration analysis, and a sophisticated RFM (Recency, Frequency, Monetary) data-driven segmentation query using percentiles.
2. **`retention_analytics.sql`**: Focuses on platform stickiness. Includes Repeat Purchase Rate calculations, median purchase interval analysis using `LAG()` window functions, and an advanced Cohort Analysis Matrix anchored on the user's first purchase date.
3. **`product_analytics.sql`**: Focuses on inventory economics. Computes exact unit-level gross profit and margin percentages, rolling up from the SKU level to the Category/Sub-category level.
4. **`regional_analytics.sql`**: Focuses on geographic performance. Analyzes unique customer penetration and revenue contribution across shipping states and regions using `SUM() OVER(PARTITION BY)`.
5. **`executive_kpis.sql`**: Focuses on high-level dashboard feeds. Includes Payment Method Analysis (to track AOV differences between COD and Credit) and a single unified query that pulls global hero metrics (Total Revenue, Blended Margin, AOV).

## Execution Guide

These scripts are written in standard PostgreSQL syntax. They are primarily `SELECT` statements (not materialized views or stored procedures) and are safe to run against production data, though it is highly recommended to execute the heavier analytical queries (like Cohort Analysis and Pareto) against a Read-Replica.

To execute a specific module via psql:
```bash
psql -U your_username -d your_ecommerce_db -f sql/analytics/customer_analytics.sql
```

Each query is prepended with a detailed block comment documenting:
*   **Business Purpose**
*   **Query Explanation**
*   **Expected Insight**
*   **Performance Notes** (including recommended indexes to support the query structure).
