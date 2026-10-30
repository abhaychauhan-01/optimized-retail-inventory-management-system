from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductInput(BaseModel):
    product_id: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=100)
    stock_qty: int = Field(ge=0)
    reorder_level: int = Field(ge=0)
    daily_sales: float = Field(ge=0, allow_inf_nan=False)
    supplier_id: str | None = Field(default=None, max_length=80)
    lead_days: int = Field(ge=0)
    unit_cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class ProductOut(ProductInput):
    model_config = ConfigDict(from_attributes=True)
    updated_at: datetime


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int


class StockAdjustment(BaseModel):
    quantity_delta: int
    reason: str = Field(min_length=3, max_length=200)


class SupplierInput(BaseModel):
    supplier_id: str = Field(min_length=1, max_length=80)
    contact_name: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    lead_days: int = Field(ge=0)


class SupplierOut(SupplierInput):
    model_config = ConfigDict(from_attributes=True)
    products_count: int = 0


class ForecastRequest(BaseModel):
    horizon_days: int = Field(default=14, ge=1, le=365)


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or "." not in cleaned.rsplit("@", 1)[-1]:
            raise ValueError("Enter a valid email address.")
        return cleaned


class AuthenticatedUser(BaseModel):
    id: int
    email: str
    is_admin: bool


class LoginResponse(BaseModel):
    user: AuthenticatedUser


class ModelPredictionInput(BaseModel):
    date: date
    category: str = Field(min_length=1, max_length=100)
    season: str = Field(min_length=1, max_length=100)
    stock_qty: int = Field(ge=0)
    reorder_level: int = Field(ge=0)
    unit_cost: float = Field(ge=0, allow_inf_nan=False)
    lead_days: int = Field(ge=0)

    @field_validator("category", "season")
    @classmethod
    def require_nonblank_label(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Value must not be blank.")
        return cleaned


class PurchaseOrderLine(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class PurchaseOrderInput(BaseModel):
    supplier_id: str
    items: list[PurchaseOrderLine] = Field(min_length=1)


class ReceiveLine(BaseModel):
    item_id: int
    quantity: int = Field(gt=0)


class ReceiveInput(BaseModel):
    items: list[ReceiveLine] = Field(min_length=1)


class SettingInput(BaseModel):
    safety_stock_rate: float = Field(default=0.2, ge=0, le=2, allow_inf_nan=False)
    replenishment_horizon_days: int = Field(default=14, ge=1, le=365)


class StockStatus(BaseModel):
    product_id: str
    category: str
    stock_qty: int
    daily_sales: float
    daily_sales_estimate: float
    lead_days: int
    safety_stock: int
    expected_lead_demand: float
    reorder_point: int
    target_stock: int
    recommended_quantity: int
    supplier_id: str | None
    method: str = "trained daily-sales regression estimate with rule-based reorder policy"


class ObservationPoint(BaseModel):
    date: date
    recorded_sales_units: float
    observation_rows: int


class DashboardSummary(BaseModel):
    total_products: int
    total_stock_units: int
    low_stock_products: int
    out_of_stock_products: int
    latest_recorded_daily_sales_units: float
    observation_dates: int
    latest_observation_date: date | None