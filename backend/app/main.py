from __future__ import annotations

import csv
import io
import os
import time
from datetime import date, timedelta
from urllib.parse import urlsplit

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .db.database import Base, engine, get_db
from .models import AppSetting, InventoryTransaction, Product, PurchaseOrder, PurchaseOrderItem, SalesObservation, Supplier, User
from .schemas.api import (
    AuthenticatedUser, DashboardSummary, ForecastRequest, LoginInput, LoginResponse, ModelPredictionInput, ObservationPoint, ProductInput, ProductOut, ProductPage,
    PurchaseOrderInput, ReceiveInput, SettingInput, StockAdjustment, StockStatus, SupplierInput, SupplierOut,
)
from .services.auth import APP_ENV, AUTH_SECRET_KEY, COOKIE_HTTPS_ONLY, COOKIE_SAME_SITE, SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS, require_session_user, verify_password
from .services.daily_sales_model import ModelUnavailableError, model_status, predict_daily_sales, predict_product_daily_sales, predict_product_daily_sales_for_dates, predict_products_daily_sales, read_metrics
from .services.inventory import replenishment_recommendation
from .services.seed import seed_from_official_data


API_PREFIX = "/api/v1"
PUBLIC_API_PATHS = {f"{API_PREFIX}/health", f"{API_PREFIX}/auth/login", f"{API_PREFIX}/auth/logout", f"{API_PREFIX}/auth/me"}
origins = [value.strip() for value in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if value.strip()]


def _is_allowed_origin(origin: str) -> bool:
    if origin in origins:
        return True
    if APP_ENV != "development":
        return False
    try:
        parsed = urlsplit(origin)
        return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"} and parsed.port is not None
    except ValueError:
        return False


def require_api_auth(request: Request, db: Session = Depends(get_db)) -> None:
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and not _is_allowed_origin(origin):
            raise HTTPException(status_code=403, detail="Request origin is not allowed.")
    if not request.url.path.startswith(f"{API_PREFIX}/") or request.url.path in PUBLIC_API_PATHS:
        return
    require_session_user(request, db)


app = FastAPI(title="Retail Inventory Management API", version="1.0.0", dependencies=[Depends(require_api_auth)])
app.add_middleware(
    SessionMiddleware,
    secret_key=AUTH_SECRET_KEY,
    session_cookie=SESSION_COOKIE_NAME,
    max_age=SESSION_MAX_AGE_SECONDS,
    same_site=COOKIE_SAME_SITE,
    https_only=COOKIE_HTTPS_ONLY,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$" if APP_ENV == "development" else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with next(get_db()) as db:
        seed_from_official_data(db)


def _settings(db: Session) -> tuple[float, int]:
    values = {row.key: row.value for row in db.scalars(select(AppSetting)).all()}
    return float(values.get("safety_stock_rate", os.getenv("SAFETY_STOCK_RATE", "0.2"))), int(values.get("replenishment_horizon_days", os.getenv("REPLENISHMENT_HORIZON_DAYS", "14")))


@app.get(f"{API_PREFIX}/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(f"{API_PREFIX}/auth/login", response_model=LoginResponse)
def login(payload: LoginInput, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["expires_at"] = int(time.time()) + SESSION_MAX_AGE_SECONDS
    return {"user": AuthenticatedUser(id=user.id, email=user.email, is_admin=user.is_admin)}


@app.post(f"{API_PREFIX}/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"logged_out": True}


@app.get(f"{API_PREFIX}/auth/me", response_model=AuthenticatedUser)
def current_user(request: Request, db: Session = Depends(get_db)):
    user = require_session_user(request, db)
    return AuthenticatedUser(id=user.id, email=user.email, is_admin=user.is_admin)


@app.get(f"{API_PREFIX}/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    products = db.scalars(select(Product)).all()
    latest_date = db.scalar(select(func.max(SalesObservation.observation_date)))
    latest_sales = 0.0
    date_count = int(db.scalar(select(func.count(func.distinct(SalesObservation.observation_date)))) or 0)
    if latest_date:
        latest_sales = float(db.scalar(select(func.sum(SalesObservation.daily_sales)).where(SalesObservation.observation_date == latest_date)) or 0)
    return DashboardSummary(
        total_products=len(products),
        total_stock_units=sum(product.stock_qty for product in products),
        low_stock_products=sum(product.stock_qty <= product.reorder_level for product in products),
        out_of_stock_products=sum(product.stock_qty == 0 for product in products),
        latest_recorded_daily_sales_units=latest_sales,
        observation_dates=date_count,
        latest_observation_date=latest_date,
    )


@app.get(f"{API_PREFIX}/products", response_model=ProductPage)
def list_products(
    search: str | None = None,
    category: str | None = None,
    stock_status: str | None = Query(default=None, pattern="^(low|healthy|out)$"),
    sort_by: str = Query(default="product_id", pattern="^(product_id|category|stock_qty|daily_sales|lead_days|reorder_level)$"),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(Product)
    if search:
        query = query.where(Product.product_id.ilike(f"%{search.strip()}%"))
    if category:
        query = query.where(Product.category == category)
    if stock_status == "out":
        query = query.where(Product.stock_qty == 0)
    elif stock_status == "low":
        query = query.where(Product.stock_qty > 0, Product.stock_qty <= Product.reorder_level)
    elif stock_status == "healthy":
        query = query.where(Product.stock_qty > Product.reorder_level)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    sort_column = getattr(Product, sort_by)
    query = query.order_by(sort_column.desc() if sort_order == "desc" else sort_column.asc()).offset((page - 1) * page_size).limit(page_size)
    return ProductPage(items=db.scalars(query).all(), total=total, page=page, page_size=page_size)


@app.post(f"{API_PREFIX}/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductInput, db: Session = Depends(get_db)):
    if db.get(Product, payload.product_id):
        raise HTTPException(409, "Product ID already exists.")
    if payload.supplier_id and not db.get(Supplier, payload.supplier_id):
        raise HTTPException(422, "Supplier does not exist.")
    product = Product(**payload.model_dump())
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Product could not be created due to a conflicting record.")
    db.refresh(product)
    return product


@app.get(f"{API_PREFIX}/products/{{product_id}}", response_model=ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")
    return product


@app.put(f"{API_PREFIX}/products/{{product_id}}", response_model=ProductOut)
def update_product(product_id: str, payload: ProductInput, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")
    if payload.product_id != product_id:
        raise HTTPException(422, "Product ID cannot be changed.")
    if payload.supplier_id and not db.get(Supplier, payload.supplier_id):
        raise HTTPException(422, "Supplier does not exist.")
    for key, value in payload.model_dump().items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@app.delete(f"{API_PREFIX}/products/{{product_id}}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: str, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")
    if product.transactions or db.scalar(select(PurchaseOrderItem.id).where(PurchaseOrderItem.product_id == product_id).limit(1)):
        raise HTTPException(409, "Product has stock or purchase-order history and cannot be deleted.")
    db.delete(product)
    db.commit()


@app.post(f"{API_PREFIX}/products/{{product_id}}/stock-adjustments", status_code=status.HTTP_201_CREATED)
def adjust_stock(product_id: str, payload: StockAdjustment, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")
    if payload.quantity_delta == 0:
        raise HTTPException(422, "Adjustment quantity cannot be zero.")
    new_stock = product.stock_qty + payload.quantity_delta
    if new_stock < 0:
        raise HTTPException(422, "Adjustment would make stock negative.")
    product.stock_qty = new_stock
    transaction = InventoryTransaction(product_id=product_id, quantity_delta=payload.quantity_delta, reason=payload.reason)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return {"id": transaction.id, "product_id": product_id, "stock_qty": new_stock, "quantity_delta": transaction.quantity_delta, "reason": transaction.reason, "created_at": transaction.created_at}


@app.get(f"{API_PREFIX}/suppliers", response_model=list[SupplierOut])
def list_suppliers(search: str | None = None, db: Session = Depends(get_db)):
    query = select(Supplier).order_by(Supplier.supplier_id)
    if search:
        query = query.where(Supplier.supplier_id.ilike(f"%{search.strip()}%"))
    return [{**{key: getattr(supplier, key) for key in ("supplier_id", "contact_name", "email", "phone", "lead_days")}, "products_count": len(supplier.products)} for supplier in db.scalars(query).all()]


@app.post(f"{API_PREFIX}/suppliers", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierInput, db: Session = Depends(get_db)):
    if db.get(Supplier, payload.supplier_id):
        raise HTTPException(409, "Supplier ID already exists.")
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@app.put(f"{API_PREFIX}/suppliers/{{supplier_id}}", response_model=SupplierOut)
def update_supplier(supplier_id: str, payload: SupplierInput, db: Session = Depends(get_db)):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "Supplier not found.")
    if supplier_id != payload.supplier_id:
        raise HTTPException(422, "Supplier ID cannot be changed.")
    for key, value in payload.model_dump().items():
        setattr(supplier, key, value)
    db.commit()
    db.refresh(supplier)
    return supplier


@app.get(f"{API_PREFIX}/reorders", response_model=list[StockStatus])
def get_reorders(db: Session = Depends(get_db)):
    rate, horizon = _settings(db)
    products = list(db.scalars(select(Product)).all())
    try:
        estimates = predict_products_daily_sales(products)
    except ModelUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc
    recommendations = [
        replenishment_recommendation(product, estimate["daily_sales_estimate"], rate, horizon)
        for product, estimate in zip(products, estimates)
    ]
    return sorted((item for item in recommendations if item["stock_qty"] <= item["reorder_point"]), key=lambda item: (-item["recommended_quantity"], item["product_id"]))


def _forecast(product_id: str, horizon_days: int, db: Session):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Product not found.")
    observations = db.scalars(select(SalesObservation).where(SalesObservation.product_id == product_id).order_by(SalesObservation.observation_date)).all()
    prediction_dates = [date.today() + timedelta(days=offset) for offset in range(1, horizon_days + 1)]
    try:
        predictions = predict_product_daily_sales_for_dates(product, prediction_dates)
    except ModelUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc
    estimated_units = sum(item["daily_sales_estimate"] for item in predictions)
    average_daily_estimate = estimated_units / horizon_days
    return {
        "product_id": product_id,
        "horizon_days": horizon_days,
        "estimated_units": round(estimated_units, 2),
        "daily_sales_estimate": round(average_daily_estimate, 2),
        "model_name": predictions[0]["model_name"],
        "training_timestamp": predictions[0]["training_timestamp"],
        "method": predictions[0]["model_name"],
        "predictions": predictions,
        "historical_series_available": False,
        "observations": [{"date": item.observation_date, "daily_sales": item.daily_sales} for item in observations],
    }


@app.get(f"{API_PREFIX}/forecasts/{{product_id}}")
def get_forecast(product_id: str, horizon_days: int = Query(default=14, ge=1, le=365), db: Session = Depends(get_db)):
    return _forecast(product_id, horizon_days, db)


@app.post(f"{API_PREFIX}/forecasts/{{product_id}}")
def create_forecast(product_id: str, payload: ForecastRequest, db: Session = Depends(get_db)):
    return _forecast(product_id, payload.horizon_days, db)


@app.get(f"{API_PREFIX}/analytics/sales")
def sales_analytics(db: Session = Depends(get_db)):
    rows = db.execute(select(SalesObservation.observation_date, func.sum(SalesObservation.daily_sales), func.count(SalesObservation.id)).group_by(SalesObservation.observation_date).order_by(SalesObservation.observation_date)).all()
    top = db.execute(select(SalesObservation.product_id, func.sum(SalesObservation.daily_sales).label("units")).group_by(SalesObservation.product_id).order_by(func.sum(SalesObservation.daily_sales).desc()).limit(10)).all()
    return {
        "available": bool(rows),
        "source_label": "recorded source observations; not a complete sales ledger",
        "timeline": [ObservationPoint(date=row[0], recorded_sales_units=float(row[1] or 0), observation_rows=int(row[2])) for row in rows],
        "top_products": [{"product_id": row[0], "recorded_sales_units": float(row[1] or 0)} for row in top],
    }


@app.get(f"{API_PREFIX}/analytics/inventory")
def inventory_analytics(db: Session = Depends(get_db)):
    products = db.scalars(select(Product)).all()
    categories: dict[str, dict[str, int]] = {}
    for product in products:
        item = categories.setdefault(product.category, {"products": 0, "stock_units": 0, "low_stock": 0})
        item["products"] += 1
        item["stock_units"] += product.stock_qty
        item["low_stock"] += int(product.stock_qty <= product.reorder_level)
    return {"products": len(products), "categories": [{"category": key, **value} for key, value in sorted(categories.items())], "status": {"healthy": sum(p.stock_qty > p.reorder_level for p in products), "low": sum(0 < p.stock_qty <= p.reorder_level for p in products), "out": sum(p.stock_qty == 0 for p in products)}}


@app.get(f"{API_PREFIX}/model/metrics")
def model_metrics():
    status_result = model_status()
    if not status_result["trained_model_available"]:
        raise HTTPException(503, status_result["message"] or "The daily-sales model is unavailable.")
    try:
        return read_metrics()
    except ModelUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get(f"{API_PREFIX}/model/status")
def get_model_status():
    return model_status()


@app.post(f"{API_PREFIX}/model/predict")
def predict_model_daily_sales(payload: ModelPredictionInput):
    try:
        return predict_daily_sales(payload.model_dump())
    except ModelUnavailableError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, "The daily-sales prediction could not be produced.") from exc


@app.get(f"{API_PREFIX}/settings")
def get_settings(db: Session = Depends(get_db)):
    rate, horizon = _settings(db)
    return {"safety_stock_rate": rate, "replenishment_horizon_days": horizon}


@app.put(f"{API_PREFIX}/settings")
def update_settings(payload: SettingInput, db: Session = Depends(get_db)):
    for key, value in payload.model_dump().items():
        setting = db.get(AppSetting, key) or AppSetting(key=key, value=str(value))
        setting.value = str(value)
        db.add(setting)
    db.commit()
    return payload.model_dump()


@app.get(f"{API_PREFIX}/transactions")
def recent_transactions(limit: int = Query(default=10, ge=1, le=100), db: Session = Depends(get_db)):
    transactions = db.scalars(select(InventoryTransaction).order_by(InventoryTransaction.created_at.desc()).limit(limit)).all()
    return [{"id": item.id, "product_id": item.product_id, "quantity_delta": item.quantity_delta, "reason": item.reason, "created_at": item.created_at} for item in transactions]


@app.post(f"{API_PREFIX}/purchase-orders", status_code=status.HTTP_201_CREATED)
def create_purchase_order(payload: PurchaseOrderInput, db: Session = Depends(get_db)):
    if not db.get(Supplier, payload.supplier_id):
        raise HTTPException(422, "Supplier does not exist.")
    product_ids = [line.product_id for line in payload.items]
    if len(set(product_ids)) != len(product_ids):
        raise HTTPException(422, "A product may appear only once per purchase order.")
    for line in payload.items:
        if not db.get(Product, line.product_id):
            raise HTTPException(422, f"Product {line.product_id} does not exist.")
    order = PurchaseOrder(supplier_id=payload.supplier_id, items=[PurchaseOrderItem(product_id=line.product_id, quantity_ordered=line.quantity) for line in payload.items])
    db.add(order)
    db.commit()
    db.refresh(order)
    return {"id": order.id, "supplier_id": order.supplier_id, "status": order.status, "items": [{"id": item.id, "product_id": item.product_id, "quantity_ordered": item.quantity_ordered, "quantity_received": item.quantity_received} for item in order.items]}


@app.post(f"{API_PREFIX}/purchase-orders/{{order_id}}/receipts")
def receive_purchase_order(order_id: int, payload: ReceiveInput, db: Session = Depends(get_db)):
    order = db.scalar(select(PurchaseOrder).options(selectinload(PurchaseOrder.items)).where(PurchaseOrder.id == order_id))
    if not order:
        raise HTTPException(404, "Purchase order not found.")
    by_id = {item.id: item for item in order.items}
    if len({line.item_id for line in payload.items}) != len(payload.items):
        raise HTTPException(422, "Each order line may appear only once per receipt.")
    products: list[tuple[Product, int]] = []
    for line in payload.items:
        item = by_id.get(line.item_id)
        if not item or item.quantity_received + line.quantity > item.quantity_ordered:
            raise HTTPException(422, "Receipt quantity exceeds an outstanding purchase-order quantity.")
        products.append((db.get(Product, item.product_id), line.quantity))
    for line, (product, quantity) in zip(payload.items, products):
        item = by_id[line.item_id]
        item.quantity_received += quantity
        product.stock_qty += quantity
        db.add(InventoryTransaction(product_id=product.product_id, quantity_delta=quantity, reason=f"Purchase order {order_id} received"))
    order.status = "received" if all(item.quantity_received == item.quantity_ordered for item in order.items) else "partially_received"
    db.commit()
    return {"id": order.id, "status": order.status, "received_lines": len(payload.items)}


def _read_upload(upload: UploadFile) -> pd.DataFrame:
    if not upload.filename or not upload.filename.lower().endswith(".csv"):
        raise HTTPException(415, "Upload a .csv file.")
    content = upload.file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "CSV files must be 5 MB or smaller.")
    try:
        frame = pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(422, "Could not parse the CSV file.") from exc
    expected = {"date", "product_id", "category", "season", "stock_qty", "reorder_level", "daily_sales", "unit_cost", "supplier_id", "lead_days"}
    missing = sorted(expected - set(frame.columns))
    if missing:
        raise HTTPException(422, f"Missing required columns: {', '.join(missing)}")
    if len(frame) > 10000:
        raise HTTPException(413, "CSV files may contain at most 10,000 rows.")
    for column in ["stock_qty", "reorder_level", "daily_sales", "unit_cost", "lead_days"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    bad = frame[list(expected)].isna().any(axis=1)
    bad |= frame[["product_id", "category", "season", "supplier_id"]].astype("string").apply(lambda column: column.str.strip().eq("")).any(axis=1)
    for column in ["stock_qty", "reorder_level", "daily_sales", "unit_cost", "lead_days"]:
        bad |= (frame[column] < 0) | ~frame[column].map(lambda value: pd.notna(value) and abs(value) != float("inf"))
    for column in ["stock_qty", "reorder_level", "lead_days"]:
        bad |= frame[column].notna() & (frame[column] % 1 != 0)
    if bad.any():
        raise HTTPException(422, f"CSV contains {int(bad.sum())} invalid row(s); no rows were imported.")
    return frame


@app.post(f"{API_PREFIX}/imports/preview")
def preview_import(file: UploadFile = File(...)):
    frame = _read_upload(file)
    return {"valid": True, "rows": len(frame), "products": int(frame.product_id.nunique()), "suppliers": int(frame.supplier_id.nunique()), "duplicate_product_dates": int(frame.duplicated(["date", "product_id"]).sum()), "message": "Preview only; no database changes were made."}


@app.post(f"{API_PREFIX}/imports/confirm")
def confirm_import(file: UploadFile = File(...), db: Session = Depends(get_db)):
    frame = _read_upload(file).sort_values("date")
    latest = frame.drop_duplicates("product_id", keep="last")
    try:
        for supplier_id, group in frame.groupby("supplier_id"):
            supplier = db.get(Supplier, supplier_id)
            if not supplier:
                db.add(Supplier(supplier_id=supplier_id, lead_days=int(group.lead_days.median().round())))
        db.flush()
        for row in latest.itertuples(index=False):
            product = db.get(Product, row.product_id)
            values = {"category": row.category, "stock_qty": int(row.stock_qty), "reorder_level": int(row.reorder_level), "daily_sales": float(row.daily_sales), "supplier_id": row.supplier_id, "lead_days": int(row.lead_days), "unit_cost": float(row.unit_cost)}
            if product:
                for key, value in values.items():
                    setattr(product, key, value)
            else:
                db.add(Product(product_id=row.product_id, **values))
        for row in frame.itertuples(index=False):
            db.add(SalesObservation(product_id=row.product_id, observation_date=row.date.date(), daily_sales=float(row.daily_sales), category=row.category, source="csv_import"))
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(422, "Import could not be committed; the transaction was rolled back.")
    return {"imported_observations": len(frame), "upserted_products": len(latest), "message": "Import committed."}


@app.get(f"{API_PREFIX}/exports/inventory.csv")
def export_inventory(db: Session = Depends(get_db)):
    products = db.scalars(select(Product).order_by(Product.product_id)).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["product_id", "category", "stock_qty", "reorder_level", "daily_sales", "supplier_id", "lead_days"])
    for product in products:
        writer.writerow([product.product_id, product.category, product.stock_qty, product.reorder_level, product.daily_sales, product.supplier_id or "", product.lead_days])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=inventory.csv"})


@app.exception_handler(IntegrityError)
def handle_integrity_error(request, exc):
    return JSONResponse(status_code=409, content={"detail": "The operation conflicts with existing data."})