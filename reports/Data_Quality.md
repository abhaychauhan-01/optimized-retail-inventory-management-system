# Data Quality Report

- Source rows: 500
- Cleaned rows: 500
- Invalid rows excluded by documented validation: 0
- Exact duplicate rows: 0
- Rows participating in duplicate (date, product_id) keys: 24
- Unique products / suppliers: 311 / 30
- Observation dates: 2024-01-01 through 2024-01-25

## Missing Values Before Row Validation

- `date`: 0
- `product_id`: 0
- `category`: 0
- `season`: 0
- `stock_qty`: 0
- `reorder_level`: 0
- `daily_sales`: 0
- `unit_cost`: 0
- `supplier_id`: 0
- `lead_days`: 0

## Numeric Ranges After Cleaning

- `stock_qty`: 0 to 500
- `reorder_level`: 20 to 100
- `daily_sales`: 5 to 60
- `unit_cost`: withheld (pricing-sensitive; validated as numeric and non-negative)
- `lead_days`: 3 to 21

## Rules and Limitations

Required columns are checked against the supplied schema. Unparseable dates, missing or empty identifiers, non-numeric values, negative quantities/cost/lead times, and fractional values in integer fields are excluded and counted. Exact duplicate rows are reported; no otherwise-valid rows are deduplicated. Duplicate product/date keys remain in the cleaned output because the source provides no rule for resolving conflicting observations.
The file is sparse: a product can have multiple dated snapshots, but the observations are not a complete daily series. `daily_sales` is therefore treated as an observed source field, not evidence of continuous historical demand.
