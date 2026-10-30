from __future__ import annotations

import math

from ..models import Product


def replenishment_recommendation(
    product: Product,
    daily_sales_estimate: float,
    safety_stock_rate: float = 0.2,
    horizon_days: int = 14,
) -> dict[str, object]:
    if product.stock_qty < 0 or not math.isfinite(daily_sales_estimate) or daily_sales_estimate < 0 or product.lead_days < 0:
        raise ValueError("Stock, sales, and lead time must be non-negative.")
    if not 0 <= safety_stock_rate <= 2 or not 1 <= horizon_days <= 365:
        raise ValueError("Safety stock rate or replenishment horizon is outside supported limits.")

    lead_demand = daily_sales_estimate * product.lead_days
    safety_stock = math.ceil(lead_demand * safety_stock_rate)
    reorder_point = math.ceil(lead_demand + safety_stock)
    target_stock = math.ceil(daily_sales_estimate * horizon_days + safety_stock)
    return {
        "product_id": product.product_id,
        "category": product.category,
        "stock_qty": product.stock_qty,
        "daily_sales": round(daily_sales_estimate, 2),
        "daily_sales_estimate": round(daily_sales_estimate, 2),
        "lead_days": product.lead_days,
        "safety_stock": safety_stock,
        "expected_lead_demand": round(lead_demand, 2),
        "reorder_point": reorder_point,
        "target_stock": target_stock,
        "recommended_quantity": max(0, target_stock - product.stock_qty),
        "supplier_id": product.supplier_id,
        "method": "trained daily-sales regression estimate with rule-based reorder policy",
    }