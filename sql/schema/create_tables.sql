-- ============================================================================
-- E-COMMERCE CUSTOMER INTELLIGENCE & SALES ANALYTICS PLATFORM
-- PostgreSQL Database Schema (DDL)
-- ============================================================================
-- Author  : Senior Data Architect
-- Engine  : PostgreSQL 15+
-- Purpose : Production-grade analytical schema following star-schema design
-- Tables  : categories, products, customers, orders, order_items
-- ============================================================================


-- ============================================================================
-- SECTION 1: CLEANUP (Idempotent Re-Runs)
-- ============================================================================
-- Drop tables in reverse dependency order to respect foreign key constraints.
-- Child tables (those that reference others) must be dropped before parent
-- tables, otherwise PostgreSQL will raise a dependency error.
--
-- Dependency chain:
--   order_items  depends on → orders, products
--   orders       depends on → customers
--   products     depends on → categories
--   customers    depends on → (none)
--   categories   depends on → (none)
-- ============================================================================

DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders       CASCADE;
DROP TABLE IF EXISTS products     CASCADE;
DROP TABLE IF EXISTS customers    CASCADE;
DROP TABLE IF EXISTS categories   CASCADE;
DROP TABLE IF EXISTS dim_date     CASCADE;


-- ============================================================================
-- SECTION 2: DIMENSION TABLES
-- ============================================================================
-- Dimension tables are loaded first because fact tables reference them
-- via foreign keys. In a star schema, dimensions describe the "who, what,
-- where" context around each transactional fact.
-- ============================================================================


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: categories
-- ────────────────────────────────────────────────────────────────────────────
-- ROLE       : Dimension table — product classification hierarchy
-- GRAIN      : One row per unique (category_name, sub_category) combination
-- REFERENCED BY : products.category_id (FK)
--
-- DESIGN NOTES:
--   • Two-level hierarchy (category → sub_category) in a single table keeps
--     the schema simple while enabling drill-down from "Electronics" →
--     "Smartphones" in Power BI / SQL GROUP BY queries.
--   • Normalized out of products to avoid repeating category strings across
--     hundreds of product rows and to prevent update anomalies.
--   • UNIQUE constraint on (category_name, sub_category) prevents duplicate
--     classification entries — e.g., two rows both saying "Electronics > Laptops".
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE categories (

    -- Primary Key: Surrogate integer key for efficient joins and indexing.
    -- SERIAL auto-generates sequential IDs (PostgreSQL shorthand for
    -- INTEGER + DEFAULT nextval(sequence)).
    category_id     SERIAL          PRIMARY KEY,

    -- Top-level product grouping (e.g., "Electronics", "Clothing").
    -- VARCHAR(50) is generous for category names; NOT NULL ensures every
    -- row has a valid classification.
    category_name   VARCHAR(50)     NOT NULL,

    -- Granular classification within a category (e.g., "Smartphones", "Laptops").
    -- Enables sub-category-level reporting without requiring a separate table.
    sub_category    VARCHAR(50)     NOT NULL,

    -- BUSINESS RULE: No two rows should have the same category + sub_category
    -- combination. This prevents data quality issues during ETL loads.
    CONSTRAINT uq_category_subcategory UNIQUE (category_name, sub_category)
);

-- Rationale: Queries frequently GROUP BY or filter on category_name alone
-- (e.g., "total revenue by category"). This index accelerates those lookups.
CREATE INDEX idx_categories_name ON categories (category_name);

COMMENT ON TABLE categories IS 'Dimension: Two-level product hierarchy (category → sub_category). Referenced by products.';
COMMENT ON COLUMN categories.category_id   IS 'Surrogate PK – auto-incremented integer';
COMMENT ON COLUMN categories.category_name IS 'Top-level grouping: Electronics, Clothing, Home & Kitchen, etc.';
COMMENT ON COLUMN categories.sub_category  IS 'Granular classification within parent: Smartphones, Laptops, etc.';


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: products
-- ────────────────────────────────────────────────────────────────────────────
-- ROLE       : Dimension table — product catalog / master data
-- GRAIN      : One row per unique SKU / product
-- REFERENCED BY : order_items.product_id (FK)
-- REFERENCES    : categories.category_id  (FK)
--
-- DESIGN NOTES:
--   • Stores both unit_cost (COGS) and list_price to enable gross margin
--     and profitability analysis — a critical differentiator for senior-level
--     portfolio projects.
--   • list_price is the catalog/sticker price. The actual selling price at
--     the time of purchase is captured in order_items.unit_price, which may
--     be lower due to promotions. Comparing the two enables discount depth
--     and price erosion analysis.
--   • brand is stored as a VARCHAR column rather than a separate dimension
--     table — sufficient for GROUP BY brand analysis at this project's scope.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE products (

    -- Primary Key
    product_id      SERIAL          PRIMARY KEY,

    -- Foreign Key to categories dimension.
    -- Every product MUST belong to exactly one category-subcategory pair.
    -- ON DELETE RESTRICT prevents accidentally deleting a category that
    -- still has products referencing it.
    category_id     INTEGER         NOT NULL,

    -- Descriptive product name (e.g., "Samsung Galaxy S24 Ultra").
    -- VARCHAR(150) accommodates long product titles common in e-commerce.
    product_name    VARCHAR(150)    NOT NULL,

    -- Manufacturer / brand name (e.g., "Samsung", "Nike", "IKEA").
    -- Enables brand-level performance analysis and cross-brand comparison.
    brand           VARCHAR(75)     NOT NULL,

    -- Cost of Goods Sold per unit — what the retailer pays the supplier.
    -- NUMERIC(10,2) stores up to 99,999,999.99 with exact decimal precision.
    -- PostgreSQL NUMERIC is preferred over FLOAT for financial data because
    -- it avoids floating-point rounding errors.
    -- CHECK ensures cost is never negative.
    unit_cost       NUMERIC(10,2)   NOT NULL    CHECK (unit_cost >= 0),

    -- Standard retail / catalog price before any discounts.
    -- Must be strictly positive — a product cannot have a $0 list price.
    list_price      NUMERIC(10,2)   NOT NULL    CHECK (list_price > 0),

    -- BUSINESS RULE: Cost should not exceed list price under normal operations.
    -- This constraint catches data quality errors during ETL — e.g., a
    -- reversed cost/price entry that would produce negative margins.
    CONSTRAINT chk_cost_vs_price CHECK (unit_cost <= list_price),

    -- Foreign key relationship: products → categories
    CONSTRAINT fk_products_category
        FOREIGN KEY (category_id)
        REFERENCES categories (category_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- Rationale: Product performance queries join order_items → products → categories.
-- This index on category_id speeds up the products → categories leg of those joins.
CREATE INDEX idx_products_category ON products (category_id);

-- Rationale: Brand-level aggregation queries (revenue by brand, margin by brand)
-- benefit from a B-tree index on brand for fast grouping and filtering.
CREATE INDEX idx_products_brand ON products (brand);

COMMENT ON TABLE products IS 'Dimension: Product catalog with cost and pricing data. FK to categories; referenced by order_items.';
COMMENT ON COLUMN products.product_id   IS 'Surrogate PK – auto-incremented integer';
COMMENT ON COLUMN products.category_id  IS 'FK → categories.category_id – product classification';
COMMENT ON COLUMN products.product_name IS 'Full descriptive product title';
COMMENT ON COLUMN products.brand        IS 'Manufacturer or brand name for brand-level analytics';
COMMENT ON COLUMN products.unit_cost    IS 'COGS per unit – enables gross margin calculation';
COMMENT ON COLUMN products.list_price   IS 'Catalog/sticker price before any discounts';


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: customers
-- ────────────────────────────────────────────────────────────────────────────
-- ROLE       : Dimension table — customer master data
-- GRAIN      : One row per unique customer
-- REFERENCED BY : orders.customer_id (FK)
--
-- DESIGN NOTES:
--   • signup_date is the COHORT ANCHOR — every cohort analysis groups
--     customers by their signup month. Without this field, cohort retention
--     analysis is impossible.
--   • age_group is stored pre-bucketed ("25-34") rather than as a raw DOB.
--     This simplifies analysis and avoids PII sensitivity concerns.
--   • region is denormalized (derivable from state) but stored explicitly to
--     avoid repeated CASE/JOIN logic in every regional query. This is a
--     standard and accepted practice in analytical / data warehouse schemas.
--   • customer_segment stores the RFM-derived segment label. This is updated
--     periodically by the Python segmentation pipeline. Storing it in the
--     dimension enables Power BI slicers to filter all visuals by segment
--     without recomputing RFM on every dashboard refresh.
--   • customer_source tracks the acquisition channel, enabling CAC analysis
--     and CLV-by-channel reporting.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE customers (

    -- Primary Key
    customer_id     SERIAL          PRIMARY KEY,

    -- Customer name fields — used for display, not analytics.
    first_name      VARCHAR(50)     NOT NULL,
    last_name       VARCHAR(50)     NOT NULL,

    -- Email must be unique — serves as the natural key in practice.
    -- In production, this would be the primary deduplication field.
    email           VARCHAR(100)    NOT NULL    UNIQUE,

    -- Demographic fields for persona analysis.
    -- CHECK constraints enforce a controlled vocabulary, acting like an
    -- ENUM but with more flexibility for future additions.
    gender          VARCHAR(10)     NOT NULL
                    CHECK (gender IN ('Male', 'Female', 'Other')),

    age_group       VARCHAR(20)     NOT NULL
                    CHECK (age_group IN ('18-24', '25-34', '35-44', '45-54', '55+')),

    -- *** COHORT ANCHOR ***
    -- The single most important date in the entire schema for retention
    -- and cohort analysis. Customers are grouped into monthly cohorts
    -- based on this date (e.g., "Jan-2024 cohort").
    signup_date     DATE            NOT NULL,

    -- Multi-level geography for regional intelligence.
    -- Drill path: region → state → city (coarse to fine).
    city            VARCHAR(75)     NOT NULL,
    state           VARCHAR(75)     NOT NULL,
    region          VARCHAR(50)     NOT NULL
                    CHECK (region IN ('North', 'South', 'East', 'West', 'Central')),
    country         VARCHAR(50)     NOT NULL    DEFAULT 'India',

    -- Acquisition channel — how the customer discovered the platform.
    -- Critical for CLV-by-channel and CAC efficiency analysis.
    customer_source VARCHAR(50)     NOT NULL
                    CHECK (customer_source IN (
                        'Organic Search', 'Paid Ads', 'Social Media',
                        'Referral', 'Direct', 'Email Campaign'
                    )),

    -- RFM-derived customer segment label.
    -- Updated periodically by the Python analytics pipeline.
    -- DEFAULT 'New' for freshly registered customers with no purchase history.
    -- Power BI slicers use this field to filter dashboards by segment.
    customer_segment VARCHAR(30)    NOT NULL    DEFAULT 'New'
                     CHECK (customer_segment IN (
                         'Champions', 'Loyal Customers', 'Potential Loyalists',
                         'Recent Customers', 'Promising', 'Needs Attention',
                         'About to Sleep', 'At Risk', 'Cannot Lose Them',
                         'Hibernating', 'Lost', 'New'
                     ))
);

-- Rationale: Cohort analysis queries frequently filter/group on signup_date
-- (e.g., DATE_TRUNC('month', signup_date)). A B-tree index on this column
-- accelerates those scans dramatically on 20,000+ rows.
CREATE INDEX idx_customers_signup ON customers (signup_date);

-- Rationale: Regional intelligence queries filter customers by region.
-- This index supports WHERE region = 'South' or GROUP BY region.
CREATE INDEX idx_customers_region ON customers (region);

-- Rationale: Customer segment is used as a slicer/filter in Power BI and
-- in SQL WHERE clauses to isolate specific segments (e.g., "At Risk").
CREATE INDEX idx_customers_segment ON customers (customer_segment);

-- Rationale: Acquisition channel analysis groups customers by source.
CREATE INDEX idx_customers_source ON customers (customer_source);

COMMENT ON TABLE customers IS 'Dimension: Customer master with demographics, geography, acquisition source, and RFM segment. Referenced by orders.';
COMMENT ON COLUMN customers.customer_id     IS 'Surrogate PK – auto-incremented integer';
COMMENT ON COLUMN customers.email           IS 'Unique email – natural key for deduplication';
COMMENT ON COLUMN customers.gender          IS 'Demographic: Male / Female / Other';
COMMENT ON COLUMN customers.age_group       IS 'Pre-bucketed age range for demographic analysis';
COMMENT ON COLUMN customers.signup_date     IS '*** COHORT ANCHOR *** – date of account creation; defines cohort membership';
COMMENT ON COLUMN customers.region          IS 'Denormalized geographic region for fast GROUP BY (North/South/East/West/Central)';
COMMENT ON COLUMN customers.customer_source IS 'Acquisition channel: Organic Search, Paid Ads, Social Media, Referral, Direct, Email Campaign';
COMMENT ON COLUMN customers.customer_segment IS 'RFM-derived segment label – updated by analytics pipeline; used as Power BI slicer';


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: dim_date
-- ────────────────────────────────────────────────────────────────────────────
-- ROLE       : Dimension table — calendar / date dimension (Kimball-style)
-- GRAIN      : One row per calendar day (no gaps)
-- REFERENCED BY : orders.order_date  (natural join on full_date)
--                 customers.signup_date (natural join on full_date)
--
-- WHY THIS TABLE EXISTS:
--   Power BI's built-in time intelligence functions — SAMEPERIODLASTYEAR,
--   TOTALYTD, DATEADD, PARALLELPERIOD, etc. — have a hard requirement:
--   they ONLY work when the date column belongs to a dedicated Date Table
--   that is:
--     (a) Marked as a "Date Table" in Power BI (Table Tools → Mark as Date Table)
--     (b) Contiguous — one row for EVERY calendar day, with NO gaps
--     (c) Covers the full range of dates in the fact tables
--   Without this table, YoY/MoM comparisons, rolling averages, and
--   period-over-period calculations will NOT function.
--
-- DESIGN NOTES:
--   • date_key uses the YYYYMMDD integer format (e.g., 20240115 for
--     Jan 15, 2024). This is the Kimball data warehouse standard for date
--     surrogate keys — compact, sortable, human-readable, and join-efficient.
--   • full_date (DATE type) is the natural join column. orders.order_date
--     and customers.signup_date join to dim_date.full_date.
--   • Pre-computed attributes (month_name, quarter, is_weekend, etc.)
--     eliminate repeated date-part extraction in SQL, DAX, and Python.
--   • The table should span 2024-01-01 through 2025-12-31 (731 rows) to
--     cover the full data window with buffer on both sides.
--
-- POWER BI SETUP (after import):
--   1. Select the dim_date table in the Model view
--   2. Table Tools → Mark as Date Table → select full_date
--   3. Create relationships:
--        orders.order_date      → dim_date.full_date (Many-to-One)
--        customers.signup_date  → dim_date.full_date (Many-to-One)
--   4. Set both relationships to single-direction cross-filter
--      (dimension → fact), which is the default
--   5. Hide date_key from Report view (used only for sorting)
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE dim_date (

    -- Primary Key: Integer surrogate in YYYYMMDD format.
    -- NOT auto-incremented — values are deterministic (20240101, 20240102, ...).
    -- Integer keys are more efficient for joins and sorts than DATE types
    -- in large-scale warehouses. At this project's scale the difference is
    -- negligible, but using YYYYMMDD is the industry-standard convention
    -- and demonstrates data warehouse design literacy.
    date_key        INTEGER         PRIMARY KEY,

    -- The actual calendar date. This is the JOIN column.
    -- UNIQUE ensures no duplicate dates (one row per day, guaranteed).
    -- orders.order_date and customers.signup_date reference this column.
    full_date       DATE            NOT NULL    UNIQUE,

    -- Day of the month (1–31).
    -- Useful for day-of-month patterns (e.g., payday spikes on 1st/15th).
    day_of_month    SMALLINT        NOT NULL    CHECK (day_of_month BETWEEN 1 AND 31),

    -- Calendar month number (1–12).
    -- Sort key for month_name (Power BI sorts text alphabetically by default;
    -- without a numeric sort column, "April" appears before "January").
    month_number    SMALLINT        NOT NULL    CHECK (month_number BETWEEN 1 AND 12),

    -- Full month name for display in reports and chart axes.
    -- Sorted by month_number in Power BI (Sort by Column feature).
    month_name      VARCHAR(15)     NOT NULL,

    -- Calendar quarter (1–4).
    -- Enables quarterly aggregation: Q1 = Jan–Mar, Q2 = Apr–Jun, etc.
    quarter         SMALLINT        NOT NULL    CHECK (quarter BETWEEN 1 AND 4),

    -- Calendar year (e.g., 2024, 2025).
    -- Primary filter for YoY comparisons.
    year            SMALLINT        NOT NULL    CHECK (year BETWEEN 2020 AND 2030),

    -- ISO week number (1–53).
    -- Enables weekly aggregation for operational dashboards.
    week_of_year    SMALLINT        NOT NULL    CHECK (week_of_year BETWEEN 1 AND 53),

    -- Day of the week (1 = Monday, 7 = Sunday, ISO standard).
    -- Sort key for day_name. Enables weekday-vs-weekend analysis.
    day_of_week     SMALLINT        NOT NULL    CHECK (day_of_week BETWEEN 1 AND 7),

    -- Full day name for display ("Monday", "Tuesday", ...).
    -- Sorted by day_of_week in Power BI (Sort by Column feature).
    day_name        VARCHAR(15)     NOT NULL,

    -- Weekend flag for weekend-vs-weekday segmentation.
    -- TRUE = Saturday or Sunday. Pre-computed to avoid repeated
    -- CASE WHEN day_of_week IN (6,7) logic in every query.
    is_weekend      BOOLEAN         NOT NULL,

    -- BUSINESS RULE: date_key must encode the same date as full_date.
    -- E.g., full_date = '2024-03-15' must have date_key = 20240315.
    -- This is enforced during data generation, not via a CHECK
    -- (CHECK cannot reference EXTRACT on another column in standard SQL).
    -- Documented here for data pipeline awareness.

    -- BUSINESS RULE: The table must be CONTIGUOUS — one row for every
    -- calendar day from 2024-01-01 through 2025-12-31. No gaps allowed.
    -- A gap would cause Power BI time intelligence to silently produce
    -- incorrect period-over-period calculations.
    -- Validated during data generation with: COUNT(*) = expected_days.

    CONSTRAINT chk_date_range CHECK (
        full_date >= '2024-01-01' AND full_date <= '2025-12-31'
    )
);

-- Rationale: The primary join pattern is orders.order_date = dim_date.full_date.
-- The UNIQUE constraint on full_date already creates an implicit unique index,
-- so no additional index is needed for the join column.

-- Rationale: Month-level aggregation queries (GROUP BY year, month_number)
-- benefit from this composite index for fast monthly rollups.
CREATE INDEX idx_dim_date_year_month ON dim_date (year, month_number);

-- Rationale: Quarter-level aggregation queries (GROUP BY year, quarter)
-- for quarterly KPI reports and QoQ comparisons.
CREATE INDEX idx_dim_date_year_quarter ON dim_date (year, quarter);

COMMENT ON TABLE dim_date IS 'Dimension: Calendar date table (Kimball-style). One row per day, contiguous, no gaps. Required for Power BI time intelligence. Join on full_date.';
COMMENT ON COLUMN dim_date.date_key     IS 'Surrogate PK – integer in YYYYMMDD format (e.g., 20240315). Sort-friendly, human-readable.';
COMMENT ON COLUMN dim_date.full_date    IS 'Actual calendar date – JOIN column for orders.order_date and customers.signup_date';
COMMENT ON COLUMN dim_date.day_of_month IS 'Day of month (1–31). Useful for payday-spike analysis.';
COMMENT ON COLUMN dim_date.month_number IS 'Month (1–12). Sort key for month_name in Power BI.';
COMMENT ON COLUMN dim_date.month_name   IS 'Full month name (January–December). Display label; sort by month_number.';
COMMENT ON COLUMN dim_date.quarter      IS 'Calendar quarter (1–4). Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec.';
COMMENT ON COLUMN dim_date.year         IS 'Calendar year (2024, 2025). Primary YoY comparison filter.';
COMMENT ON COLUMN dim_date.week_of_year IS 'ISO week number (1–53). Weekly operational reporting.';
COMMENT ON COLUMN dim_date.day_of_week  IS 'Day of week (1=Mon, 7=Sun, ISO). Sort key for day_name.';
COMMENT ON COLUMN dim_date.day_name     IS 'Full day name (Monday–Sunday). Display label; sort by day_of_week.';
COMMENT ON COLUMN dim_date.is_weekend   IS 'TRUE = Saturday/Sunday. Pre-computed weekend flag.';


-- ============================================================================
-- SECTION 3: FACT TABLES
-- ============================================================================
-- Fact tables store transactional events. They reference dimension tables
-- via foreign keys and contain the numeric measures (amounts, quantities)
-- that analytics queries aggregate.
-- ============================================================================


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: orders
-- ────────────────────────────────────────────────────────────────────────────
-- ROLE       : Fact table (order header) — one row per transaction
-- GRAIN      : One row per unique customer order
-- REFERENCED BY : order_items.order_id (FK)
-- REFERENCES    : customers.customer_id  (FK)
--
-- DESIGN NOTES:
--   • This is the PRIMARY table for time-series analysis, retention tracking,
--     repeat purchase counting, and regional sales intelligence.
--   • Shipping geography is SEPARATE from customer home geography because
--     customers may ship to different locations (gifts, offices). Regional
--     sales analysis should use shipping address (where demand exists).
--   • Two-tier discount model:
--       - order-level: discount_amount (cart coupons, site-wide promos)
--       - line-level:  order_items.discount_percent (product-specific deals)
--     Together they enable comprehensive discount impact analysis.
--   • order_status is critical for accurate revenue reporting. Cancelled and
--     Returned orders must be filterable — including them inflates all metrics.
--   • shipping_cost enables true profitability:
--     Net Profit = Revenue − COGS − Discounts − Shipping
--   • is_first_order is a pre-computed boolean flag identifying each customer's
--     chronologically first completed order. WITHOUT this flag, every repeat
--     purchase query requires a window function:
--       ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date)
--     and every Power BI measure would need a complex CALCULATE + FILTER +
--     EARLIER pattern. Storing the flag eliminates this overhead entirely.
--     Populated during data generation; updated if order history changes.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE orders (

    -- Primary Key
    order_id        SERIAL          PRIMARY KEY,

    -- Foreign Key to customers dimension.
    -- Every order MUST be placed by a registered customer.
    -- ON DELETE RESTRICT prevents deleting a customer who has order history
    -- (critical for maintaining referential integrity in analytics).
    customer_id     INTEGER         NOT NULL,

    -- Date the order was placed.
    -- DATE type (not TIMESTAMP) — daily granularity is sufficient for this
    -- analytical project. Hourly/minute analysis would require TIMESTAMP.
    -- This field drives: time-series trends, MoM growth, retention matrices,
    -- inter-purchase interval calculations, and seasonality analysis.
    order_date      DATE            NOT NULL,

    -- Current fulfillment status.
    -- CHECK constraint enforces a controlled vocabulary.
    -- *** CRITICAL FILTER: Revenue queries MUST use WHERE order_status = 'Completed' ***
    -- Forgetting this filter is one of the most common analytical errors.
    order_status    VARCHAR(20)     NOT NULL
                    CHECK (order_status IN (
                        'Completed', 'Processing', 'Cancelled', 'Returned'
                    )),

    -- Payment instrument used.
    -- Enables payment method preference analysis by region and segment.
    payment_method  VARCHAR(30)     NOT NULL
                    CHECK (payment_method IN (
                        'Credit Card', 'Debit Card', 'UPI',
                        'Net Banking', 'COD', 'Wallet'
                    )),

    -- Shipping destination geography (separate from customer home address).
    -- Drill path: shipping_region → shipping_state → shipping_city.
    shipping_city    VARCHAR(75)    NOT NULL,
    shipping_state   VARCHAR(75)    NOT NULL,
    shipping_region  VARCHAR(50)    NOT NULL
                     CHECK (shipping_region IN ('North', 'South', 'East', 'West', 'Central')),
    shipping_country VARCHAR(50)    NOT NULL    DEFAULT 'India',

    -- Order-level discount (flat amount, not percentage).
    -- Captures cart-level coupons and site-wide promotional discounts.
    -- Separate from line-item discounts in order_items.discount_percent.
    discount_amount  NUMERIC(10,2)  NOT NULL    DEFAULT 0.00
                     CHECK (discount_amount >= 0),

    -- Delivery/shipping charges.
    -- Essential for true profitability analysis. Many orders have free shipping
    -- (0.00) which is itself an analytical insight (free shipping conversion impact).
    shipping_cost    NUMERIC(10,2)  NOT NULL    DEFAULT 0.00
                     CHECK (shipping_cost >= 0),

    -- Final order total AFTER discounts, INCLUDING shipping.
    -- This is the source-of-truth revenue figure — what the customer actually paid.
    -- Must be positive (a $0 order has no business meaning).
    total_amount     NUMERIC(12,2)  NOT NULL    CHECK (total_amount > 0),

    -- Pre-computed flag: TRUE if this is the customer's first completed order.
    -- DEFAULT FALSE because most orders are not first orders (only 1 per customer).
    --
    -- HOW IT WILL BE POPULATED (during Python data generation):
    --   1. Group all orders by customer_id
    --   2. Sort each customer's orders by order_date ASC
    --   3. Mark the FIRST order with order_status = 'Completed' as TRUE
    --   4. All other orders for that customer remain FALSE
    --   Tie-breaker: if a customer has two orders on the same date,
    --   the one with the lower order_id is treated as first.
    --
    -- Equivalent SQL (for validation, not used at generation time):
    --   UPDATE orders o SET is_first_order = TRUE
    --   FROM (
    --       SELECT DISTINCT ON (customer_id) order_id
    --       FROM orders
    --       WHERE order_status = 'Completed'
    --       ORDER BY customer_id, order_date, order_id
    --   ) first_orders
    --   WHERE o.order_id = first_orders.order_id;
    --
    -- HOW IT SUPPORTS RETENTION ANALYSIS:
    --   • First-order date = customer's "activation" date in the purchase
    --     lifecycle. Retention is measured from this point forward.
    --   • Instant filtering: WHERE is_first_order = TRUE gives the exact
    --     first-purchase cohort without any windowing or subqueries.
    --   • First-order-to-second-order interval ("time to repeat") becomes
    --     a simple join between the first order and the next order.
    --
    -- HOW IT SIMPLIFIES POWER BI REPORTING:
    --   • Without this flag, calculating "new vs. returning customers" in
    --     DAX requires:
    --       New Customers = CALCULATE(
    --           DISTINCTCOUNT(orders[customer_id]),
    --           FILTER(
    --               orders,
    --               orders[order_date] = CALCULATE(
    --                   MIN(orders[order_date]),
    --                   ALLEXCEPT(orders, orders[customer_id])
    --               )
    --           )
    --       )
    --     This is verbose, error-prone, and slow on large datasets.
    --
    --   • WITH this flag, the same measure becomes:
    --       New Customers = CALCULATE(
    --           DISTINCTCOUNT(orders[customer_id]),
    --           orders[is_first_order] = TRUE
    --       )
    --     Clean, performant, and readable.
    --
    --   • Additional Power BI simplifications:
    --       - "First Order Revenue" = SUM where is_first_order = TRUE
    --       - "Repeat Order Revenue" = SUM where is_first_order = FALSE
    --       - "Repeat Purchase Rate" = Returning / Total customers
    --       - Slicer: is_first_order as a visual-level filter
    --       - Conditional formatting: highlight first orders in detail tables
    is_first_order   BOOLEAN         NOT NULL    DEFAULT FALSE,

    -- Foreign key relationship: orders → customers
    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- *** MOST CRITICAL INDEX IN THE SCHEMA ***
-- Rationale: The majority of analytical queries need to find all orders for a
-- specific customer sorted by date. This composite index serves:
--   • CLV:             SUM(total_amount) WHERE customer_id = X
--   • Retention:       orders per customer per month since signup
--   • Repeat Purchase: COUNT(*) and LAG(order_date) OVER (PARTITION BY customer_id)
--   • Cohort Analysis: join customers.signup_date with orders grouped by customer
-- The (customer_id, order_date) order is optimal because customer_id is the
-- partition key and order_date is the sort key within each customer's orders.
CREATE INDEX idx_orders_customer_date ON orders (customer_id, order_date);

-- Rationale: Regional sales queries aggregate by shipping_region + time period.
-- This composite index accelerates:
--   WHERE shipping_region = 'South' AND order_date BETWEEN ... AND ...
CREATE INDEX idx_orders_region_date ON orders (shipping_region, order_date);

-- Rationale: Time-series queries (monthly revenue, MoM growth, seasonality)
-- scan orders by date range. A standalone date index supplements the
-- composite indexes above for queries that don't filter on customer or region.
CREATE INDEX idx_orders_date ON orders (order_date);

-- Rationale: Status-filtered queries (WHERE order_status = 'Completed') run
-- on nearly every revenue report. This index helps PostgreSQL quickly
-- skip Cancelled/Returned rows, especially beneficial when combined with
-- other WHERE conditions.
CREATE INDEX idx_orders_status ON orders (order_status);

-- Rationale: Repeat purchase analysis frequently filters on is_first_order.
-- A partial index on TRUE values is small (one row per customer) and enables
-- fast lookups for first-order cohorts, new customer counts, and
-- first-order revenue calculations.
CREATE INDEX idx_orders_first_order ON orders (customer_id, order_date)
    WHERE is_first_order = TRUE;

COMMENT ON TABLE orders IS 'Fact (header): One row per customer order. FK to customers; referenced by order_items. Primary table for time-series, retention, and regional analysis.';
COMMENT ON COLUMN orders.order_id        IS 'Surrogate PK – auto-incremented integer';
COMMENT ON COLUMN orders.customer_id     IS 'FK → customers.customer_id – who placed the order';
COMMENT ON COLUMN orders.order_date      IS 'Transaction date – drives time-series, cohort, and retention analysis';
COMMENT ON COLUMN orders.order_status    IS 'Fulfillment status: Completed / Processing / Cancelled / Returned. *** ALWAYS FILTER FOR REVENUE QUERIES ***';
COMMENT ON COLUMN orders.payment_method  IS 'Payment instrument: Credit Card, Debit Card, UPI, Net Banking, COD, Wallet';
COMMENT ON COLUMN orders.shipping_region IS 'Delivery region – use for regional sales analysis (not customer home region)';
COMMENT ON COLUMN orders.discount_amount IS 'Order-level discount (flat ₹). Separate from line-item discount_percent.';
COMMENT ON COLUMN orders.shipping_cost   IS 'Delivery charges. ₹0 = free shipping.';
COMMENT ON COLUMN orders.total_amount    IS 'Source-of-truth revenue: final amount after discounts, including shipping';
COMMENT ON COLUMN orders.is_first_order  IS 'Pre-computed: TRUE for each customer''s chronologically first completed order. Enables simple new-vs-returning splits in Power BI without window functions.';


-- ────────────────────────────────────────────────────────────────────────────
-- TABLE: order_items
-- ────────────────────────────────────────────────────────────────────────────
-- ROLE       : Fact table (line-item detail) — most granular transactional table
-- GRAIN      : One row per product per order
-- REFERENCES : orders.order_id    (FK)
--              products.product_id (FK)
--
-- DESIGN NOTES:
--   • This is the PRIMARY table for product performance analysis, margin
--     calculations, cross-sell pattern mining, and ABC classification.
--   • unit_price captures the ACTUAL selling price at the time of purchase,
--     which may differ from products.list_price due to time-limited sales or
--     promotions. Comparing the two enables price erosion analysis.
--   • discount_percent is the LINE-ITEM discount (product-specific promo),
--     separate from the ORDER-LEVEL discount in orders.discount_amount.
--     This two-tier model mirrors real e-commerce systems.
--   • line_total is pre-calculated: quantity × unit_price × (1 − discount_percent/100).
--     Storing it avoids re-deriving in every query and acts as the
--     source of truth for line-level revenue.
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE order_items (

    -- Primary Key
    order_item_id   SERIAL          PRIMARY KEY,

    -- Foreign Key to orders fact table.
    -- ON DELETE CASCADE: if an order is deleted, its line items are
    -- automatically removed. This maintains referential integrity without
    -- orphaned line items.
    order_id        INTEGER         NOT NULL,

    -- Foreign Key to products dimension.
    -- ON DELETE RESTRICT: prevents deleting a product that has sales history.
    -- Historical order data must remain intact for analytics.
    product_id      INTEGER         NOT NULL,

    -- Number of units purchased in this line item.
    -- Must be at least 1. A customer can buy 3 units of the same product
    -- in one line item — standard e-commerce behavior.
    quantity        INTEGER         NOT NULL    CHECK (quantity >= 1),

    -- Actual selling price PER UNIT at the time of purchase.
    -- May differ from products.list_price due to promotions/sales.
    -- This captures the historical price — critical because product prices
    -- change over time, and analytics must reflect what was actually charged.
    unit_price      NUMERIC(10,2)   NOT NULL    CHECK (unit_price > 0),

    -- Line-item discount percentage (0.00 to 100.00).
    -- Represents product-specific promotions (e.g., "15% off all Nike shoes").
    -- 0.00 = no line discount applied.
    -- This is SEPARATE from orders.discount_amount (order-level coupon).
    discount_percent NUMERIC(5,2)   NOT NULL    DEFAULT 0.00
                     CHECK (discount_percent >= 0 AND discount_percent <= 100),

    -- Pre-calculated line total:
    --   line_total = quantity × unit_price × (1 − discount_percent / 100)
    -- Source of truth for line-level revenue. Must be positive.
    line_total      NUMERIC(12,2)   NOT NULL    CHECK (line_total > 0),

    -- Foreign key relationship: order_items → orders
    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id)
        REFERENCES orders (order_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    -- Foreign key relationship: order_items → products
    CONSTRAINT fk_order_items_product
        FOREIGN KEY (product_id)
        REFERENCES products (product_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

-- Rationale: Most order_items queries start by joining to a specific order.
-- This index accelerates the orders → order_items join path and also supports
-- queries that need all line items for a given order (e.g., order detail view).
CREATE INDEX idx_order_items_order ON order_items (order_id);

-- Rationale: Product performance queries aggregate across all order_items for
-- a specific product (total revenue per product, units sold per product).
-- This index accelerates WHERE product_id = X and GROUP BY product_id.
CREATE INDEX idx_order_items_product ON order_items (product_id);

-- Rationale: Cross-sell / market basket analysis queries need to find product
-- pairs within the same order. A composite index on (order_id, product_id)
-- optimizes self-joins like:
--   SELECT a.product_id, b.product_id
--   FROM order_items a JOIN order_items b ON a.order_id = b.order_id
--   WHERE a.product_id < b.product_id
CREATE INDEX idx_order_items_order_product ON order_items (order_id, product_id);

COMMENT ON TABLE order_items IS 'Fact (line-item): Most granular transaction table. One row per product per order. FK to orders and products.';
COMMENT ON COLUMN order_items.order_item_id   IS 'Surrogate PK – auto-incremented integer';
COMMENT ON COLUMN order_items.order_id        IS 'FK → orders.order_id – parent order';
COMMENT ON COLUMN order_items.product_id      IS 'FK → products.product_id – product purchased';
COMMENT ON COLUMN order_items.quantity         IS 'Units purchased (≥ 1)';
COMMENT ON COLUMN order_items.unit_price       IS 'Actual selling price per unit AT TIME OF PURCHASE (may differ from list_price)';
COMMENT ON COLUMN order_items.discount_percent IS 'Line-item discount % (0-100). Separate from order-level discount_amount.';
COMMENT ON COLUMN order_items.line_total       IS 'Pre-calculated: qty × unit_price × (1 − discount%/100). Source of truth for line revenue.';


-- ============================================================================
-- SECTION 4: RELATIONSHIP SUMMARY
-- ============================================================================
--
--  RELATIONSHIP                          TYPE        JOIN TYPE    RULE
--  ────────────────────────────────────────────────────────────────────────────
--  dim_date    → orders                 1 : Many    Natural Key  One calendar day can have many orders.
--               (full_date = order_date)                          An order falls on exactly one date.
--                                                                 Join: orders.order_date = dim_date.full_date
--                                                                 No FK constraint — enforced at ETL layer
--                                                                 to keep dim_date independent of fact tables.
--
--  dim_date    → customers              1 : Many    Natural Key  One calendar day can have many signups.
--               (full_date = signup_date)                         A customer signed up on exactly one date.
--                                                                 Join: customers.signup_date = dim_date.full_date
--                                                                 No FK constraint — same rationale as above.
--
--  categories  → products               1 : Many    FK           One category has many products.
--                                                                 A product belongs to exactly one category.
--                                                                 Deleting a category is RESTRICTED if
--                                                                 products reference it.
--
--  customers   → orders                 1 : Many    FK           One customer places many orders.
--                                                                 An order belongs to exactly one customer.
--                                                                 Deleting a customer is RESTRICTED if
--                                                                 orders reference them.
--
--  orders      → order_items            1 : Many    FK           One order contains many line items.
--                                                                 A line item belongs to exactly one order.
--                                                                 Deleting an order CASCADES to its
--                                                                 line items (no orphans).
--
--  products    → order_items            1 : Many    FK           One product appears in many line items.
--                                                                 A line item references exactly one product.
--                                                                 Deleting a product is RESTRICTED if
--                                                                 order_items reference it.
--
-- ============================================================================
--
-- WHY dim_date USES NATURAL-KEY JOINS (NOT FOREIGN KEYS):
--
--   In Kimball dimensional modeling, the date dimension is a "conformed
--   dimension" shared across multiple fact tables. Adding a FK from every
--   fact table to dim_date creates tight coupling:
--     • dim_date must be loaded BEFORE any fact table (load-order dependency)
--     • Reloading dim_date requires disabling/re-enabling FKs on all facts
--     • Adds INSERT overhead on high-volume fact tables for FK validation
--
--   Instead, the relationship is enforced:
--     • At the ETL layer (Python data generation ensures valid dates)
--     • At the BI layer (Power BI relationship: order_date → full_date)
--     • Via CHECK constraints (order_date range matches dim_date range)
--
--   This is the standard practice in production data warehouses.
--
-- ============================================================================


-- ============================================================================
-- SECTION 5: INDEX SUMMARY
-- ============================================================================
--
--  INDEX NAME                           TABLE          COLUMNS                       PURPOSE
--  ───────────────────────────────────────────────────────────────────────────────────────────────
--  (unique on full_date)                dim_date       (full_date)                   Implicit unique index from UNIQUE constraint; join target for fact tables
--  idx_dim_date_year_month              dim_date       (year, month_number)          Monthly rollup aggregation
--  idx_dim_date_year_quarter            dim_date       (year, quarter)               Quarterly KPI aggregation
--  idx_categories_name                  categories     (category_name)               Category-level GROUP BY and filtering
--  idx_products_category                products       (category_id)                 products → categories JOIN acceleration
--  idx_products_brand                   products       (brand)                       Brand-level aggregation and filtering
--  idx_customers_signup                 customers      (signup_date)                 Cohort assignment and date-range filtering
--  idx_customers_region                 customers      (region)                      Customer geographic distribution queries
--  idx_customers_segment                customers      (customer_segment)            RFM segment filtering (Power BI slicers)
--  idx_customers_source                 customers      (customer_source)             Acquisition channel analysis
--  idx_orders_customer_date  ***        orders         (customer_id, order_date)     CLV, retention, repeat purchase, cohort
--  idx_orders_region_date               orders         (shipping_region, order_date) Regional sales time-series
--  idx_orders_date                      orders         (order_date)                  Global time-series; also serves dim_date join
--  idx_orders_status                    orders         (order_status)                Status filtering (Completed only)
--  idx_order_items_order                order_items    (order_id)                    orders → order_items JOIN
--  idx_order_items_product              order_items    (product_id)                  Product-level aggregation
--  idx_order_items_order_product        order_items    (order_id, product_id)        Cross-sell / market basket self-joins
--
-- *** = Most critical index in the schema
--
-- ============================================================================
--
-- POWER BI DATA MODEL — RELATIONSHIP MAP
-- ============================================================================
--
--                          ┌───────────┐
--                          │  dim_date │
--                          │ (full_date)│
--                          └─────┬─────┘
--                         1      │      1
--                       ┌────────┴────────┐
--                       │                 │
--                  Many ▼                 ▼ Many
--            ┌───────────────┐    ┌────────────┐
--            │   customers   │    │   orders   │
--            │ (signup_date) │    │(order_date)│
--            └───────────────┘    └──────┬─────┘
--                       │          1    │
--                  1    │               │ Many
--                       ▼ Many          ▼
--                  ┌──────────┐  ┌─────────────┐
--                  │ (unused) │  │ order_items  │
--                  └──────────┘  └──────┬───────┘
--                                  Many │
--                                       │ 1
--                                       ▼
--                            ┌────────────────┐
--                            │    products    │
--                            └───────┬────────┘
--                               Many │
--                                    │ 1
--                                    ▼
--                            ┌────────────────┐
--                            │  categories    │
--                            └────────────────┘
--
--  All relationships: Single-direction filter (dimension → fact)
--  Active relationships: dim_date → orders (on order_date)
--  Inactive relationship: dim_date → customers (on signup_date)
--    → Use USERELATIONSHIP() DAX function when needed
--
-- ============================================================================


-- ============================================================================
-- SECTION 6: REVENUE RECONCILIATION LOGIC
-- ============================================================================
--
-- This section defines the EXACT mathematical relationships between all
-- financial fields across the orders and order_items tables. These rules
-- are the single source of truth for how revenue flows through the schema.
--
-- Any violation of these rules indicates a data quality defect that MUST
-- be resolved before analytics can be trusted. The validation queries at
-- the end of this section should be run after every data load.
--
-- ============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- 6.1  LINE-ITEM FORMULA (order_items table)
-- ─────────────────────────────────────────────────────────────────────────────
--
-- Each row in order_items represents one product line within an order.
-- The line_total is the revenue contribution of that line after applying
-- the line-item discount percentage.
--
-- FORMULA:
--
--   line_total = quantity × unit_price × (1 − discount_percent / 100)
--
-- EXAMPLE:
--   quantity = 2, unit_price = 49.99, discount_percent = 15.00
--   line_total = 2 × 49.99 × (1 − 15/100)
--              = 2 × 49.99 × 0.85
--              = 84.98 (rounded to 2 decimal places)
--
-- ROUNDING RULE:
--   line_total is stored as NUMERIC(12,2). During data generation, apply
--   ROUND(..., 2) after the multiplication to avoid sub-penny residuals.
--
-- TOLERANCE:
--   Due to floating-point arithmetic in Python (float64), a tolerance of
--   ±₹0.01 per line item is acceptable. This means:
--     ABS(line_total - ROUND(quantity * unit_price * (1 - discount_percent/100), 2)) <= 0.01
--
-- ─────────────────────────────────────────────────────────────────────────────


-- ─────────────────────────────────────────────────────────────────────────────
-- 6.2  ORDER-LEVEL FORMULA (orders table)
-- ─────────────────────────────────────────────────────────────────────────────
--
-- The orders.total_amount is the FINAL amount the customer pays. It is
-- derived from the sum of its line items, minus any order-level discount,
-- plus shipping charges.
--
-- FORMULA:
--
--   total_amount = SUM(order_items.line_total)     -- gross line revenue
--                − discount_amount                 -- order-level coupon
--                + shipping_cost                   -- delivery charges
--
-- EQUIVALENTLY:
--
--   SUM(order_items.line_total) = total_amount + discount_amount − shipping_cost
--
-- EXAMPLE:
--   Order #50002 has 3 line items:
--     Line 1: line_total =  84.98  (2× shirt at 15% off)
--     Line 2: line_total =  50.97  (3× book, no discount)
--     Line 3: line_total = 314.99  (1× headphones at 10% off)
--     ─────────────────────────────
--     SUM(line_total)    = 450.94
--
--   discount_amount = 200.00  (cart coupon: "SAVE200")
--   shipping_cost   =  49.00  (standard delivery)
--
--   total_amount = 450.94 − 200.00 + 49.00 = 299.94
--
-- TWO-TIER DISCOUNT MODEL:
--   ┌──────────────────────────────────────────────────────────────────┐
--   │  DISCOUNT LAYER        WHERE IT LIVES         EXAMPLE           │
--   │  ──────────────────────────────────────────────────────────────  │
--   │  Line-item discount    order_items.discount_percent   15% off   │
--   │                        (applied PER PRODUCT)          Nike      │
--   │                                                                  │
--   │  Order-level discount  orders.discount_amount         ₹200 off  │
--   │                        (applied to ENTIRE CART)       coupon    │
--   └──────────────────────────────────────────────────────────────────┘
--
--   Line-item discounts are ALREADY reflected in line_total.
--   Order-level discount is applied AFTER summing line totals.
--   These two layers are independent and can stack.
--
-- RECONCILIATION TOLERANCE:
--   ABS(total_amount − (SUM(line_total) − discount_amount + shipping_cost)) <= 0.02
--   The ₹0.02 tolerance accounts for cumulative rounding across multiple
--   line items (each rounded individually to 2 decimals).
--
-- ─────────────────────────────────────────────────────────────────────────────


-- ─────────────────────────────────────────────────────────────────────────────
-- 6.3  FULL REVENUE WATERFALL (cross-table)
-- ─────────────────────────────────────────────────────────────────────────────
--
-- The complete revenue flow from catalog price to net profit:
--
--   ┌─────────────────────────────────────────────────────────────────────────┐
--   │  STEP   METRIC                    SOURCE                               │
--   │  ─────────────────────────────────────────────────────────────────────  │
--   │   1     Catalog Revenue           SUM(quantity × products.list_price)   │
--   │   −     Price Adjustment          (list_price − unit_price) per item    │
--   │   =     Gross Line Revenue        SUM(order_items.line_total)           │
--   │   −     Line-Item Discounts       Already embedded in line_total        │
--   │   −     Order-Level Discounts     SUM(orders.discount_amount)           │
--   │   +     Shipping Revenue          SUM(orders.shipping_cost)             │
--   │   =     Net Revenue (total_amount) SUM(orders.total_amount)             │
--   │   −     COGS                      SUM(quantity × products.unit_cost)    │
--   │   =     Gross Profit                                                    │
--   │   −     Shipping Cost (if borne)  (operational, not in schema)          │
--   │   =     Net Profit                                                      │
--   └─────────────────────────────────────────────────────────────────────────┘
--
-- NOTE: In this schema, shipping_cost is revenue FROM the customer (what
-- they pay for delivery). The actual fulfillment cost to the retailer is
-- an operational expense NOT captured in this analytical schema.
--
-- ─────────────────────────────────────────────────────────────────────────────


-- ─────────────────────────────────────────────────────────────────────────────
-- 6.4  BUSINESS RULES & CONSTRAINTS
-- ─────────────────────────────────────────────────────────────────────────────
--
-- RULE 1: discount_amount MUST NOT exceed the sum of line totals.
--         A coupon cannot make the pre-shipping subtotal negative.
--         discount_amount <= SUM(order_items.line_total) for each order.
--
-- RULE 2: total_amount MUST be positive (enforced by CHECK > 0).
--         Even after the largest possible discount, shipping_cost must
--         compensate enough to keep the total above zero.
--
-- RULE 3: Every order MUST have at least one line item.
--         An order with zero line items has no revenue source and would
--         fail reconciliation. Enforced at the ETL layer.
--
-- RULE 4: unit_price SHOULD be <= products.list_price.
--         A product selling above list price is unusual. While not
--         schema-enforced (prices change over time), the data generation
--         script should ensure unit_price <= list_price at the time of
--         the order.
--
-- RULE 5: Cancelled / Returned orders still have line items.
--         The order_status flag filters them out of revenue queries, but
--         the line items remain for historical completeness. Reconciliation
--         applies to ALL orders regardless of status.
--
-- ─────────────────────────────────────────────────────────────────────────────


-- ============================================================================
-- 6.5  VALIDATION QUERIES (run after every data load)
-- ============================================================================
--
-- These queries should return ZERO rows if the data is consistent.
-- Any rows returned indicate reconciliation failures that must be fixed
-- before downstream analytics can be trusted.
-- ============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- VALIDATION 1: Line-Item Internal Consistency
-- ─────────────────────────────────────────────────────────────────────────────
-- Verifies: line_total = quantity × unit_price × (1 − discount_percent/100)
-- Tolerance: ±₹0.01 per line item
-- Expected: 0 rows (all line items internally consistent)
-- ─────────────────────────────────────────────────────────────────────────────

-- SELECT
--     order_item_id,
--     order_id,
--     product_id,
--     quantity,
--     unit_price,
--     discount_percent,
--     line_total                                                     AS stored_line_total,
--     ROUND(quantity * unit_price * (1 - discount_percent / 100), 2) AS expected_line_total,
--     line_total - ROUND(quantity * unit_price * (1 - discount_percent / 100), 2)
--                                                                    AS difference
-- FROM order_items
-- WHERE ABS(line_total - ROUND(quantity * unit_price * (1 - discount_percent / 100), 2)) > 0.01
-- ORDER BY ABS(line_total - ROUND(quantity * unit_price * (1 - discount_percent / 100), 2)) DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- VALIDATION 2: Order-Level Revenue Reconciliation
-- ─────────────────────────────────────────────────────────────────────────────
-- Verifies: total_amount = SUM(line_total) − discount_amount + shipping_cost
-- Tolerance: ±₹0.02 per order (cumulative rounding across multiple lines)
-- Expected: 0 rows (all orders reconcile)
-- ─────────────────────────────────────────────────────────────────────────────

-- SELECT
--     o.order_id,
--     o.customer_id,
--     o.order_date,
--     o.total_amount                                                 AS stored_total,
--     li.sum_line_total                                              AS sum_of_lines,
--     o.discount_amount,
--     o.shipping_cost,
--     (li.sum_line_total - o.discount_amount + o.shipping_cost)      AS expected_total,
--     o.total_amount - (li.sum_line_total - o.discount_amount + o.shipping_cost)
--                                                                    AS difference
-- FROM orders o
-- JOIN (
--     SELECT order_id, SUM(line_total) AS sum_line_total
--     FROM order_items
--     GROUP BY order_id
-- ) li ON o.order_id = li.order_id
-- WHERE ABS(o.total_amount - (li.sum_line_total - o.discount_amount + o.shipping_cost)) > 0.02
-- ORDER BY ABS(o.total_amount - (li.sum_line_total - o.discount_amount + o.shipping_cost)) DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- VALIDATION 3: Orphan Check — Orders Without Line Items
-- ─────────────────────────────────────────────────────────────────────────────
-- Verifies: Every order has at least one line item (RULE 3)
-- Expected: 0 rows (no orphan orders)
-- ─────────────────────────────────────────────────────────────────────────────

-- SELECT
--     o.order_id,
--     o.customer_id,
--     o.order_date,
--     o.total_amount
-- FROM orders o
-- LEFT JOIN order_items oi ON o.order_id = oi.order_id
-- WHERE oi.order_item_id IS NULL
-- ORDER BY o.order_id;


-- ─────────────────────────────────────────────────────────────────────────────
-- VALIDATION 4: Discount Sanity — Discount Does Not Exceed Line Subtotal
-- ─────────────────────────────────────────────────────────────────────────────
-- Verifies: discount_amount <= SUM(line_total) for each order (RULE 1)
-- Expected: 0 rows (no over-discounted orders)
-- ─────────────────────────────────────────────────────────────────────────────

-- SELECT
--     o.order_id,
--     o.discount_amount,
--     li.sum_line_total,
--     o.discount_amount - li.sum_line_total                          AS over_discount
-- FROM orders o
-- JOIN (
--     SELECT order_id, SUM(line_total) AS sum_line_total
--     FROM order_items
--     GROUP BY order_id
-- ) li ON o.order_id = li.order_id
-- WHERE o.discount_amount > li.sum_line_total
-- ORDER BY (o.discount_amount - li.sum_line_total) DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- VALIDATION 5: Price Integrity — unit_price Does Not Exceed list_price
-- ─────────────────────────────────────────────────────────────────────────────
-- Verifies: order_items.unit_price <= products.list_price (RULE 4)
-- Expected: 0 rows (no items sold above catalog price)
-- ─────────────────────────────────────────────────────────────────────────────

-- SELECT
--     oi.order_item_id,
--     oi.order_id,
--     oi.product_id,
--     p.product_name,
--     oi.unit_price                                                  AS sold_at,
--     p.list_price                                                   AS catalog_price,
--     oi.unit_price - p.list_price                                   AS overcharge
-- FROM order_items oi
-- JOIN products p ON oi.product_id = p.product_id
-- WHERE oi.unit_price > p.list_price
-- ORDER BY (oi.unit_price - p.list_price) DESC;


-- ─────────────────────────────────────────────────────────────────────────────
-- VALIDATION 6: is_first_order Integrity
-- ─────────────────────────────────────────────────────────────────────────────
-- Verifies: Exactly ONE order per customer is marked is_first_order = TRUE
--           (among Completed orders only)
-- Expected: 0 rows in both sub-checks
-- ─────────────────────────────────────────────────────────────────────────────

-- Sub-check A: Customers with MORE THAN ONE first order (duplicates)
-- SELECT
--     customer_id,
--     COUNT(*) AS first_order_count
-- FROM orders
-- WHERE is_first_order = TRUE
-- GROUP BY customer_id
-- HAVING COUNT(*) > 1;

-- Sub-check B: Customers with completed orders but NO first order flag
-- SELECT
--     o.customer_id,
--     COUNT(*) AS completed_orders
-- FROM orders o
-- WHERE o.order_status = 'Completed'
--   AND NOT EXISTS (
--       SELECT 1 FROM orders o2
--       WHERE o2.customer_id = o.customer_id
--         AND o2.is_first_order = TRUE
--   )
-- GROUP BY o.customer_id;


-- ─────────────────────────────────────────────────────────────────────────────
-- VALIDATION SUMMARY — EXPECTED RESULTS
-- ─────────────────────────────────────────────────────────────────────────────
--
--  #   VALIDATION                              EXPECTED ROWS   SEVERITY
--  ─────────────────────────────────────────────────────────────────────
--  1   Line-Item Internal Consistency          0               CRITICAL
--      → If fails: line_total was miscalculated during generation.
--        Impact: All product-level revenue metrics are wrong.
--
--  2   Order-Level Revenue Reconciliation      0               CRITICAL
--      → If fails: total_amount doesn't match its line items.
--        Impact: Order-level and line-level revenue reports diverge.
--        This is the MOST DAMAGING data quality issue.
--
--  3   Orphan Orders (no line items)           0               CRITICAL
--      → If fails: orders exist with no products.
--        Impact: Revenue exists at order level but is invisible at
--        product level. ABC analysis and margin reports are incomplete.
--
--  4   Discount Exceeds Subtotal               0               HIGH
--      → If fails: coupon gave more discount than the order was worth.
--        Impact: Negative pre-shipping subtotals; profitability is
--        artificially inflated by shipping_cost.
--
--  5   Price Exceeds Catalog                   0               MEDIUM
--      → If fails: a product was sold above its list_price.
--        Impact: Discount depth analysis produces negative percentages.
--        May be legitimate (price increase between order date and
--        current catalog) but unlikely in synthetic data.
--
--  6   is_first_order Integrity                0               HIGH
--      → If fails: duplicate or missing first-order flags.
--        Impact: New vs. returning customer counts are wrong;
--        repeat purchase rate is inaccurate.
--
-- ============================================================================


-- ============================================================================
-- SECTION 7: TEMPORAL INTEGRITY RULES
-- ============================================================================
--
-- This section defines the mandatory time-ordering constraints between
-- tables. These rules cannot be expressed as standard PostgreSQL CHECK
-- constraints (which are single-row, single-table), so they MUST be
-- enforced during data generation and validated post-load.
--
-- ============================================================================


-- ─────────────────────────────────────────────────────────────────────────────
-- 7.1  THE CORE RULE: order_date >= signup_date
-- ─────────────────────────────────────────────────────────────────────────────
--
-- RULE:
--   For every order, the order_date MUST be on or after the customer's
--   signup_date. A customer cannot place an order before they exist in
--   the system.
--
--   orders.order_date >= customers.signup_date
--   (for every row in orders, when joined to its customer)
--
-- WHY PostgreSQL CANNOT ENFORCE THIS:
--   CHECK constraints in PostgreSQL operate on a single row within a
--   single table. Cross-table validation (orders referencing a value in
--   customers) requires either:
--     (a) A trigger (adds complexity, not appropriate for a portfolio project)
--     (b) ETL-layer enforcement (our approach — simple, explicit, testable)
--
-- ─────────────────────────────────────────────────────────────────────────────


-- ─────────────────────────────────────────────────────────────────────────────
-- 7.2  WHY THIS RULE IS REQUIRED FOR COHORT ANALYSIS
-- ─────────────────────────────────────────────────────────────────────────────
--
-- Cohort analysis groups customers by their signup_month and tracks their
-- purchasing activity in subsequent months. The fundamental metric is:
--
--   months_since_signup = DATE_PART('month',
--       AGE(order_date, signup_date)
--   )
--
-- This value MUST be >= 0 for the cohort matrix to be valid.
--
--
-- WHAT HAPPENS IF order_date < signup_date (violation):
--
--   Suppose customer #10001 has:
--     signup_date = 2024-03-15
--     order_date  = 2024-01-20   ← VIOLATION (order 2 months BEFORE signup)
--
--   months_since_signup = DATE_PART('month', AGE('2024-01-20', '2024-03-15'))
--                       = -2     ← NEGATIVE VALUE
--
--   This produces a row in month "-2" of the cohort matrix — a month that
--   does not exist and has no business meaning.
--
--
-- IMPACT ON THE COHORT RETENTION MATRIX:
--
--   ┌─────────────────────────────────────────────────────────────────────┐
--   │                                                                     │
--   │  CORRECT MATRIX (all months_since_signup >= 0):                     │
--   │                                                                     │
--   │  Cohort     M0     M1     M2     M3     M4     M5                  │
--   │  ─────────────────────────────────────────────────                  │
--   │  Jan-2024   100%   35%    28%    22%    18%    15%                  │
--   │  Feb-2024   100%   38%    30%    24%    20%    —                    │
--   │  Mar-2024   100%   32%    26%    21%    —      —                    │
--   │                                                                     │
--   │  ✓ Monotonically decreasing (normal churn behavior)                │
--   │  ✓ M0 always = 100% (by definition: signup month)                  │
--   │  ✓ Clean triangular shape (later cohorts have fewer data points)   │
--   │                                                                     │
--   └─────────────────────────────────────────────────────────────────────┘
--
--   ┌─────────────────────────────────────────────────────────────────────┐
--   │                                                                     │
--   │  CORRUPTED MATRIX (violations present):                            │
--   │                                                                     │
--   │  Cohort     M-2    M-1    M0     M1     M2     M3                  │
--   │  ─────────────────────────────────────────────────                  │
--   │  Jan-2024   —      —      100%   35%    28%    22%                 │
--   │  Feb-2024   —      3%     100%   38%    30%    24%    ← IMPOSSIBLE │
--   │  Mar-2024   2%     5%     100%   32%    26%    21%    ← IMPOSSIBLE │
--   │                                                                     │
--   │  ✗ Negative month columns appear (M-2, M-1)                       │
--   │  ✗ Customers appear "active" before they signed up                 │
--   │  ✗ Retention rates in early months become inflated                 │
--   │  ✗ Power BI cohort heatmap renders extra columns on the left      │
--   │  ✗ Python pivot_table produces unexpected column order             │
--   │                                                                     │
--   └─────────────────────────────────────────────────────────────────────┘
--
-- ─────────────────────────────────────────────────────────────────────────────


-- ─────────────────────────────────────────────────────────────────────────────
-- 7.3  WHY THIS RULE IS REQUIRED FOR RETENTION METRICS
-- ─────────────────────────────────────────────────────────────────────────────
--
-- METRIC: Monthly Retention Rate
--
--   Retention_M(n) = Customers from cohort active in Month n
--                    ÷ Total customers in cohort
--                    × 100
--
-- "Active in Month n" means: the customer has at least one completed
-- order where months_since_signup = n.
--
-- If months_since_signup can be negative, the following breaks:
--
--   1. RETENTION RATE > 100%
--      A customer whose order falls in M-1 would be counted as active in
--      a month before their cohort started. If this customer is ALSO
--      active in M0, they get counted in both periods. The M0 retention
--      rate (which should always be 100% by construction) could exceed
--      100% in some calculation approaches — a logical impossibility.
--
--   2. CHURN RATE BECOMES NEGATIVE
--      Churn = 1 − Retention. If retention > 100%, churn goes negative.
--      A negative churn rate has no business meaning and will confuse
--      stakeholders.
--
--   3. TIME-TO-SECOND-PURCHASE GOES NEGATIVE
--      Time to second purchase = 2nd order_date − 1st order_date.
--      If the "first" order is before signup and the "second" is after,
--      the first order may actually not be the true first. The entire
--      inter-purchase interval analysis becomes unreliable.
--
--   4. CLV LIFESPAN DISTORTED
--      CLV = Avg. Order Value × Purchase Frequency × Customer Lifespan.
--      Customer lifespan = last_order_date − first_order_date.
--      If first_order_date < signup_date, the lifespan is artificially
--      inflated, pumping up CLV estimates.
--
--   5. POWER BI DAX MEASURES BREAK
--      Common DAX patterns for retention use:
--        DATEDIFF(customer[signup_date], orders[order_date], MONTH)
--      If this returns a negative integer, SWITCH/IF logic that maps
--      month numbers to column headers will hit unexpected ELSE branches
--      or produce blank/error cells in matrix visuals.
--
-- ─────────────────────────────────────────────────────────────────────────────


-- ─────────────────────────────────────────────────────────────────────────────
-- 7.4  DATA GENERATION ENFORCEMENT
-- ─────────────────────────────────────────────────────────────────────────────
--
-- The Python data generation script MUST enforce this rule using the
-- following approach:
--
-- APPROACH: Generate signup_date FIRST, then generate order_dates relative
-- to it. This makes violations structurally impossible.
--
-- PSEUDOCODE:
--
--   for each customer:
--       signup_date = random_date(START_DATE, END_DATE)
--
--       for each order belonging to this customer:
--           # Days between signup and the end of the data window
--           max_days_after_signup = (END_DATE - signup_date).days
--
--           # Order must fall within [signup_date, END_DATE]
--           days_offset = random_int(0, max_days_after_signup)
--           order_date  = signup_date + timedelta(days=days_offset)
--
--           # GUARANTEE: order_date >= signup_date (offset >= 0)
--
-- KEY IMPLEMENTATION DETAILS:
--
--   • days_offset = 0 is valid: a customer can order on their signup day.
--     This represents a customer who signs up and immediately purchases,
--     which is a common and realistic e-commerce pattern.
--
--   • The offset should NOT be uniformly distributed. Use a weighted
--     distribution that makes early orders (within first 30 days) more
--     likely, matching real-world behavior:
--       - 40% of first orders within 7 days of signup
--       - 25% of first orders within 8-30 days
--       - 20% of first orders within 31-90 days
--       - 15% of first orders after 90 days
--
--   • For REPEAT orders (2nd, 3rd, ...):
--       - Each subsequent order_date must be >= the previous order_date
--         for that customer (chronological ordering).
--       - Use an inter-purchase interval drawn from a realistic
--         distribution (e.g., median ~30 days, right-skewed).
--
-- ─────────────────────────────────────────────────────────────────────────────


-- ─────────────────────────────────────────────────────────────────────────────
-- 7.5  ADDITIONAL TEMPORAL RULES
-- ─────────────────────────────────────────────────────────────────────────────
--
-- RULE A: All dates within the data window.
--   signup_date  BETWEEN '2024-01-01' AND '2025-12-31'
--   order_date   BETWEEN '2024-01-01' AND '2025-12-31'
--   (Already enforced by CHECK constraints on orders and dim_date range)
--
-- RULE B: Orders are chronologically ordered per customer.
--   For each customer, when orders are sorted by order_date ASC, the
--   sequence must be temporally valid. While two orders CAN share the
--   same order_date (same-day purchases), no order should have an
--   order_date earlier than a previously placed order. This is naturally
--   satisfied by the data generation approach above (cumulative offsets).
--
-- RULE C: signup_date <= first order_date for dim_date consistency.
--   Both signup_date and order_date must exist in the dim_date table.
--   Since dim_date spans 2024-01-01 to 2025-12-31, and both dates are
--   constrained to that range, this is automatically satisfied.
--
-- ─────────────────────────────────────────────────────────────────────────────


-- ─────────────────────────────────────────────────────────────────────────────
-- 7.6  VALIDATION QUERY
-- ─────────────────────────────────────────────────────────────────────────────
-- Verifies: order_date >= signup_date for every order
-- Expected: 0 rows (no temporal violations)
-- Severity: CRITICAL — violations corrupt cohort analysis, retention
--           metrics, CLV lifespan, and repeat purchase intervals
-- ─────────────────────────────────────────────────────────────────────────────

-- VALIDATION 7: Temporal Integrity — order_date >= signup_date

-- SELECT
--     o.order_id,
--     o.customer_id,
--     c.signup_date,
--     o.order_date,
--     (o.order_date - c.signup_date)                                  AS days_difference,
--     DATE_PART('month', AGE(o.order_date, c.signup_date))            AS months_since_signup
-- FROM orders o
-- JOIN customers c ON o.customer_id = c.customer_id
-- WHERE o.order_date < c.signup_date
-- ORDER BY (o.order_date - c.signup_date) ASC;

-- If any rows are returned, the days_difference column will be NEGATIVE,
-- showing how many days the order precedes signup. Sort ascending to see
-- the worst violations first.


-- VALIDATION 8: Chronological Order Integrity — No Backward Jumps

-- SELECT
--     curr.order_id                                                   AS current_order,
--     curr.customer_id,
--     prev.order_date                                                 AS previous_order_date,
--     curr.order_date                                                 AS current_order_date,
--     (curr.order_date - prev.order_date)                             AS days_gap
-- FROM (
--     SELECT
--         order_id,
--         customer_id,
--         order_date,
--         LAG(order_date) OVER (
--             PARTITION BY customer_id ORDER BY order_date, order_id
--         ) AS prev_order_date
--     FROM orders
-- ) curr
-- JOIN orders prev ON curr.customer_id = prev.customer_id
--                  AND prev.order_date = curr.prev_order_date
-- WHERE curr.prev_order_date IS NOT NULL
--   AND curr.order_date < curr.prev_order_date;


-- ─────────────────────────────────────────────────────────────────────────────
-- UPDATED VALIDATION SUMMARY (adding validations 7 & 8)
-- ─────────────────────────────────────────────────────────────────────────────
--
--  #   VALIDATION                              EXPECTED ROWS   SEVERITY
--  ─────────────────────────────────────────────────────────────────────
--  7   Temporal: order_date >= signup_date     0               CRITICAL
--      → If fails: orders exist before customer registered.
--        Impact: Negative months_since_signup values corrupt the
--        cohort retention matrix, inflate CLV lifespan, and produce
--        retention rates > 100%. Power BI DAX DATEDIFF returns
--        negative months, breaking SWITCH/IF logic in matrix visuals.
--
--  8   Chronological Order Integrity           0               MEDIUM
--      → If fails: a customer's order sequence has backward jumps.
--        Impact: Inter-purchase interval analysis (LAG-based) would
--        produce negative gaps. Minor if order_date ties exist on
--        the same day (those are valid same-day purchases).
--
-- ============================================================================

