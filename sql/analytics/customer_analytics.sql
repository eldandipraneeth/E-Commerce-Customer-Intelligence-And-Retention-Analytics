/* =========================================================================
   CUSTOMER ANALYTICS MODULE
   Contains: CLV, Pareto Analysis, Customer Segmentation
   ========================================================================= */

/* -------------------------------------------------------------------------
   1. Customer Lifetime Value (CLV) & Top Revenue Customers (VIPs)
   
   Business Purpose: Identify the absolute most valuable customers across their 
                     entire lifecycle to prioritize VIP marketing efforts.
   Query Explanation: Uses CTEs to aggregate total spend per customer across all 
                      'Completed' orders, then applies RANK() to isolate the Top 100.
   Expected Insight: Returns the precise IDs, names, and total lifetime spend 
                     of the top spenders, allowing tailored "White Glove" outreach.
   Performance Notes: Ensure an INDEX exists on orders(customer_id) and 
                      orders(order_status) to speed up the join and filter.
   ------------------------------------------------------------------------- */
WITH customer_clv AS (
    SELECT 
        c.customer_id,
        c.first_name,
        c.last_name,
        c.email,
        COUNT(o.order_id) AS total_orders,
        SUM(o.total_amount) AS lifetime_revenue
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    WHERE o.order_status = 'Completed'
    GROUP BY 
        c.customer_id,
        c.first_name,
        c.last_name,
        c.email
),
ranked_vips AS (
    SELECT 
        *,
        RANK() OVER (ORDER BY lifetime_revenue DESC) AS revenue_rank
    FROM customer_clv
)
SELECT 
    revenue_rank,
    customer_id,
    first_name,
    last_name,
    email,
    total_orders,
    lifetime_revenue
FROM ranked_vips
WHERE revenue_rank <= 100
ORDER BY revenue_rank;


/* -------------------------------------------------------------------------
   2. Customer Pareto Analysis (80/20 Rule)
   
   Business Purpose: Determine the exact concentration of revenue to prove 
                     if a small subset of customers drives the majority of sales.
   Query Explanation: Uses SUM() OVER() to calculate a running total of revenue 
                      ordered by customer spend, then divides by the grand total 
                      to find the cumulative percentage.
   Expected Insight: Validates revenue concentration risk. E.g., "The top 20% of 
                     customers generate 78% of the revenue."
   Performance Notes: Window functions over the entire dataset can be heavy. 
                      Pre-calculating customer-level totals in a materialized 
                      view is recommended for massive datasets.
   ------------------------------------------------------------------------- */
WITH customer_totals AS (
    SELECT 
        customer_id,
        SUM(total_amount) AS customer_revenue
    FROM orders
    WHERE order_status = 'Completed'
    GROUP BY customer_id
),
running_totals AS (
    SELECT 
        customer_id,
        customer_revenue,
        SUM(customer_revenue) OVER (ORDER BY customer_revenue DESC) AS cumulative_revenue,
        SUM(customer_revenue) OVER () AS grand_total_revenue,
        ROW_NUMBER() OVER (ORDER BY customer_revenue DESC) AS row_num,
        COUNT(*) OVER () AS total_customers
    FROM customer_totals
)
SELECT 
    row_num,
    customer_id,
    customer_revenue,
    cumulative_revenue,
    ROUND((cumulative_revenue / grand_total_revenue) * 100, 2) AS cumulative_revenue_pct,
    ROUND((row_num::numeric / total_customers::numeric) * 100, 2) AS customer_percentile
FROM running_totals
WHERE (row_num::numeric / total_customers::numeric) <= 0.20
ORDER BY row_num;


/* -------------------------------------------------------------------------
   3. RFM Data-Driven Customer Segmentation
   
   Business Purpose: Categorize the active user base into targeted groups 
                     (VIP, At-Risk, Loyal, Regular) for lifecycle marketing.
   Query Explanation: Computes Recency, Frequency, and Monetary metrics, computes 
                      global percentiles using `percentile_cont`, and assigns 
                      segments via a CASE statement.
   Expected Insight: An exact headcount and revenue breakdown of the 4 key 
                     marketing segments to guide strategy allocation.
   Performance Notes: Extensive aggregation and percentile window functions. 
                      Run during off-peak hours or against a read-replica.
   ------------------------------------------------------------------------- */
WITH rfm_base AS (
    SELECT 
        customer_id,
        COUNT(order_id) AS total_orders,
        SUM(total_amount) AS lifetime_revenue,
        MAX(order_date) AS latest_purchase_date,
        MIN(order_date) AS first_purchase_date,
        (SELECT MAX(order_date) FROM orders WHERE order_status = 'Completed') - MAX(order_date) AS recency_days,
        (SELECT MAX(order_date) FROM orders WHERE order_status = 'Completed') - MIN(order_date) AS tenure_days
    FROM orders
    WHERE order_status = 'Completed'
    GROUP BY customer_id
),
thresholds AS (
    SELECT 
        percentile_cont(0.90) WITHIN GROUP (ORDER BY lifetime_revenue) AS p90_revenue,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY recency_days) AS p75_recency
    FROM rfm_base
),
segmented_customers AS (
    SELECT 
        r.customer_id,
        r.total_orders,
        r.lifetime_revenue,
        r.recency_days,
        CASE 
            WHEN r.lifetime_revenue >= t.p90_revenue THEN 'VIP'
            WHEN r.total_orders > 1 AND r.recency_days > t.p75_recency THEN 'At-Risk'
            WHEN r.total_orders >= 3 THEN 'Loyal'
            ELSE 'Regular'
        END AS segment
    FROM rfm_base r
    CROSS JOIN thresholds t
)
SELECT 
    segment,
    COUNT(customer_id) AS customer_count,
    ROUND(SUM(lifetime_revenue), 2) AS total_revenue,
    ROUND(AVG(total_orders), 2) AS avg_orders,
    ROUND(AVG(recency_days), 0) AS avg_recency_days
FROM segmented_customers
GROUP BY segment
ORDER BY total_revenue DESC;
