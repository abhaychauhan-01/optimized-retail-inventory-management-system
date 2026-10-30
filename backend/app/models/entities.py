from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    lead_days: Mapped[int] = mapped_column(Integer, default=0)
    products: Mapped[list[Product]] = relationship(back_populates="supplier")

    __table_args__ = (CheckConstraint("lead_days >= 0", name="ck_supplier_lead_days_nonnegative"),)


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    category: Mapped[str] = mapped_column(String(100), index=True)
    stock_qty: Mapped[int] = mapped_column(Integer)
    reorder_level: Mapped[int] = mapped_column(Integer)
    daily_sales: Mapped[float] = mapped_column(Float, default=0)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.supplier_id"), index=True, nullable=True)
    lead_days: Mapped[int] = mapped_column(Integer, default=0)
    unit_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    supplier: Mapped[Supplier | None] = relationship(back_populates="products")
    transactions: Mapped[list[InventoryTransaction]] = relationship(back_populates="product")

    __table_args__ = (
        CheckConstraint("stock_qty >= 0", name="ck_product_stock_nonnegative"),
        CheckConstraint("reorder_level >= 0", name="ck_product_reorder_nonnegative"),
        CheckConstraint("daily_sales >= 0", name="ck_product_sales_nonnegative"),
        CheckConstraint("lead_days >= 0", name="ck_product_lead_days_nonnegative"),
    )


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), index=True)
    quantity_delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    product: Mapped[Product] = relationship(back_populates="transactions")

    __table_args__ = (CheckConstraint("quantity_delta != 0", name="ck_transaction_nonzero"),)


class SalesObservation(Base):
    __tablename__ = "sales_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(80), index=True)
    observation_date: Mapped[date] = mapped_column(Date, index=True)
    daily_sales: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(100), index=True)
    source: Mapped[str] = mapped_column(String(40), default="official_dataset")

    __table_args__ = (Index("ix_sales_product_date", "product_id", "observation_date"),)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    items: Mapped[list[PurchaseOrderItem]] = relationship(back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), index=True)
    quantity_ordered: Mapped[int] = mapped_column(Integer)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0)
    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity_ordered > 0", name="ck_ordered_positive"),
        CheckConstraint("quantity_received >= 0 AND quantity_received <= quantity_ordered", name="ck_received_range"),
        UniqueConstraint("purchase_order_id", "product_id", name="uq_order_product"),
    )


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))