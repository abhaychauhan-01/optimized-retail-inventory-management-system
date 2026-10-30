"""Audit whether the original snapshots support per-product forecasting."""

from __future__ import annotations

import json

import pandas as pd

from ml.preprocess import INTEGER_COLUMNS, PROJECT_ROOT, RAW_PATH, REQUIRED_COLUMNS, load_and_validate


REPORT_PATH = PROJECT_ROOT / "reports" / "Official_Source_Suitability.md"
RESULT_PATH = PROJECT_ROOT / "reports" / "official_source_suitability.json"


def assess_suitability(frame: pd.DataFrame) -> dict[str, object]:
    product_counts = frame.groupby("product_id")["date"].nunique() if not frame.empty else pd.Series(dtype=int)
    eligible_products = int((product_counts >= 10).sum())
    duplicate_keys = int(frame.duplicated(["date", "product_id"]).sum())
    suitable = eligible_products >= 10 and duplicate_keys == 0
    return {
        "suitable": suitable,
        "total_observations": len(frame),
        "products": int(frame["product_id"].nunique()) if not frame.empty else 0,
        "products_with_at_least_10_dates": eligible_products,
        "duplicate_product_date_excess_rows": duplicate_keys,
        "duplicate_product_date_participating_rows": int(frame.duplicated(["date", "product_id"], keep=False).sum()),
        "validation_method": "Would require per-product chronological holdout with at least 10 dated observations per eligible product and no ambiguous product/date keys.",
    }


def _column_profiles(frame: pd.DataFrame) -> list[dict[str, object]]:
    profiles = []
    for column, meaning in REQUIRED_COLUMNS.items():
        series = frame[column]
        distinct = int(series.nunique(dropna=False))
        if column == "date":
            dates = pd.to_datetime(series)
            rows_per_date = series.value_counts()
            distribution = (
                f"{distinct} dates ({dates.min():%Y-%m-%d} to {dates.max():%Y-%m-%d}); "
                f"{int(rows_per_date.min())} to {int(rows_per_date.max())} rows per date"
            )
            data_type = "date"
        elif column == "product_id":
            per_product_dates = frame.groupby("product_id")["date"].nunique().value_counts().sort_index()
            buckets = ", ".join(f"{int(count)} date(s): {int(products)} products" for count, products in per_product_dates.items())
            distribution = f"{distinct} IDs; distinct dates/product: {buckets}"
            data_type = "string"
        elif column in {"category", "season"}:
            counts = series.value_counts().sort_index()
            distribution = ", ".join(f"{value}: {int(count)}" for value, count in counts.items())
            data_type = "string"
        elif column == "supplier_id":
            supplier_rows = frame.groupby("supplier_id").size()
            row_count_distribution = supplier_rows.value_counts().sort_index()
            counts = ", ".join(f"{int(rows)} rows: {int(ids)} IDs" for rows, ids in row_count_distribution.items())
            distribution = f"{distinct} IDs; {counts}"
            data_type = "string"
        elif column == "unit_cost":
            distribution = f"{distinct} distinct numeric values; values withheld because pricing is sensitive"
            data_type = "number"
        elif column in INTEGER_COLUMNS:
            quartiles = series.quantile([0.25, 0.5, 0.75])
            distribution = (
                f"min {series.min():g}; Q1 {quartiles.loc[0.25]:g}; median {quartiles.loc[0.5]:g}; "
                f"Q3 {quartiles.loc[0.75]:g}; max {series.max():g}"
            )
            data_type = "integer"
        else:
            data_type = str(series.dtype)
            distribution = f"{distinct} distinct values"
        profiles.append({
            "name": column,
            "meaning": meaning,
            "data_type": data_type,
            "missing": int(series.isna().sum()),
            "distinct": distinct,
            "distribution": distribution,
        })
    return profiles


def _duplicate_groups(frame: pd.DataFrame) -> list[dict[str, object]]:
    groups = []
    for (date, product_id), group in frame.groupby(["date", "product_id"], sort=True):
        if len(group) < 2:
            continue
        conflicting_columns = [
            column for column in frame.columns
            if column not in {"date", "product_id"} and group[column].nunique(dropna=False) > 1
        ]
        groups.append({
            "date": str(date),
            "product_id": str(product_id),
            "rows": len(group),
            "exact_duplicate_rows": int(group.duplicated().sum()),
            "conflicting_columns": conflicting_columns,
        })
    return groups


def build_dataset_audit(frame: pd.DataFrame) -> dict[str, object]:
    suitability = assess_suitability(frame)
    duplicate_groups = _duplicate_groups(frame)
    duplicated_keys = frame.duplicated(["date", "product_id"], keep=False)
    unambiguous = frame.loc[~duplicated_keys].copy()
    unambiguous["date"] = pd.to_datetime(unambiguous["date"])
    unambiguous = unambiguous.sort_values(["product_id", "date"])
    unambiguous["next_date"] = unambiguous.groupby("product_id")["date"].shift(-1)
    unambiguous["next_stock"] = unambiguous.groupby("product_id")["stock_qty"].shift(-1)
    unambiguous["next_reorder"] = unambiguous.groupby("product_id")["reorder_level"].shift(-1)
    transitions = unambiguous.loc[unambiguous["next_date"].notna()].copy()
    gaps = (transitions["next_date"] - transitions["date"]).dt.days
    below_reorder_count = int((transitions["next_stock"] <= transitions["next_reorder"]).sum())
    stockout_count = int((transitions["next_stock"] == 0).sum())
    category_instability = int((frame.groupby("product_id")["category"].nunique() > 1).sum())
    supplier_instability = int((frame.groupby("product_id")["supplier_id"].nunique() > 1).sum())
    current_below_reorder = int((frame["stock_qty"] <= frame["reorder_level"]).sum())
    current_stockouts = int((frame["stock_qty"] == 0).sum())
    variable_lead_suppliers = int((frame.groupby("supplier_id")["lead_days"].nunique() > 1).sum())
    average_dates_per_product = (
        float(frame.groupby("product_id")["date"].nunique().mean())
        if not frame.empty else 0.0
    )

    return {
        **suitability,
        "date_count": int(frame["date"].nunique()),
        "average_distinct_dates_per_product": average_dates_per_product,
        "date_min": str(frame["date"].min()) if not frame.empty else None,
        "date_max": str(frame["date"].max()) if not frame.empty else None,
        "product_date_counts": {
            str(int(count)): int(products)
            for count, products in frame.groupby("product_id")["date"].nunique().value_counts().sort_index().items()
        },
        "rows_with_missing_values": int(frame.isna().any(axis=1).sum()),
        "exact_duplicate_rows": int(frame.duplicated().sum()),
        "duplicate_groups": duplicate_groups,
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_participating_rows": int(duplicated_keys.sum()),
        "current_below_reorder_rows": current_below_reorder,
        "current_stockout_rows": current_stockouts,
        "successive_unambiguous_pairs": len(transitions),
        "successive_pair_gap_min_days": int(gaps.min()) if not gaps.empty else None,
        "successive_pair_gap_median_days": float(gaps.median()) if not gaps.empty else None,
        "successive_pair_gap_max_days": int(gaps.max()) if not gaps.empty else None,
        "next_observation_below_reorder_rows": below_reorder_count,
        "next_observation_stockout_rows": stockout_count,
        "product_ids_with_multiple_categories": category_instability,
        "product_ids_with_multiple_suppliers": supplier_instability,
        "suppliers_with_variable_lead_days": variable_lead_suppliers,
        "columns": _column_profiles(frame),
        "candidate_tasks": [
            {
                "name": "Per-product demand forecasting",
                "status": "not supported",
                "evidence": f"{suitability['products_with_at_least_10_dates']} products have at least 10 distinct dates; maximum is {int(frame.groupby('product_id')['date'].nunique().max()) if not frame.empty else 0}.",
            },
            {
                "name": "Current below-reorder classification",
                "status": "not independent",
                "evidence": f"{current_below_reorder} rows meet stock_qty <= reorder_level; this label is directly defined by input fields and is not an independent future outcome.",
            },
            {
                "name": "Future stockout prediction",
                "status": "not supported",
                "evidence": f"Among {len(transitions)} successive unambiguous record pairs, there are {stockout_count} next-observation stockouts; the data does not label stockout duration or a fixed prediction horizon.",
            },
            {
                "name": "Next-observation below-reorder classification",
                "status": "exploratory only",
                "evidence": f"{below_reorder_count} positive outcomes among {len(transitions)} pairs, but gaps vary from {int(gaps.min()) if not gaps.empty else 0} to {int(gaps.max()) if not gaps.empty else 0} days, and product IDs change category for {category_instability} products and supplier for {supplier_instability} products.",
            },
            {
                "name": "Product category classification",
                "status": "not supported",
                "evidence": f"Category is already supplied as a feature, and {category_instability} product IDs have multiple recorded categories, so it is not a stable held-out product label.",
            },
            {
                "name": "Supplier lead-time estimation",
                "status": "not supported",
                "evidence": f"All {variable_lead_suppliers} suppliers with multiple observations have varying lead_days values; the source has no shipment-specific promised-versus-actual outcome.",
            },
            {
                "name": "Season classification",
                "status": "not supported",
                "evidence": f"Only {frame['season'].nunique() if not frame.empty else 0} season value is present, so there is no class variation to learn or evaluate.",
            },
        ],
        "required_data": [
            "Stable product/SKU identifiers and documented resolution for repeated product/date keys.",
            "Complete dated sales quantities per SKU, with stockout and unavailable-period censoring identified.",
            "A defined prediction target and fixed horizon, such as stockout within a specified number of days.",
            "Inventory events such as receipts, adjustments, reservations, and purchase orders if predicting future stock risk.",
            "Enough longitudinal coverage and positive target events for a chronological holdout with meaningful uncertainty estimates.",
        ],
        "validation_method": (
            "No train/test split was run because no candidate target passed the validity gate. "
            "For future evaluation, use a chronological holdout, derive features only from data available "
            "at prediction time, fit transformations on training rows only, and compare a candidate with "
            "a simple baseline on identical holdout rows."
        ),
    }


def run() -> dict[str, object]:
    frame, _ = load_and_validate(RAW_PATH)
    assessment = build_dataset_audit(frame)
    result = {
        "source_dataset": "data/raw/dataset.csv",
        "assessment_scope": "Suitability of the original sparse snapshots for per-product forecasting; this does not evaluate the augmented daily-sales regression model.",
        **assessment,
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    note = "The original 500-row snapshot file does not support a defensible per-product future-demand or stockout forecast: history is sparse and irregular, product/date keys conflict, and there is no independent fixed-horizon outcome. This source-suitability audit is separate from the exploratory daily-sales regression trained on the augmented dataset."
    report = [
        "# Official Source Suitability Audit",
        "",
        "## Result",
        "",
        "- Scope: original source suitability for per-product forecasting; not the augmented-data daily-sales regression evaluation",
        "- Independent per-product forecasting metrics: **Not measured**",
        f"- Source data: {assessment['total_observations']} rows, {assessment['products']} product IDs, {assessment['date_count']} dates ({assessment['date_min']} to {assessment['date_max']})",
        f"- Per-product history: mean {assessment['average_distinct_dates_per_product']:.2f} distinct dates; maximum {max(map(int, assessment['product_date_counts']))}; {assessment['products_with_at_least_10_dates']} products meet the basic 10-date gate.",
        f"- Duplicate keys: {assessment['duplicate_product_date_excess_rows']} excess rows across {assessment['duplicate_group_count']} groups ({assessment['duplicate_participating_rows']} participating rows); all groups have conflicting fields and none are exact duplicates.",
        f"- Validation method: {assessment['validation_method']}",
        "",
        "## Dataset Profile",
        "",
        "| Column | Type | Meaning | Observed distribution |",
        "| --- | --- | --- | --- |",
        *[
            f"| `{column['name']}` | {column['data_type']} ({column['distinct']} distinct; {column['missing']} missing) | {column['meaning']} | {column['distribution']} |"
            for column in assessment["columns"]
        ],
        "",
        "`unit_cost` values are withheld from this report because source pricing is sensitive.",
        "",
        "## Duplicate Product/Date Groups",
        "",
        "No duplicate keys were dropped or aggregated. All groups below are conflicting observations, not exact duplicate rows; the source does not identify whether these are repeated snapshots, product-ID reuse, or data errors.",
        "",
        "| Date | Product ID | Rows | Conflicting columns |",
        "| --- | --- | ---: | --- |",
        *[
            f"| {group['date']} | `{group['product_id']}` | {group['rows']} | {', '.join(group['conflicting_columns'])} |"
            for group in assessment["duplicate_groups"]
        ],
        "",
        "## Alternative ML Tasks",
        "",
        *[
            f"- **{task['name']}** ({task['status']}): {task['evidence']}"
            for task in assessment["candidate_tasks"]
        ],
        "",
        "A current below-reorder label is derived directly from `stock_qty` and `reorder_level`; training against it would reproduce a rule, not demonstrate independent prediction. The next-observation label has no consistent horizon and is not treated as a fixed-horizon stock-risk outcome.",
        "",
        "## Decision and Validation",
        "",
        note,
        "",
        "No per-product future-demand or stockout train/test split is reported because no such target passed the validity gate for the original source file. The separate daily-sales regression metrics are reported in `backend/artifacts/model_metrics.json` and `reports/model_metrics.json`.",
        "",
        "## Additional Data Required",
        "",
        *[f"- {item}" for item in assessment["required_data"]],
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(note)
    return result


if __name__ == "__main__":
    run()