# Exploratory Data Analysis

## Dataset profile

The supplied file has 500 rows and 10 columns. It spans 2024-01-01 to 2024-01-25 across 25 dates, with 311 distinct product identifiers and 30 supplier identifiers. There are 24 rows participating in repeated product/date keys.

No invalid rows were excluded (0); missing values before validation: 0; exact duplicate rows: 0.

## Findings

- Distinct observed products by category: Electronics: 115, HomeDecor: 114, Apparel: 112, Grocery: 103.
- 44 of 311 products in the selected latest observation are at or below their source reorder level.
- The replenishment-gap ranking uses RandomForestRegressor daily-sales predictions for the current date; it is exploratory, not validated future-demand accuracy.
- Recorded daily-sales values have mean 32.05, median 32.00, and range 5–60 units per row.
- Per-date recorded-sales means range from 22.75 to 37.80; row counts vary from 20 to 20.
- The latest snapshot is selected by date; tied product/date records are reduced only for per-product plots by keeping the last source row. The original processed observations remain intact.

## Data limitations

These are sparse inventory observations, not a complete daily sales history. Most products appear only once or twice, product/date keys repeat, and there are no product names or supplier contact/pricing terms. Daily-sales model predictions use an augmented dataset containing synthetic observations, have not been established as real-world accuracy, and must not be interpreted as validated future-demand forecasts. The other charts describe recorded rows or the selected latest snapshot.

## Figures

1. `figures/products_by_category.png` — distinct observed products per category.
2. `figures/stock_vs_reorder.png` — latest selected stock versus source reorder level.
3. `figures/daily_sales_distribution.png` — distribution of observed daily-sales values.
4. `figures/inventory_risk.png` — model-estimated replenishment-gap ranking from latest selected product rows.
