// =========================================================================
// POWER QUERY (M) SCRIPTS FOR E-COMMERCE DASHBOARD
// To use: Open Power Query Editor > Advanced Editor > Paste query
// Note: Update "BasePath" if your project folder is located elsewhere.
// =========================================================================

// 1. Analytical Master Table (Fact)
let
    // Update the project folder path below if cloned on a different directory
    BasePath = "C:\Users\eldan\OneDrive\Desktop\e-commerce",
    Source = Csv.Document(File.Contents(BasePath & "\data\analytics\analytical_master_table.csv"),[Delimiter=",", Columns=30, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    PromoteHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangeTypes = Table.TransformColumnTypes(PromoteHeaders,{
        {"order_id", Int64.Type}, 
        {"customer_id", Int64.Type}, 
        {"product_id", Int64.Type}, 
        {"order_date", type date}, 
        {"first_purchase_date", type date},
        {"latest_purchase_date", type date},
        {"quantity", Int64.Type}, 
        {"unit_price", type number}, 
        {"discount_percent", type number}, 
        {"line_total", type number}, 
        {"shipping_cost", type number}, 
        {"total_amount", type number},
        {"customer_tenure_days", Int64.Type},
        {"days_since_last_purchase", Int64.Type},
        {"total_orders", Int64.Type},
        {"total_revenue", type number},
        {"gross_profit", type number},
        {"gross_margin_pct", type number}
    })
in
    ChangeTypes

// 2. Customer Segments (Dimension)
let
    BasePath = "C:\Users\eldan\OneDrive\Desktop\e-commerce",
    Source = Csv.Document(File.Contents(BasePath & "\data\analytics\customer_segments.csv"),[Delimiter=",", Columns=6, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    PromoteHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangeTypes = Table.TransformColumnTypes(PromoteHeaders,{
        {"customer_id", Int64.Type}, 
        {"total_orders", Int64.Type}, 
        {"lifetime_revenue", type number}, 
        {"recency_days", Int64.Type}, 
        {"segment", type text}
    })
in
    ChangeTypes

// 3. Cohort Retention Rates (Dimension/Fact Hybrid)
let
    BasePath = "C:\Users\eldan\OneDrive\Desktop\e-commerce",
    Source = Csv.Document(File.Contents(BasePath & "\data\analytics\cohort_retention_rates.csv"),[Delimiter=",", Columns=14, Encoding=1252, QuoteStyle=QuoteStyle.None]),
    PromoteHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    // We unpivot the month columns so it can be graphed easily in Power BI
    UnpivotOtherColumns = Table.UnpivotOtherColumns(PromoteHeaders, {"cohort_month"}, "Month_Index", "Retention_Rate"),
    ChangeTypes = Table.TransformColumnTypes(UnpivotOtherColumns,{
        {"cohort_month", type date}, 
        {"Month_Index", Int64.Type}, 
        {"Retention_Rate", type number}
    })
in
    ChangeTypes
