"""Validate the official retail CSV and produce reproducible local outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / "data" / "raw" / "dataset.csv"
PROCESSED_PATH = PROJECT_ROOT / "data" / "processed" / "dataset.csv"
ROOT_CLEAN_PATH = PROJECT_ROOT / "dataset.csv"
DICTIONARY_PATH = PROJECT_ROOT / "data_dictionary.csv"
QUALITY_PATH = PROJECT_ROOT / "reports" / "Data_Quality.md"

REQUIRED_COLUMNS = {
    "date": "Date of the inventory observation; not a complete sales ledger.",
    "product_id": "Source product identifier.",
    "category": "Retail category recorded for the product observation.",
    "season": "Season label recorded for the observation.",
    "stock_qty": "On-hand stock quantity at observation time.",
    "reorder_level": "Source-provided stock threshold.",
    "daily_sales": "Daily sales estimate/value recorded for the observation.",
    "unit_cost": "Source unit cost; excluded from external-facing reports and exports.",
    "supplier_id": "Source supplier identifier; no supplier contact details are supplied.",
    "lead_days": "Supplier lead time in days.",
}
NUMERIC_COLUMNS = ["stock_qty", "reorder_level", "daily_sales", "unit_cost", "lead_days"]
INTEGER_COLUMNS = ["stock_qty", "reorder_level", "daily_sales", "lead_days"]


def load_and_validate(path: Path = RAW_PATH) -> tuple[pd.DataFrame, dict[str, object]]:
    """Load source data, reject unusable rows, and return a quality summary."""
    if not path.is_file():
        raise FileNotFoundError(f"Official dataset not found: {path}")

    frame = pd.read_csv(path)
    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing_columns)}")

    source_rows = len(frame)
    frame = frame[list(REQUIRED_COLUMNS)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    for column in ["product_id", "category", "season", "supplier_id"]:
        frame[column] = frame[column].astype("string").str.strip()

    invalid_numeric = frame[NUMERIC_COLUMNS].isna().any(axis=1)
    negative_values = (frame[NUMERIC_COLUMNS] < 0).any(axis=1)
    non_integer = pd.Series(False, index=frame.index)
    for column in INTEGER_COLUMNS:
        non_integer |= frame[column].notna() & (frame[column] % 1 != 0)
    empty_identifiers = frame[["product_id", "category", "season", "supplier_id"]].isna().any(axis=1)
    empty_identifiers |= frame[["product_id", "category", "season", "supplier_id"]].eq("").any(axis=1)
    invalid_rows = frame["date"].isna() | invalid_numeric | negative_values | non_integer | empty_identifiers
    invalid_row_count = int(invalid_rows.sum())
    cleaned = frame.loc[~invalid_rows].copy()

    cleaned["date"] = cleaned["date"].dt.strftime("%Y-%m-%d")
    for column in INTEGER_COLUMNS:
        cleaned[column] = cleaned[column].astype("int64")

    exact_duplicates = int(cleaned.duplicated().sum())
    duplicate_product_dates = int(cleaned.duplicated(["date", "product_id"], keep=False).sum())
    quality: dict[str, object] = {
        "source_rows": source_rows,
        "cleaned_rows": len(cleaned),
        "invalid_rows_removed": invalid_row_count,
        "missing_values_by_column": frame.isna().sum().astype(int).to_dict(),
        "exact_duplicate_rows": exact_duplicates,
        "rows_with_duplicate_product_date": duplicate_product_dates,
        "unique_products": int(cleaned["product_id"].nunique()),
        "unique_suppliers": int(cleaned["supplier_id"].nunique()),
        "date_min": str(cleaned["date"].min()) if not cleaned.empty else "Unavailable",
        "date_max": str(cleaned["date"].max()) if not cleaned.empty else "Unavailable",
        "numeric_ranges": {
            column: [float(cleaned[column].min()), float(cleaned[column].max())]
            for column in NUMERIC_COLUMNS
            if not cleaned.empty
        },
    }
    return cleaned, quality


def write_data_dictionary() -> None:
    """Write documented source meanings and validation/preprocessing rules."""
    rows = []
    for column, meaning in REQUIRED_COLUMNS.items():
        rows.append(
            {
                "column": column,
                "data_type": "date" if column == "date" else ("integer" if column in INTEGER_COLUMNS else ("number" if column == "unit_cost" else "string")),
                "business_meaning": meaning,
                "validation_rules": (
                    "Parseable date"
                    if column == "date"
                    else "Non-empty identifier/category"
                    if column in {"product_id", "category", "season", "supplier_id"}
                    else "Numeric, non-negative; integral values required"
                    if column in INTEGER_COLUMNS
                    else "Numeric and non-negative"
                ),
                "preprocessing": (
                    "Normalized to YYYY-MM-DD"
                    if column == "date"
                    else "Trimmed whitespace"
                    if column in {"product_id", "category", "season", "supplier_id"}
                    else "Coerced to numeric; invalid rows excluded and counted"
                ),
            }
        )
    pd.DataFrame(rows).to_csv(DICTIONARY_PATH, index=False)


def write_quality_report(quality: dict[str, object]) -> None:
    missing = quality["missing_values_by_column"]
    ranges = quality["numeric_ranges"]
    report = [
        "# Data Quality Report",
        "",
        f"- Source rows: {quality['source_rows']}",
        f"- Cleaned rows: {quality['cleaned_rows']}",
        f"- Invalid rows excluded by documented validation: {quality['invalid_rows_removed']}",
        f"- Exact duplicate rows: {quality['exact_duplicate_rows']}",
        f"- Rows participating in duplicate (date, product_id) keys: {quality['rows_with_duplicate_product_date']}",
        f"- Unique products / suppliers: {quality['unique_products']} / {quality['unique_suppliers']}",
        f"- Observation dates: {quality['date_min']} through {quality['date_max']}",
        "",
        "## Missing Values Before Row Validation",
        "",
        *[f"- `{column}`: {count}" for column, count in missing.items()],
        "",
        "## Numeric Ranges After Cleaning",
        "",
        *[f"- `{column}`: withheld (pricing-sensitive; validated as numeric and non-negative)" if column == "unit_cost" else f"- `{column}`: {bounds[0]:g} to {bounds[1]:g}" for column, bounds in ranges.items()],
        "",
        "## Rules and Limitations",
        "",
        "Required columns are checked against the supplied schema. Unparseable dates, missing or empty identifiers, non-numeric values, negative quantities/cost/lead times, and fractional values in integer fields are excluded and counted. Exact duplicate rows are reported; no otherwise-valid rows are deduplicated. Duplicate product/date keys remain in the cleaned output because the source provides no rule for resolving conflicting observations.",
        "The file is sparse: a product can have multiple dated snapshots, but the observations are not a complete daily series. `daily_sales` is therefore treated as an observed source field, not evidence of continuous historical demand.",
    ]
    QUALITY_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def run() -> pd.DataFrame:
    cleaned, quality = load_and_validate()
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(PROCESSED_PATH, index=False)
    cleaned.to_csv(ROOT_CLEAN_PATH, index=False)
    write_data_dictionary()
    write_quality_report(quality)
    print(f"Cleaned {quality['cleaned_rows']} of {quality['source_rows']} rows.")
    print(f"Wrote {PROCESSED_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {ROOT_CLEAN_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {DICTIONARY_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {QUALITY_PATH.relative_to(PROJECT_ROOT)}")
    return cleaned


if __name__ == "__main__":
    run()