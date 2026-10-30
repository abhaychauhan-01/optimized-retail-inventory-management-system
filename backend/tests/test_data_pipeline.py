from pathlib import Path

import pandas as pd
import pytest

from ml.evaluate import assess_suitability, build_dataset_audit
from ml.preprocess import load_and_validate


def test_preprocess_preserves_valid_rows_and_reports_duplicate_keys(tmp_path: Path):
    source = tmp_path / "sample.csv"
    pd.DataFrame([
        {"date": "2024-01-01", "product_id": "A", "category": "Food", "season": "Winter", "stock_qty": 4, "reorder_level": 2, "daily_sales": 1, "unit_cost": 2.5, "supplier_id": "S", "lead_days": 1},
        {"date": "2024-01-01", "product_id": "A", "category": "Food", "season": "Winter", "stock_qty": 3, "reorder_level": 2, "daily_sales": 1, "unit_cost": 2.5, "supplier_id": "S", "lead_days": 1},
        {"date": "invalid", "product_id": "B", "category": "Food", "season": "Winter", "stock_qty": 4, "reorder_level": 2, "daily_sales": 1, "unit_cost": 2.5, "supplier_id": "S", "lead_days": 1},
    ]).to_csv(source, index=False)
    clean, quality = load_and_validate(source)
    assert len(clean) == 2
    assert quality["invalid_rows_removed"] == 1
    assert quality["rows_with_duplicate_product_date"] == 2


def test_preprocess_rejects_missing_required_column(tmp_path: Path):
    source = tmp_path / "incomplete.csv"
    pd.DataFrame({"product_id": ["A"]}).to_csv(source, index=False)
    with pytest.raises(ValueError, match="missing required columns"):
        load_and_validate(source)


def test_sparse_official_data_does_not_pass_model_gate():
    data = pd.read_csv(Path(__file__).resolve().parents[2] / "data" / "raw" / "dataset.csv")
    result = assess_suitability(data)
    assert result["suitable"] is False
    assert result["products_with_at_least_10_dates"] == 0


def test_official_dataset_audit_keeps_conflicting_rows_and_rejects_targets():
    source_path = Path(__file__).resolve().parents[2] / "data" / "raw" / "dataset.csv"
    source_bytes = source_path.read_bytes()
    data = pd.read_csv(source_path)
    audit = build_dataset_audit(data)
    assert source_path.read_bytes() == source_bytes
    assert audit["total_observations"] == 500
    assert len(audit["columns"]) == 10
    assert audit["duplicate_group_count"] == 12
    assert audit["duplicate_participating_rows"] == 24
    assert audit["exact_duplicate_rows"] == 0
    assert all(group["conflicting_columns"] for group in audit["duplicate_groups"])
    assert audit["current_below_reorder_rows"] == 64
    assert audit["current_stockout_rows"] == 1
    assert audit["successive_unambiguous_pairs"] == 170
    assert audit["next_observation_stockout_rows"] == 0
    assert audit["average_distinct_dates_per_product"] == pytest.approx(1.5691, abs=0.001)
    assert audit["product_ids_with_multiple_categories"] == 112
    assert audit["suppliers_with_variable_lead_days"] == 30
    assert audit["candidate_tasks"][0]["status"] == "not supported"
    assert audit["candidate_tasks"][1]["status"] == "not independent"
    assert audit["candidate_tasks"][-1]["status"] == "not supported"