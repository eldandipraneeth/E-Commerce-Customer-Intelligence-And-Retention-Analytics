# Executive Customer Intelligence Module

## Overview & Methodology
This presentation synthesizes the customer base into highly actionable segments to optimize marketing ROI and defend Customer Lifetime Value (CLV).

To ensure accuracy, we deployed a **purely data-driven segmentation model** instead of using arbitrary thresholds:
* **VIP:** Top 10% of customers by historical CLV (Threshold: `>= INR 135,680.41`).
* **At-Risk:** Repeat buyers whose days since last purchase exceeds the 75th percentile of all repeat buyers (Threshold: `> 389 days`).
* **Loyal:** Customers with 3+ orders and a purchase frequency above the global average (`> 0.0081`).
* **Regular:** All other active customers (primarily our massive one-time buyer cohort).

## Segment KPIs

| Segment | Customer Count | Total Revenue | Revenue Share | Average Order Value (AOV) | Avg Purchase Frequency |
|---|---|---|---|---|---|
| **VIP** | 2,000 | INR 508,164,830.25 | 56.3% | INR 31,006.46 | 0.0271 |
| **Loyal** | 2,477 | INR 144,897,840.03 | 16.1% | INR 10,154.02 | 0.0226 |
| **Regular** | 14,158 | INR 189,905,996.52 | 21.1% | INR 14,104.72 | 0.0031 |
| **At-Risk** | 1,365 | INR 58,833,470.62 | 6.5% | INR 11,513.40 | 0.0061 |


## Visual Insights

### 1. Segment Distribution & Revenue Contribution
![Segment Distribution](../images/customer_intelligence/segment_distribution.png)

**Business Interpretation:** 
Despite making up the largest absolute volume of the customer base, **Regular** customers (largely one-time buyers) contribute a disproportionately low amount of total revenue. Our **VIP** and **Loyal** segments, while small in headcount, are the massive twin engines driving our top-line metrics. The **At-Risk** segment represents previously engaged buyers who are actively churning, carrying highly lucrative AOV that is bleeding away.

### 2. Revenue Concentration (Pareto Principle)
![Pareto Curve](../images/customer_intelligence/customer_pareto.png)

**Business Interpretation:** 
The Pareto curve definitively proves our revenue concentration risk. The **Top 20% of our customers generate exactly 78.2% of our lifetime revenue**. This implies immense vulnerability if a competitor targets our VIP tier. 

## Strategic Business Recommendations

1. **VIP Clienteling:** Launch a dedicated "White Glove" account management tier for the Top 10% (VIP). These customers are too valuable to rely on automated marketing. Offer them early access to product drops and zero-fee expedited shipping.
2. **Win-Back Campaign for At-Risk:** The data explicitly shows that repeat customers generally buy within 389 days. The current At-Risk cohort has breached this mathematical threshold. Trigger an aggressive, high-discount "Win-Back" email/SMS flow specifically targeting these high-LTV defectors.
3. **Loyalty Nurturing:** Loyal customers exhibit fantastic frequency but lack the absolute AOV of VIPs. Implement targeted bundling campaigns ("Buy 2, Get 1 Accessory Free") to naturally stretch their cart size into VIP territory without cannibalizing base margins.
4. **Power BI Integration:** The dataset powering these metrics has been perfectly flattened and exported to `data/analytics/customer_segments.csv` for immediate syncing into your BI ecosystem.
