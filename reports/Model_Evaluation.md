# Daily Sales Regression Evaluation

## Results

- Model: **RandomForestRegressor**
- Dataset: `data/raw/dataset_augmented.csv` (mixed; 500 source rows and 4500 synthetic rows)
- Training / evaluation observations: 4087 / 913
- Chronological training dates: 2024-01-01 to 2024-10-18
- Chronological testing dates: 2024-10-19 to 2024-12-31
- MAE / RMSE / R²: 15.0637 / 17.9665 / -0.0207
- Features: category, season, stock_qty, reorder_level, unit_cost, lead_days, date_month, date_day_of_week, date_day_of_year
- Repeated product/calendar-date excess rows retained: 65 (129 participating rows)

## Limitations

This is an exploratory supervised regression fit against the supplied `daily_sales` column, not validated future-demand forecasting. The augmented dataset contains generated observations; the reported holdout metrics can be optimistic or otherwise unrepresentative of real retail operations. The 500 matched source rows are identified as original-file records, but their provenance does not independently establish that they are genuine transaction history.

The chronological split assigns every observation on the same calendar date to one side of the holdout. Repeated product/date rows were retained; this can overweight repeated records despite avoiding same-day train/test leakage. The model supplies daily estimates to Demand Estimate and the existing deterministic reorder formulas. This integration does not make the estimates validated future-demand forecasts.

Training timestamp: `2026-10-30T17:06:15+00:00`.
