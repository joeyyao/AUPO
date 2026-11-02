"""Product catalogue (product_list) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..data_store import store
from ..services.orders import product_public_view

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("")
def list_products(
    search: str | None = Query(None, description="Case-insensitive match on SKU or product name."),
    data_source: str | None = Query(None, description="query_export | generated_placeholder"),
) -> dict:
    rows = store.products()
    views = [product_public_view(row) for row in rows]

    if search:
        needle = search.strip().lower()
        views = [
            view
            for view in views
            if needle in str(view.get("sku", "")).lower()
            or needle in str(view.get("name", "")).lower()
        ]
    if data_source:
        views = [view for view in views if view.get("data_source") == data_source]

    return {"count": len(views), "products": views}


@router.get("/{sku}")
def get_product(sku: str) -> dict:
    needle = sku.strip().lower()
    for row in store.products():
        if str(row.get("SKU", "")).strip().lower() == needle:
            return product_public_view(row)  # type: ignore[return-value]
    raise HTTPException(status_code=404, detail=f"SKU '{sku}' was not found in product_list.")
