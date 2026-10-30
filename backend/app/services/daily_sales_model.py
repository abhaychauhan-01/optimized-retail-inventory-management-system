from __future__ import annotations

from datetime import date
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from ..models import Product


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = PROJECT_ROOT / "backend" / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "daily_sales_model.joblib"
METRICS_PATH = ARTIFACT_DIR / "model_metrics.json"


class ModelUnavailableError(RuntimeError):
    pass


def read_metrics() -> dict[str, Any]:
    if not METRICS_PATH.is_file():
        raise ModelUnavailableError("Model metrics are unavailable; train the daily-sales model first.")
    try:
        with METRICS_PATH.open(encoding="utf-8") as metrics_file:
            metrics = json.load(metrics_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelUnavailableError("The model metrics file could not be read.") from exc
    if not isinstance(metrics, dict) or not metrics.get("trained_model_available"):
        raise ModelUnavailableError("No trained daily-sales model is recorded in the metrics file.")
    return metrics


@lru_cache(maxsize=1)
def _load_bundle(modified_time_ns: int) -> dict[str, Any]:
    del modified_time_ns
    if not MODEL_PATH.is_file():
        raise ModelUnavailableError("The daily-sales model artifact is missing; train the model first.")
    try:
        bundle = joblib.load(MODEL_PATH)
    except Exception as exc:
        raise ModelUnavailableError("The daily-sales model artifact could not be loaded.") from exc
    if not isinstance(bundle, dict) or "pipeline" not in bundle:
        raise ModelUnavailableError("The daily-sales model artifact has an invalid format.")
    return bundle


def _current_bundle() -> dict[str, Any]:
    try:
        modified_time_ns = MODEL_PATH.stat().st_mtime_ns
    except OSError as exc:
        raise ModelUnavailableError("The daily-sales model artifact is missing; train the model first.") from exc
    return _load_bundle(modified_time_ns)


def model_status() -> dict[str, Any]:
    try:
        metrics = read_metrics()
        bundle = _current_bundle()
    except ModelUnavailableError as exc:
        return {
            "trained_model_available": False,
            "model_name": None,
            "prediction_target": "daily_sales",
            "training_timestamp": None,
            "dataset_source": "data/raw/dataset_augmented.csv",
            "message": str(exc),
        }
    return {
        "trained_model_available": True,
        "model_name": bundle["model_name"],
        "prediction_target": metrics["prediction_target"],
        "training_timestamp": bundle["training_timestamp"],
        "dataset_source": metrics["dataset_source"],
        "dataset_type": metrics["dataset_type"],
        "category_options": metrics["category_options"],
        "season_options": metrics["season_options"],
        "message": None,
    }


def predict_daily_sales(values: dict[str, Any]) -> dict[str, Any]:
    metrics = read_metrics()
    bundle = _current_bundle()
    observation_date = pd.Timestamp(values["date"])
    features = pd.DataFrame([{
        "category": values["category"],
        "season": values["season"],
        "stock_qty": values["stock_qty"],
        "reorder_level": values["reorder_level"],
        "unit_cost": values["unit_cost"],
        "lead_days": values["lead_days"],
        "date_month": observation_date.month,
        "date_day_of_week": observation_date.day_of_week,
        "date_day_of_year": observation_date.day_of_year,
    }], columns=bundle["features"])
    prediction = float(bundle["pipeline"].predict(features)[0])
    return {
        "predicted_daily_sales": round(prediction, 2),
        "model_name": bundle["model_name"],
        "training_timestamp": bundle["training_timestamp"],
        "status": "success",
        "prediction_target": metrics["prediction_target"],
    }


def _season_for_date(observation_date: date) -> str:
    month_day = (observation_date.month, observation_date.day)
    if (10, 28) <= month_day <= (11, 3):
        return "Diwali"
    if observation_date.month in {12, 1, 2}:
        return "Winter"
    if observation_date.month in {3, 4, 5}:
        return "Spring"
    if observation_date.month in {6, 7, 8}:
        return "Summer"
    return "Autumn"


def predict_products_daily_sales(
    products: list[Product], observation_dates: list[date] | None = None,
) -> list[dict[str, Any]]:
    if not products:
        return []
    prediction_dates = observation_dates or [date.today()] * len(products)
    if len(prediction_dates) != len(products):
        raise ValueError("Every product must have exactly one prediction date.")
    metrics = read_metrics()
    bundle = _current_bundle()
    fallback_unit_cost = float(metrics["numeric_medians"]["unit_cost"])
    rows = [{
        "category": product.category,
        "season": _season_for_date(prediction_date),
        "stock_qty": product.stock_qty,
        "reorder_level": product.reorder_level,
        "unit_cost": product.unit_cost if product.unit_cost is not None else fallback_unit_cost,
        "lead_days": product.lead_days,
        "date_month": prediction_date.month,
        "date_day_of_week": prediction_date.weekday(),
        "date_day_of_year": prediction_date.timetuple().tm_yday,
    } for product, prediction_date in zip(products, prediction_dates)]
    features = pd.DataFrame(rows, columns=bundle["features"])
    predictions = bundle["pipeline"].predict(features)
    return [{
        "daily_sales_estimate": round(float(prediction), 2),
        "model_name": bundle["model_name"],
        "training_timestamp": bundle["training_timestamp"],
        "prediction_date": prediction_date.isoformat(),
        "season": _season_for_date(prediction_date),
    } for prediction, prediction_date in zip(predictions, prediction_dates)]


def predict_product_daily_sales(
    product: Product, observation_date: date | None = None,
) -> dict[str, Any]:
    return predict_products_daily_sales([product], [observation_date or date.today()])[0]


def predict_product_daily_sales_for_dates(product: Product, prediction_dates: list[date]) -> list[dict[str, Any]]:
    return predict_products_daily_sales([product] * len(prediction_dates), prediction_dates)