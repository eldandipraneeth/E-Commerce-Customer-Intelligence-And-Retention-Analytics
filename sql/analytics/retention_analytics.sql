/* =========================================================================
   RETENTION ANALYTICS MODULE
   Contains: Repeat Purchase Rate, Purchase Interval, Cohort Analysis
   ========================================================================= */

/* -------------------------------------------------------------------------
   1. Repeat Purchase Analysis
   
   Business Purpose: Determine the split between One-Time buyers and Repeat 
                     buyers to measure fundamental platform stickiness.
   Query Explanation: Aggregates total orders per customer, then uses conditional 
                      aggregation (SUM(CASE...)) to count One-Time vs Repeaters.
   Expected Insight: The overarching Repeat Purchase Rate (e.g. 36%), serving 
                     as the north star metric for the retention team.
   Performance Notes: A highly efficient full table scan with basic Group By. 
                      Suitable for frequent dashboard refreshes.
   ------------------------------------------------------------------------- */
WITH customer_order_counts AS (
    SELECT 
        customer_id,
        COUNT(order_id) AS completed_orders
    FROM orders
    WHERE order_status = 'Completed'
    GROUP BY customer_id
)
SELECT 
    COUNT(customer_id) AS total_customers,
    SUM(CASE WHEN completed_orders = 1 THEN 1 ELSE 0 END) AS one_time_buyers,
    SUM(CASE WHEN completed_orders > 1 THEN 1 ELSE 0 END) AS repeat_buyers,
    ROUND(
        SUM(CASE WHEN completed_orders > 1 THEN 1 ELSE 0 END)::numeric / 
        COUNT(customer_id)::numeric * 100, 2
    ) AS repeat_purchase_rate_pct
FROM customer_order_counts;


/* -------------------------------------------------------------------------
   2. Customer Retention / Purchase Interval Analysis
   
   Business Purpose: Discover the "Golden Window" for retargeting by measuring 
                     exactly how long it takes a returning customer to buy again.
   Query Explanation: Uses the LAG() window function to fetch the customer's 
                      previous order date, then extracts the days between orders.
   Expected Insight: The average number of days between sequential orders.
   Performance Notes: LAG() requires sorting the entire partition by customer_id 
                      and order_date. Ensure a composite index exists on 
                      (customer_id, order_date).
   ------------------------------------------------------------------------- */
WITH order_gaps AS (
    SELECT 
        customer_id,
        order_date,
        LAG(order_date) OVER (PARTITION BY customer_id ORDER BY order_date) AS prev_order_date
    FROM orders
    WHERE order_status = 'Completed'
),
days_between AS (
    SELECT 
        customer_id,
        order_date,
        prev_order_date,
        (order_date - prev_order_date) AS days_since_last_order
    FROM order_gaps
    WHERE prev_order_date IS NOT NULL
)
SELECT 
    ROUND(AVG(days_since_last_order), 1) AS avg_days_between_purchases,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY days_since_last_order) AS median_days_between_purchases
FROM days_between;


/* -------------------------------------------------------------------------
   3. Monthly Cohort Analysis (Retention Matrix)
   
   Business Purpose: Track long-term user decay by cohorting users based on 
                     their exact month of first purchase.
   Query Explanation: Identifies the first purchase month for each customer. 
                      Then, joins all subsequent orders and calculates the 
                      'month_index' (months elapsed since cohort month).
                      Finally, pivots data out to Month 0, 1, 2, 3.
   Expected Insight: A matrix identifying exactly when cohorts drop off (e.g. 
                     seeing a 95% drop between Month 0 and Month 1).
   Performance Notes: Requires self-joining or heavy window functions. This 
                      query is notoriously expensive on large datasets and 
                      should be materialized.
   ------------------------------------------------------------------------- */
WITH first_purchases AS (
    SELECT 
        customer_id,
        DATE_TRUNC('month', MIN(order_date)) AS cohort_month
    FROM orders
    WHERE order_status = 'Completed'
    GROUP BY customer_id
),
cohort_data AS (
    SELECT 
        fp.cohort_month,
        DATE_TRUNC('month', o.order_date) AS order_month,
        o.customer_id,
        EXTRACT(year FROM age(DATE_TRUNC('month', o.order_date), fp.cohort_month)) * 12 + 
        EXTRACT(month FROM age(DATE_TRUNC('month', o.order_date), fp.cohort_month)) AS month_index
    FROM orders o
    JOIN first_purchases fp ON o.customer_id = fp.customer_id
    WHERE o.order_status = 'Completed'
)
SELECT 
    TO_CHAR(cohort_month, 'YYYY-MM') AS cohort,
    COUNT(DISTINCT customer_id) AS initial_size,
    COUNT(DISTINCT CASE WHEN month_index = 1 THEN customer_id END) AS month_1_retained,
    COUNT(DISTINCT CASE WHEN month_index = 2 THEN customer_id END) AS month_2_retained,
    COUNT(DISTINCT CASE WHEN month_index = 3 THEN customer_id END) AS month_3_retained,
    COUNT(DISTINCT CASE WHEN month_index = 4 THEN customer_id END) AS month_4_retained
FROM cohort_data
GROUP BY cohort_month
ORDER BY cohort_month;
