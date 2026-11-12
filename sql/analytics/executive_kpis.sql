/* =========================================================================
   EXECUTIVE KPIs MODULE
   Contains: Payment Method Analysis & High-Level Aggregations
   ========================================================================= */

/* -------------------------------------------------------------------------
   1. Payment Method Performance Analysis
   
   Business Purpose: Understand how payment instruments affect cart size (AOV) 
                     and overall volume. Cash-on-Delivery (COD) vs Prepaid.
   Query Explanation: Standard group by calculating Average Order Value (AOV).
   Expected Insight: Credit cards and UPI typically drive higher AOVs compared 
                     to COD or wallets.
   Performance Notes: Fast query.
   ------------------------------------------------------------------------- */
SELECT 
    payment_method,
    COUNT(order_id) AS total_orders,
    SUM(total_amount) AS total_revenue,
    ROUND(AVG(total_amount), 2) AS average_order_value
FROM orders
WHERE order_status = 'Completed'
GROUP BY payment_method
ORDER BY total_revenue DESC;


/* -------------------------------------------------------------------------
   2. Executive Summary KPI Dashboard
   
   Business Purpose: A single query to feed the top "hero numbers" of a BI 
                     dashboard (Total Revenue, Total Customers, AOV, Gross Margin).
   Query Explanation: Uses CROSS JOIN to blend independent aggregations from 
                      the `orders` and `order_items`/`products` tables into 
                      a single wide row.
   Expected Insight: A high-level snapshot of the business's overall health.
   Performance Notes: Can be heavy if the tables are massive, as it scans 
                      multiple large tables independently.
   ------------------------------------------------------------------------- */
WITH order_kpis AS (
    SELECT 
        COUNT(DISTINCT customer_id) AS total_active_customers,
        COUNT(order_id) AS total_completed_orders,
        SUM(total_amount) AS gross_revenue,
        AVG(total_amount) AS global_aov
    FROM orders
    WHERE order_status = 'Completed'
),
margin_kpis AS (
    SELECT 
        SUM(oi.line_total - (oi.quantity * p.unit_cost)) AS total_gross_profit,
        (SUM(oi.line_total - (oi.quantity * p.unit_cost)) / SUM(oi.line_total)) * 100 AS blended_gross_margin_pct
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.order_status = 'Completed'
)
SELECT 
    o.total_active_customers,
    o.total_completed_orders,
    o.gross_revenue,
    o.global_aov,
    m.total_gross_profit,
    m.blended_gross_margin_pct
FROM order_kpis o
CROSS JOIN margin_kpis m;
