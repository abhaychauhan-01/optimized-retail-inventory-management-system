"""Generate EDA figures and concise findings from the cleaned dataset."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from backend.app.models import Product
from backend.app.services.daily_sales_model import predict_products_daily_sales
from ml.preprocess import PROJECT_ROOT, RAW_PATH, load_and_validate


FIGURES = PROJECT_ROOT / "reports" / "figures"
INSIGHTS = PROJECT_ROOT / "reports" / "EDA_Insights.md"


def _latest_snapshot(frame: pd.DataFrame) -> pd.DataFrame:
    latest_date = frame.groupby("product_id")["date"].transform("max")
    latest = frame.loc[frame["date"].eq(latest_date)].copy()
    return latest.sort_values("date").drop_duplicates("product_id", keep="last")


def run() -> None:
    frame, quality = load_and_validate(RAW_PATH)
    FIGURES.mkdir(parents=True, exist_ok=True)
    if frame.empty:
        INSIGHTS.write_text("# EDA Insights\n\nThe cleaned dataset is empty; visual analysis is unavailable.\n", encoding="utf-8")
        return

    latest = _latest_snapshot(frame)
    plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white", "font.size": 9})

    category_counts = frame.groupby("category")["product_id"].nunique().sort_values()
    fig, axis = plt.subplots(figsize=(8, 4.5))
    category_counts.plot.barh(ax=axis, color="#287c73")
    axis.set(title="Distinct observed products by category", xlabel="Products", ylabel="")
    axis.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIGURES / "products_by_category.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(7, 5))
    axis.scatter(latest["reorder_level"], latest["stock_qty"], alpha=0.68, color="#287c73", edgecolors="white", linewidths=0.4)
    limit = max(int(latest["stock_qty"].max()), int(latest["reorder_level"].max()), 1)
    axis.plot([0, limit], [0, limit], linestyle="--", color="#c65d4b", linewidth=1)
    axis.set(title="Latest observed stock versus reorder level", xlabel="Reorder level (units)", ylabel="Stock quantity (units)")
    axis.grid(alpha=0.18)
    fig.tight_layout()
    fig.savefig(FIGURES / "stock_vs_reorder.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(8, 4.5))
    axis.hist(frame["daily_sales"], bins=18, color="#d39b43", edgecolor="white")
    axis.set(title="Distribution of recorded daily-sales values", xlabel="Recorded daily sales (units)", ylabel="Observation rows")
    axis.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIGURES / "daily_sales_distribution.png", dpi=160)
    plt.close(fig)

    model_products = [Product(
        product_id=str(row.product_id),
        category=str(row.category),
        stock_qty=int(row.stock_qty),
        reorder_level=int(row.reorder_level),
        daily_sales=float(row.daily_sales),
        lead_days=int(row.lead_days),
        unit_cost=float(row.unit_cost),
    ) for row in latest.itertuples(index=False)]
    model_estimates = predict_products_daily_sales(model_products)
    latest["daily_sales_estimate"] = [item["daily_sales_estimate"] for item in model_estimates]
    latest["risk_units"] = (latest["daily_sales_estimate"] * latest["lead_days"] + latest["reorder_level"] - latest["stock_qty"]).clip(lower=0)
    risk = latest.nlargest(15, "risk_units").sort_values("risk_units")
    fig, axis = plt.subplots(figsize=(9, 6))
    axis.barh(risk["product_id"], risk["risk_units"], color="#c65d4b")
    axis.set(title="Products ranked by model-estimated replenishment gap", xlabel="Model-estimated units needed to cover lead-time demand and reorder level", ylabel="Product ID")
    axis.grid(axis="x", alpha=0.2)
    fig.tight_layout()
    fig.savefig(FIGURES / "inventory_risk.png", dpi=160)
    plt.close(fig)

    daily = frame.groupby("date")["daily_sales"].agg(["mean", "count"])
    risk_count = int((latest["stock_qty"] <= latest["reorder_level"]).sum())
    category_text = ", ".join(f"{name}: {count}" for name, count in category_counts.sort_values(ascending=False).items())
    report = [
        "# Exploratory Data Analysis",
        "",
        "## Dataset profile",
        "",
        f"The supplied file has {quality['source_rows']} rows and {len(frame.columns)} columns. It spans {quality['date_min']} to {quality['date_max']} across {frame['date'].nunique()} dates, with {frame['product_id'].nunique()} distinct product identifiers and {frame['supplier_id'].nunique()} supplier identifiers. There are {quality['rows_with_duplicate_product_date']} rows participating in repeated product/date keys.",
        "",
        f"No invalid rows were excluded ({quality['invalid_rows_removed']}); missing values before validation: {sum(quality['missing_values_by_column'].values())}; exact duplicate rows: {quality['exact_duplicate_rows']}.",
        "",
        "## Findings",
        "",
        f"- Distinct observed products by category: {category_text}.",
        f"- {risk_count} of {len(latest)} products in the selected latest observation are at or below their source reorder level.",
        f"- The replenishment-gap ranking uses {model_estimates[0]['model_name']} daily-sales predictions for the current date; it is exploratory, not validated future-demand accuracy.",
        f"- Recorded daily-sales values have mean {frame['daily_sales'].mean():.2f}, median {frame['daily_sales'].median():.2f}, and range {frame['daily_sales'].min():.0f}–{frame['daily_sales'].max():.0f} units per row.",
        f"- Per-date recorded-sales means range from {daily['mean'].min():.2f} to {daily['mean'].max():.2f}; row counts vary from {daily['count'].min()} to {daily['count'].max()}.",
        "- The latest snapshot is selected by date; tied product/date records are reduced only for per-product plots by keeping the last source row. The original processed observations remain intact.",
        "",
        "## Data limitations",
        "",
        "These are sparse inventory observations, not a complete daily sales history. Most products appear only once or twice, product/date keys repeat, and there are no product names or supplier contact/pricing terms. Daily-sales model predictions use an augmented dataset containing synthetic observations, have not been established as real-world accuracy, and must not be interpreted as validated future-demand forecasts. The other charts describe recorded rows or the selected latest snapshot.",
        "",
        "## Figures",
        "",
        "1. `figures/products_by_category.png` — distinct observed products per category.",
        "2. `figures/stock_vs_reorder.png` — latest selected stock versus source reorder level.",
        "3. `figures/daily_sales_distribution.png` — distribution of observed daily-sales values.",
        "4. `figures/inventory_risk.png` — model-estimated replenishment-gap ranking from latest selected product rows.",
    ]
    INSIGHTS.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Generated 4 figures in {FIGURES.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {INSIGHTS.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    run()