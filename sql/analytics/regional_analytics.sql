/* =========================================================================
   REGIONAL ANALYTICS MODULE
   Contains: Geographic performance
   ========================================================================= */

/* -------------------------------------------------------------------------
   1. Regional Performance Analysis
   
   Business Purpose: Identify high-performing and lagging geographies to 
                     optimize logistics and localized marketing spend.
   Query Explanation: Groups order data by region and state, calculating 
                      penetration (unique customers) and volume. 
                      Uses window function SUM() OVER(PARTITION BY region) 
                      to calculate the state's percentage contribution to its region.
   Expected Insight: Which states are carrying their regions, and which 
                     regions are dragging down national averages.
   Performance Notes: Standard aggregation. Index on orders(shipping_region).
   ------------------------------------------------------------------------- */
WITH regional_base AS (
    SELECT 
        shipping_region AS region,
        shipping_state AS state,
        COUNT(DISTINCT customer_id) AS unique_customers,
        COUNT(order_id) AS total_orders,
        SUM(total_amount) AS total_revenue
    FROM orders
    WHERE order_status = 'Completed'
    GROUP BY 
        shipping_region,
        shipping_state
)
SELECT 
    region,
    state,
    unique_customers,
    total_orders,
    total_revenue,
    SUM(total_revenue) OVER (PARTITION BY region) AS region_total_revenue,
    ROUND((total_revenue / SUM(total_revenue) OVER (PARTITION BY region)) * 100, 2) AS pct_of_region_revenue
FROM regional_base
ORDER BY 
    region_total_revenue DESC,
    total_revenue DESC;
