# Optimized Retail Inventory Management System

HCLTech Career Shaper Programme · Digital-Data-AI / AIML · Project 21

This repository contains a local-first inventory application with a React/TypeScript frontend, FastAPI API, SQLite database, Pandas data preparation, reproducible EDA, transparent reorder policy, and a forecasting suitability gate. Source datasets and trained model binaries are excluded because the source data includes non-public pricing. To run the data pipeline, provide the authorized source file as `data/raw/dataset.csv`.

## Data findings

The official file contains 500 rows, 10 columns, 311 product IDs, 30 supplier IDs, and 25 dates from 2024-01-01 to 2024-01-25. There are no missing values, negative numeric values, or exact duplicate rows. Twelve excess `(date, product_id)` rows affect 24 rows because the source contains repeated product/date keys. Products appear an average of 1.57 distinct dates (maximum 6). The original file is not a continuous product-level sales history. The app separately trains an exploratory regression on augmented data; this does not establish real-world prediction accuracy or validated forecasting. Supplier IDs are source identifiers, not verified supplier contacts.

## Requirements

- Python 3.11+ (validated here with Python 3.12)
- Node.js 20.19+ or 22.12+
- npm

## Setup and run

From the project root in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
py -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the generated value in `.env` as `AUTH_SECRET_KEY`. For a development admin, set `DEMO_ADMIN_EMAIL` and `DEMO_ADMIN_PASSWORD` in `.env` (the password must be at least 12 characters), then run:

```powershell
py -3.12 -m backend.app.services.seed_admin
```

The seed command creates an account only when `APP_ENV=development` and both values are explicitly configured; it never creates or resets a password. Do not use demo credentials in production. Set `APP_ENV=production` and a private `AUTH_SECRET_KEY` of at least 32 characters in the production environment; production cookies are always Secure and require HTTPS. The development cookie is HttpOnly, SameSite=Lax, and lasts 12 hours. If the secret is unset in development, a temporary random key is used and sessions will not survive an API restart.

Before running data preparation, place an authorized source CSV at `data/raw/dataset.csv`. Continue setup from the project root:

```powershell
py -3.12 ml\preprocess.py
py -3.12 -m ml.train
py -3.12 -m ml.eda
py -3.12 -m uvicorn backend.app.main:app --reload
```

In a second terminal:

```powershell
Set-Location frontend
npm install
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173` to sign in. FastAPI docs are at `http://127.0.0.1:8000/docs`. The API seeds the local SQLite database from the latest dated source row per SKU on first startup and retains all source sales observations separately. Ties use the last source row for the product state; source rows are not removed from cleaned data or observations. Authentication endpoints are `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, and `GET /api/v1/auth/me`; all other application API routes require a valid session.

Environment variables are documented in `.env.example`. `DATABASE_URL` can point at a different SQLAlchemy-supported database; SQLite is the local default. CORS origins, safety-stock rate, and the replenishment horizon can be configured there.

## Checks and reproducible analysis

```powershell
py -3.12 -m pytest backend\tests -q
py -3.12 ml\preprocess.py
py -3.12 -m ml.train
py -3.12 -m ml.eda
Set-Location frontend
npm run build
npm run lint
```

Outputs include `data/processed/dataset.csv`, root-level `dataset.csv`, `data_dictionary.csv`, `reports/Data_Quality.md`, four figures in `reports/figures/`, `reports/EDA_Insights.md`, and `reports/Model_Evaluation.md`. The daily-sales regressor is an exploratory model trained on the augmented dataset; its evaluation is not validated future-demand forecasting.

## Inventory policy

Expected lead-time demand uses the trained daily-sales estimate × lead days. Safety stock is `ceil(lead_time_demand × safety_stock_rate)`. Reorder point is `ceil(lead_time_demand + safety_stock)`. Target stock is `ceil(daily_sales_estimate × replenishment_horizon_days + safety_stock)`. Suggested order quantity is `max(0, target_stock − on_hand_stock)`. The regressor supplies the daily-sales rate; the safety buffer, reorder point, target stock, and suggested quantity remain deterministic rules. The default rate is 20% and the default horizon is 14 days. These are configurable. Inventory position only includes on-hand stock; outstanding orders and reservations are not netted. The model's negative holdout R² means these are exploratory estimates, not validated recommendations.

## Privacy and data handling

The official CSV is preserved. Unit costs are stored locally for internal product records but excluded from the inventory export and public-facing report summaries. Supplier IDs and anonymized contact fields do not establish real supplier identities. Do not share source pricing externally.

## Known limitations

- Daily-sales regression metrics are exploratory; synthetic augmented observations do not establish real-world prediction accuracy or validated future-demand forecasting.
- Product labels are IDs; the dataset does not contain product names, so the interface does not invent them.
- Supplier contact details are absent from the source and remain blank until verified details are entered.
- Sales charts describe recorded `daily_sales` fields by source date, not transaction-level sales totals or an uninterrupted sales trend.
- Imports are restricted to the documented source schema and 5 MB / 10,000 row bounds. Re-importing the same file can append duplicate source observations; review the preview carefully.
- API access requires a signed HttpOnly session cookie. The development admin must be explicitly configured and seeded; production requires deployment-specific secrets, HTTPS, and operational security review. This remains a local demonstration application, not a production deployment.
- The Markdown report is structured for print/PDF conversion; no signed declaration or demo video is fabricated.

See [reports/Project_Report.md](reports/Project_Report.md), [reports/Architecture.md](reports/Architecture.md), [reports/EDA_Insights.md](reports/EDA_Insights.md), and [reports/Demo_Script.md](reports/Demo_Script.md).