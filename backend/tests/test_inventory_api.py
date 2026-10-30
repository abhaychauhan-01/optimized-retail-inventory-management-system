import math

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.database import Base
from backend.app.models import Product, User
from backend.app.services import auth as auth_service
from backend.app.services import daily_sales_model
from backend.app.services import seed_admin
from backend.app.services.inventory import replenishment_recommendation


def test_reorder_policy_handles_zero_sales_and_zero_lead_time():
    product = Product(product_id="ZERO", category="Test", stock_qty=0, reorder_level=5, daily_sales=0, lead_days=0)
    result = replenishment_recommendation(product, daily_sales_estimate=0, safety_stock_rate=0.2, horizon_days=14)
    assert result["expected_lead_demand"] == 0
    assert result["reorder_point"] == 0
    assert result["recommended_quantity"] == 0


def test_reorder_recommendation_at_exact_point():
    product = Product(product_id="EDGE", category="Test", stock_qty=36, reorder_level=8, daily_sales=10, lead_days=3)
    result = replenishment_recommendation(product, daily_sales_estimate=10, safety_stock_rate=0.2, horizon_days=14)
    assert result["reorder_point"] == 36
    assert result["recommended_quantity"] == 110


def test_auth_login_logout_and_protected_api_access(client):
    client.cookies.clear()
    assert client.get("/api/v1/products").status_code == 401
    assert client.get("/api/v1/health").status_code == 200

    invalid = client.post("/api/v1/auth/login", json={"email": "tester@example.test", "password": "wrong-password"})
    assert invalid.status_code == 401
    assert invalid.json()["detail"] == "Invalid email or password."

    login = client.post("/api/v1/auth/login", json={"email": " TESTER@example.test ", "password": "correct-test-password"})
    assert login.status_code == 200
    assert "password" not in login.json()["user"]
    cookie_header = login.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header

    current = client.get("/api/v1/auth/me")
    assert current.status_code == 200
    assert current.json()["email"] == "tester@example.test"
    assert client.get("/api/v1/products").status_code == 200
    refresh_cookie = client.cookies.get(auth_service.SESSION_COOKIE_NAME)
    with TestClient(client.app) as refreshed_client:
        refreshed_client.cookies.set(auth_service.SESSION_COOKIE_NAME, refresh_cookie)
        refreshed = refreshed_client.get("/api/v1/auth/me")
        assert refreshed.status_code == 200
        assert refreshed.json()["email"] == "tester@example.test"

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert logout.json()["logged_out"] is True
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/products").status_code == 401


def test_expired_session_is_rejected(client, monkeypatch):
    client.cookies.clear()
    login = client.post("/api/v1/auth/login", json={"email": "tester@example.test", "password": "correct-test-password"})
    assert login.status_code == 200
    current_time = auth_service.time.time()
    monkeypatch.setattr(auth_service.time, "time", lambda: current_time + auth_service.SESSION_MAX_AGE_SECONDS + 1)

    expired = client.get("/api/v1/auth/me")
    assert expired.status_code == 401


def test_demo_admin_seed_hashes_password_and_is_development_only(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(seed_admin, "engine", engine)
    monkeypatch.setattr(seed_admin, "SessionLocal", testing_session)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEMO_ADMIN_EMAIL", "admin@example.test")
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "development-password-123")

    seed_admin.seed_demo_admin()
    with testing_session() as db:
        user = db.query(User).filter_by(email="admin@example.test").one()
        password_hash = user.password_hash
        assert user.is_admin is True
        assert user.password_hash != "development-password-123"
        assert auth_service.verify_password("development-password-123", user.password_hash)

    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "different-password-456")
    seed_admin.seed_demo_admin()
    with testing_session() as db:
        user = db.query(User).filter_by(email="admin@example.test").one()
        assert user.password_hash == password_hash

    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="only when APP_ENV=development"):
        seed_admin.seed_demo_admin()
    engine.dispose()


def test_products_search_and_pagination(client):
    response = client.get("/api/v1/products?search=SKU-T&page=1&page_size=1")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["product_id"] == "SKU-T"


def test_product_create_and_edit(client):
    payload = {
        "product_id": "SKU-NEW",
        "category": "Test",
        "stock_qty": 3,
        "reorder_level": 5,
        "daily_sales": 2.5,
        "supplier_id": "SUP-T",
        "lead_days": 4,
    }
    created = client.post("/api/v1/products", json=payload)
    assert created.status_code == 201
    assert created.json()["stock_qty"] == 3

    updated_payload = {**payload, "stock_qty": 12, "category": "Updated"}
    updated = client.put("/api/v1/products/SKU-NEW", json=updated_payload)
    assert updated.status_code == 200
    assert updated.json()["stock_qty"] == 12
    assert updated.json()["category"] == "Updated"
    assert client.get("/api/v1/products/SKU-NEW").json()["stock_qty"] == 12


def test_stock_adjustment_tracks_movement_and_prevents_negative(client):
    response = client.post("/api/v1/products/SKU-T/stock-adjustments", json={"quantity_delta": -2, "reason": "Cycle count"})
    assert response.status_code == 201
    assert response.json()["stock_qty"] == 6
    rejected = client.post("/api/v1/products/SKU-T/stock-adjustments", json={"quantity_delta": -9, "reason": "Invalid count"})
    assert rejected.status_code == 422


def test_reorders_and_dashboard_are_database_backed(client):
    reorder = client.get("/api/v1/reorders")
    assert reorder.status_code == 200
    item = reorder.json()[0]
    assert item["product_id"] == "SKU-T"
    assert item["daily_sales"] != 2
    assert item["method"] == "trained daily-sales regression estimate with rule-based reorder policy"
    assert item["daily_sales_estimate"] == item["daily_sales"]
    lead_demand = item["daily_sales"] * item["lead_days"]
    safety_stock = math.ceil(lead_demand * 0.2)
    target_stock = math.ceil(item["daily_sales"] * 14 + safety_stock)
    assert item["expected_lead_demand"] == round(lead_demand, 2)
    assert item["reorder_point"] == math.ceil(lead_demand + safety_stock)
    assert item["recommended_quantity"] == target_stock - item["stock_qty"]
    summary = client.get("/api/v1/dashboard/summary").json()
    assert summary["total_products"] == 1
    assert summary["total_stock_units"] == 8


def test_demand_estimate_uses_daily_model_predictions_for_horizon(client):
    response = client.get("/api/v1/forecasts/SKU-T?horizon_days=3")
    assert response.status_code == 200
    forecast = response.json()
    assert forecast["model_name"] == "RandomForestRegressor"
    assert len(forecast["predictions"]) == 3
    assert all(item["daily_sales_estimate"] > 0 for item in forecast["predictions"])
    assert forecast["estimated_units"] == round(sum(item["daily_sales_estimate"] for item in forecast["predictions"]), 2)
    assert forecast["daily_sales_estimate"] == pytest.approx(forecast["estimated_units"] / 3)
    assert "daily_sales_baseline" not in forecast


def test_daily_sales_model_status_metrics_and_prediction(client):
    status = client.get("/api/v1/model/status")
    assert status.status_code == 200
    assert status.json()["trained_model_available"] is True
    assert status.json()["model_name"] == "RandomForestRegressor"
    assert status.json()["prediction_target"] == "daily_sales"
    assert status.json()["dataset_source"] == "data/raw/dataset_augmented.csv"

    response = client.get("/api/v1/model/metrics")
    assert response.status_code == 200
    metrics = response.json()
    assert metrics["trained_model_available"] is True
    assert metrics["dataset_type"] == "Mixed"
    assert metrics["total_observations"] == 5000
    assert metrics["original_observations"] == 500
    assert metrics["synthetic_observations"] == 4500
    assert metrics["training_observations"] + metrics["evaluation_observations"] == 5000
    assert metrics["mae"] >= 0
    assert metrics["rmse"] >= 0
    assert "product_id" not in metrics["features"]

    prediction = client.post("/api/v1/model/predict", json={
        "date": "2024-06-15",
        "category": "Grocery",
        "season": "Summer",
        "stock_qty": 120,
        "reorder_level": 50,
        "unit_cost": 250.0,
        "lead_days": 7,
    })
    assert prediction.status_code == 200
    assert prediction.json()["predicted_daily_sales"] > 0
    assert prediction.json()["model_name"] == metrics["model_name"]
    assert prediction.json()["training_timestamp"] == status.json()["training_timestamp"]

    invalid = client.post("/api/v1/model/predict", json={
        "date": "2024-06-15",
        "category": "Grocery",
        "season": "Summer",
        "stock_qty": -1,
        "reorder_level": 50,
        "unit_cost": 250.0,
        "lead_days": 7,
    })
    assert invalid.status_code == 422


def test_model_metrics_reports_unavailable_artifact(client, monkeypatch, tmp_path):
    monkeypatch.setattr(daily_sales_model, "MODEL_PATH", tmp_path / "missing.joblib")

    status = client.get("/api/v1/model/status")
    assert status.status_code == 200
    assert status.json()["trained_model_available"] is False

    metrics = client.get("/api/v1/model/metrics")
    assert metrics.status_code == 503
    assert "artifact is missing" in metrics.json()["detail"]

    prediction = client.post("/api/v1/model/predict", json={
        "date": "2024-06-15",
        "category": "Grocery",
        "season": "Summer",
        "stock_qty": 120,
        "reorder_level": 50,
        "unit_cost": 250.0,
        "lead_days": 7,
    })
    assert prediction.status_code == 503
    assert client.get("/api/v1/forecasts/SKU-T").status_code == 503
    assert client.get("/api/v1/reorders").status_code == 503


def test_replenishment_settings_round_trip(client):
    updated = client.put("/api/v1/settings", json={"safety_stock_rate": 0.35, "replenishment_horizon_days": 21})
    assert updated.status_code == 200
    assert client.get("/api/v1/settings").json() == {"safety_stock_rate": 0.35, "replenishment_horizon_days": 21}


def test_product_requires_valid_supplier(client):
    response = client.post("/api/v1/products", json={"product_id": "SKU-X", "category": "Test", "stock_qty": 1, "reorder_level": 0, "daily_sales": 0, "supplier_id": "MISSING", "lead_days": 0})
    assert response.status_code == 422


def test_supplier_create_and_edit(client):
    created = client.post("/api/v1/suppliers", json={
        "supplier_id": "SUP-NEW",
        "contact_name": "Verified Contact",
        "email": "contact@example.test",
        "phone": None,
        "lead_days": 6,
    })
    assert created.status_code == 201
    assert created.json()["supplier_id"] == "SUP-NEW"

    updated = client.put("/api/v1/suppliers/SUP-NEW", json={
        "supplier_id": "SUP-NEW",
        "contact_name": "Updated Contact",
        "email": "updated@example.test",
        "phone": None,
        "lead_days": 8,
    })
    assert updated.status_code == 200
    assert updated.json()["contact_name"] == "Updated Contact"
    assert updated.json()["lead_days"] == 8
    assert client.get("/api/v1/suppliers?search=SUP-NEW").json()[0]["lead_days"] == 8


def test_purchase_order_receipt_updates_stock_transactionally(client):
    order = client.post("/api/v1/purchase-orders", json={"supplier_id": "SUP-T", "items": [{"product_id": "SKU-T", "quantity": 5}]})
    assert order.status_code == 201
    item_id = order.json()["items"][0]["id"]
    receipt = client.post(f"/api/v1/purchase-orders/{order.json()['id']}/receipts", json={"items": [{"item_id": item_id, "quantity": 3}]})
    assert receipt.status_code == 200
    assert receipt.json()["status"] == "partially_received"
    product = client.get("/api/v1/products/SKU-T").json()
    assert product["stock_qty"] == 11
    overshoot = client.post(f"/api/v1/purchase-orders/{order.json()['id']}/receipts", json={"items": [{"item_id": item_id, "quantity": 3}]})
    assert overshoot.status_code == 422


def test_csv_preview_rejects_invalid_numeric_rows(client):
    invalid_csv = "date,product_id,category,season,stock_qty,reorder_level,daily_sales,unit_cost,supplier_id,lead_days\n2024-01-01,X,Food,Winter,-1,2,1,1.0,SUP-T,2\n"
    response = client.post("/api/v1/imports/preview", files={"file": ("inventory.csv", invalid_csv, "text/csv")})
    assert response.status_code == 422


def test_csv_preview_and_confirm_import_valid_rows(client):
    valid_csv = "date,product_id,category,season,stock_qty,reorder_level,daily_sales,unit_cost,supplier_id,lead_days\n2024-01-01,SKU-NEW,Food,Winter,4,2,1,2.5,SUP-T,3\n"
    preview = client.post("/api/v1/imports/preview", files={"file": ("inventory.csv", valid_csv, "text/csv")})
    assert preview.status_code == 200
    assert preview.json()["rows"] == 1
    imported = client.post("/api/v1/imports/confirm", files={"file": ("inventory.csv", valid_csv, "text/csv")})
    assert imported.status_code == 200
    assert client.get("/api/v1/products/SKU-NEW").status_code == 200
    sales = client.get("/api/v1/analytics/sales").json()
    assert sales["available"] is True
    assert sales["timeline"][0]["date"] == "2024-01-01"
    assert sales["timeline"][0]["recorded_sales_units"] == 1


def test_inventory_csv_export_contains_database_rows_without_unit_cost(client):
    response = client.get("/api/v1/exports/inventory.csv")
    assert response.status_code == 200
    rows = response.text.splitlines()
    assert rows[0] == "product_id,category,stock_qty,reorder_level,daily_sales,supplier_id,lead_days"
    assert "SKU-T" in rows[1]
    assert "unit_cost" not in rows[0]