"""Train an exploratory daily-sales regression model on the augmented dataset."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "data" / "raw" / "dataset_augmented.csv"
ORIGINAL_PATH = PROJECT_ROOT / "data" / "raw" / "dataset.csv"
ARTIFACT_DIR = PROJECT_ROOT / "backend" / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "daily_sales_model.joblib"
METRICS_PATH = ARTIFACT_DIR / "model_metrics.json"
REPORT_METRICS_PATH = PROJECT_ROOT / "reports" / "model_metrics.json"
REPORT_PATH = PROJECT_ROOT / "reports" / "Model_Evaluation.md"

COLUMNS = [
    "date", "product_id", "category", "season", "stock_qty", "reorder_level",
    "daily_sales", "unit_cost", "supplier_id", "lead_days",
]
INTEGER_COLUMNS = ["stock_qty", "reorder_level", "daily_sales", "lead_days"]
CATEGORICAL_FEATURES = ["category", "season"]
NUMERIC_FEATURES = [
    "stock_qty", "reorder_level", "unit_cost", "lead_days",
    "date_month", "date_day_of_week", "date_day_of_year",
]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
MODEL_NAME = "RandomForestRegressor"
RANDOM_STATE = 42


def _record_key(row: pd.Series) -> tuple[object, ...]:
    return (
        pd.Timestamp(row["date"]).date().isoformat(),
        str(row["product_id"]).strip(),
        str(row["category"]).strip(),
        str(row["season"]).strip(),
        int(row["stock_qty"]),
        int(row["reorder_level"]),
        int(row["daily_sales"]),
        round(float(row["unit_cost"]), 2),
        str(row["supplier_id"]).strip(),
        int(row["lead_days"]),
    )


def _identify_original_rows(frame: pd.DataFrame) -> pd.Series:
    original = pd.read_csv(ORIGINAL_PATH)
    if list(original.columns) != COLUMNS:
        raise ValueError("The original dataset schema does not match the augmented dataset schema.")
    remaining = Counter(_record_key(row) for _, row in original.iterrows())
    original_rows = []
    for _, row in frame.iterrows():
        key = _record_key(row)
        matched = remaining[key] > 0
        original_rows.append(matched)
        if matched:
            remaining[key] -= 1
    unmatched = sum(remaining.values())
    if unmatched:
        raise ValueError(f"The augmented dataset is missing {unmatched} record(s) from the original dataset.")
    return pd.Series(original_rows, index=frame.index, dtype=bool)


def _load_dataset() -> tuple[pd.DataFrame, pd.Series]:
    if not DATASET_PATH.is_file():
        raise FileNotFoundError(f"Training dataset not found: {DATASET_PATH}")
    if not ORIGINAL_PATH.is_file():
        raise FileNotFoundError(f"Original dataset not found: {ORIGINAL_PATH}")

    frame = pd.read_csv(DATASET_PATH)
    if list(frame.columns) != COLUMNS:
        raise ValueError(f"Expected columns in this exact order: {', '.join(COLUMNS)}")
    if frame.empty:
        raise ValueError("The augmented dataset contains no records.")

    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ["stock_qty", "reorder_level", "daily_sales", "unit_cost", "lead_days"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ["product_id", "category", "season", "supplier_id"]:
        frame[column] = frame[column].astype("string").str.strip()

    invalid = frame["date"].isna()
    invalid |= frame[["stock_qty", "reorder_level", "daily_sales", "unit_cost", "lead_days"]].isna().any(axis=1)
    invalid |= ~np.isfinite(frame[["stock_qty", "reorder_level", "daily_sales", "unit_cost", "lead_days"]]).all(axis=1)
    invalid |= (frame[["stock_qty", "reorder_level", "daily_sales", "unit_cost", "lead_days"]] < 0).any(axis=1)
    invalid |= frame[["product_id", "category", "season", "supplier_id"]].isna().any(axis=1)
    invalid |= frame[["product_id", "category", "season", "supplier_id"]].eq("").any(axis=1)
    for column in INTEGER_COLUMNS:
        invalid |= frame[column].notna() & (frame[column] % 1 != 0)
    if invalid.any():
        examples = [int(index) + 2 for index in frame.index[invalid][:10]]
        raise ValueError(
            f"Found {int(invalid.sum())} invalid row(s); none were removed. "
            f"Check CSV line(s): {examples}."
        )

    frame[INTEGER_COLUMNS] = frame[INTEGER_COLUMNS].astype("int64")
    original_rows = _identify_original_rows(frame)
    return frame, original_rows


def _add_date_features(frame: pd.DataFrame) -> pd.DataFrame:
    features = frame[FEATURES[:2] + ["stock_qty", "reorder_level", "unit_cost", "lead_days"]].copy()
    features["date_month"] = frame["date"].dt.month
    features["date_day_of_week"] = frame["date"].dt.day_of_week
    features["date_day_of_year"] = frame["date"].dt.day_of_year
    return features[FEATURES]


def _write_report(metrics: dict[str, object]) -> None:
    report = [
        "# Daily Sales Regression Evaluation",
        "",
        "## Results",
        "",
        f"- Model: **{metrics['model_name']}**",
        f"- Dataset: `{metrics['dataset_source']}` ({metrics['dataset_type'].lower()}; {metrics['original_observations']} source rows and {metrics['synthetic_observations']} synthetic rows)",
        f"- Training / evaluation observations: {metrics['training_observations']} / {metrics['evaluation_observations']}",
        f"- Chronological training dates: {metrics['training_date_range']['start']} to {metrics['training_date_range']['end']}",
        f"- Chronological testing dates: {metrics['testing_date_range']['start']} to {metrics['testing_date_range']['end']}",
        f"- MAE / RMSE / R²: {metrics['mae']:.4f} / {metrics['rmse']:.4f} / {metrics['r2']:.4f}",
        f"- Features: {', '.join(metrics['features'])}",
        f"- Repeated product/calendar-date excess rows retained: {metrics['duplicate_product_date_excess_rows']} ({metrics['duplicate_product_date_participating_rows']} participating rows)",
        "",
        "## Limitations",
        "",
        "This is an exploratory supervised regression fit against the supplied `daily_sales` column, not validated future-demand forecasting. The augmented dataset contains generated observations; the reported holdout metrics can be optimistic or otherwise unrepresentative of real retail operations. The 500 matched source rows are identified as original-file records, but their provenance does not independently establish that they are genuine transaction history.",
        "",
        "The chronological split assigns every observation on the same calendar date to one side of the holdout. Repeated product/date rows were retained; this can overweight repeated records despite avoiding same-day train/test leakage. The model supplies daily estimates to Demand Estimate and the existing deterministic reorder formulas. This integration does not make the estimates validated future-demand forecasts.",
        "",
        f"Training timestamp: `{metrics['training_timestamp']}`.",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def train() -> dict[str, object]:
    frame, original_rows = _load_dataset()
    date_key = frame["date"].dt.normalize()
    dates = pd.Index(date_key.drop_duplicates().sort_values())
    if len(dates) < 2:
        raise ValueError("At least two distinct calendar dates are required for chronological evaluation.")
    split_index = min(max(int(len(dates) * 0.8), 1), len(dates) - 1)
    cutoff = dates[split_index]
    training_mask = date_key < cutoff
    training_rows = frame.loc[training_mask]
    testing_rows = frame.loc[~training_mask]
    if training_rows.empty or testing_rows.empty:
        raise ValueError("The chronological split produced an empty training or evaluation partition.")

    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("numeric", "passthrough", NUMERIC_FEATURES),
        ],
        remainder="drop",
    )
    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", RandomForestRegressor(
            n_estimators=160,
            min_samples_leaf=2,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )),
    ])
    training_features = _add_date_features(training_rows)
    testing_features = _add_date_features(testing_rows)
    pipeline.fit(training_features, training_rows["daily_sales"])
    predictions = pipeline.predict(testing_features)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    original_count = int(original_rows.sum())
    synthetic_count = len(frame) - original_count
    duplicate_frame = frame.assign(calendar_date=date_key)
    duplicate_keys = duplicate_frame.duplicated(["product_id", "calendar_date"])
    duplicate_participating = duplicate_frame.duplicated(["product_id", "calendar_date"], keep=False)
    source_kind = "Mixed" if original_count and synthetic_count else "Original" if original_count else "Augmented"
    parsed_types = {column: str(frame[column].dtype) for column in COLUMNS}
    metrics: dict[str, object] = {
        "trained_model_available": True,
        "model_name": MODEL_NAME,
        "prediction_target": "daily_sales",
        "training_timestamp": timestamp,
        "dataset_source": "data/raw/dataset_augmented.csv",
        "dataset_type": source_kind,
        "contains_synthetic_data": synthetic_count > 0,
        "source_provenance_note": "Original-file rows are matched by date and all other source fields. Matching source rows does not independently establish genuine transaction history.",
        "total_observations": int(len(frame)),
        "original_observations": original_count,
        "synthetic_observations": synthetic_count,
        "products": int(frame["product_id"].nunique()),
        "date_count": int(date_key.nunique()),
        "date_min": date_key.min().date().isoformat(),
        "date_max": date_key.max().date().isoformat(),
        "columns": COLUMNS,
        "column_types": parsed_types,
        "missing_values_by_column": {column: int(frame[column].isna().sum()) for column in COLUMNS},
        "exact_duplicate_rows": int(frame.duplicated().sum()),
        "duplicate_product_date_excess_rows": int(duplicate_keys.sum()),
        "duplicate_product_date_participating_rows": int(duplicate_participating.sum()),
        "category_options": sorted(frame["category"].astype(str).unique().tolist()),
        "season_options": sorted(frame["season"].astype(str).unique().tolist()),
        "numeric_ranges": {
            column: {"min": float(frame[column].min()), "max": float(frame[column].max())}
            for column in ["stock_qty", "reorder_level", "daily_sales", "unit_cost", "lead_days"]
        },
        "numeric_medians": {
            column: float(frame[column].median())
            for column in ["stock_qty", "reorder_level", "unit_cost", "lead_days"]
        },
        "season_counts": {str(key): int(value) for key, value in frame["season"].value_counts().items()},
        "model_algorithm": MODEL_NAME,
        "mae": float(mean_absolute_error(testing_rows["daily_sales"], predictions)),
        "rmse": float(np.sqrt(mean_squared_error(testing_rows["daily_sales"], predictions))),
        "r2": float(r2_score(testing_rows["daily_sales"], predictions)),
        "training_observations": int(len(training_rows)),
        "evaluation_observations": int(len(testing_rows)),
        "training_date_range": {
            "start": date_key.loc[training_mask].min().date().isoformat(),
            "end": date_key.loc[training_mask].max().date().isoformat(),
        },
        "testing_date_range": {
            "start": date_key.loc[~training_mask].min().date().isoformat(),
            "end": date_key.loc[~training_mask].max().date().isoformat(),
        },
        "features": FEATURES,
        "validation_method": "Chronological holdout by calendar date; all records from one calendar date stay in the same partition. The last 20% of unique dates are held out.",
        "synthetic_data_limitation": "Synthetic augmented observations can make evaluation optimistic or unrepresentative and do not establish real-world predictive accuracy or validated future-demand forecasting.",
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipeline": pipeline, "features": FEATURES, "model_name": MODEL_NAME, "training_timestamp": timestamp}, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    REPORT_METRICS_PATH.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    _write_report(metrics)
    print(json.dumps({key: metrics[key] for key in ["model_name", "training_observations", "evaluation_observations", "mae", "rmse", "r2", "dataset_type"]}, indent=2))
    return metrics


if __name__ == "__main__":
    train()