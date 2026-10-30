from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ml.preprocess import RAW_PATH, load_and_validate
from ..models import Product, SalesObservation, Supplier


def seed_from_official_data(db: Session) -> None:
    if db.scalar(select(func.count()).select_from(Product)):
        return
    if not RAW_PATH.exists():
        return

    data, _ = load_and_validate(RAW_PATH)
    if data.empty:
        return
    data = data.copy()
    data["date"] = pd.to_datetime(data["date"])

    supplier_leads = data.groupby("supplier_id")["lead_days"].median().round().astype(int)
    for supplier_id, lead_days in supplier_leads.items():
        db.add(Supplier(supplier_id=supplier_id, lead_days=int(lead_days)))

    latest = data.sort_values("date").drop_duplicates("product_id", keep="last")
    for row in latest.itertuples(index=False):
        db.add(Product(
            product_id=row.product_id,
            category=row.category,
            stock_qty=int(row.stock_qty),
            reorder_level=int(row.reorder_level),
            daily_sales=float(row.daily_sales),
            supplier_id=row.supplier_id,
            lead_days=int(row.lead_days),
            unit_cost=float(row.unit_cost),
        ))

    for row in data.itertuples(index=False):
        db.add(SalesObservation(
            product_id=row.product_id,
            observation_date=pd.Timestamp(row.date).date(),
            daily_sales=float(row.daily_sales),
            category=row.category,
        ))
    db.commit()