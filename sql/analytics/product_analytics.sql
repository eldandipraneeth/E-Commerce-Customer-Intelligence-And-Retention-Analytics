/* =========================================================================
   PRODUCT ANALYTICS MODULE
   Contains: Product Profitability, Category Performance
   ========================================================================= */

/* -------------------------------------------------------------------------
   1. Product Profitability Analysis
   
   Business Purpose: Identify the products driving the most profit (not just revenue)
                     to inform supply chain, pricing, and marketing priorities.
   Query Explanation: Joins `order_items` with `products`, recalculating the true 
                      gross margin after item-level discounts have been applied.
   Expected Insight: A ranked list of products showing absolute profit contribution 
                     and average Gross Margin %.
   Performance Notes: Ensure foreign keys (product_id) are indexed on order_items.
   ------------------------------------------------------------------------- */
WITH item_profitability AS (
    SELECT 
        p.product_id,
        p.product_name,
        c.category_name,
        oi.quantity,
        oi.line_total,
        (oi.quantity * p.unit_cost) AS total_cogs,
        oi.line_total - (oi.quantity * p.unit_cost) AS gross_profit
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    JOIN categories c ON p.category_id = c.category_id
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.order_status = 'Completed'
)
SELECT 
    product_id,
    product_name,
    category_name,
    SUM(quantity) AS total_units_sold,
    SUM(line_total) AS total_revenue,
    SUM(gross_profit) AS total_gross_profit,
    ROUND((SUM(gross_profit) / NULLIF(SUM(line_total), 0)) * 100, 2) AS blended_margin_pct
FROM item_profitability
GROUP BY 
    product_id,
    product_name,
    category_name
ORDER BY total_gross_profit DESC
LIMIT 50;


/* -------------------------------------------------------------------------
   2. Category Performance Analysis
   
   Business Purpose: Compare high-level business divisions (e.g. Electronics vs 
                     Clothing) to balance volume drivers with margin drivers.
   Query Explanation: Aggregates the profitability calculation up to the 
                      category/subcategory hierarchy.
   Expected Insight: Clear distinction between volume-heavy categories and 
                     margin-heavy categories.
   Performance Notes: Efficient query due to small dimension tables. 
   ------------------------------------------------------------------------- */
WITH category_totals AS (
    SELECT 
        c.category_name,
        c.sub_category,
        SUM(oi.quantity) AS total_units,
        SUM(oi.line_total) AS total_revenue,
        SUM(oi.line_total - (oi.quantity * p.unit_cost)) AS total_profit
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    JOIN categories c ON p.category_id = c.category_id
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.order_status = 'Completed'
    GROUP BY 
        c.category_name,
        c.sub_category
)
SELECT 
    category_name,
    sub_category,
    total_units,
    total_revenue,
    total_profit,
    ROUND((total_profit / NULLIF(total_revenue, 0)) * 100, 2) AS gross_margin_pct
FROM category_totals
ORDER BY total_revenue DESC;
