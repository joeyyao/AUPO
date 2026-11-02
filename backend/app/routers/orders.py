"""Order endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..data_store import store
from ..services import tracking
from ..services.orders import build_index, build_order, build_order_list_item

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _context():
    products_by_sku, shipments_by_ref = build_index(store.products(), store.shipments())
    rates = store.shipping_rates()
    return products_by_sku, shipments_by_ref, rates


def _find_order(order_no: str) -> dict:
    for order in store.orders():
        if str(order.get("order_no", "")).strip().lower() == order_no.strip().lower():
            return order
    raise HTTPException(status_code=404, detail=f"Order '{order_no}' was not found.")


def _detail(order: dict):
    products_by_sku, shipments_by_ref, rates = _context()
    return build_order(order, products_by_sku, shipments_by_ref, rates)


@router.get("")
def list_orders() -> dict:
    """Order list with totals; tracking is deliberately excluded so the page is fast."""
    products_by_sku, shipments_by_ref, rates = _context()
    items = []
    for order in store.orders():
        detail = build_order(order, products_by_sku, shipments_by_ref, rates)
        items.append(build_order_list_item(order, detail))
    return {"count": len(items), "orders": items}


@router.get("/{order_no}")
def get_order(order_no: str) -> dict:
    """Full order detail: line items, GST breakdown, shipment estimate and warnings."""
    return _detail(_find_order(order_no))


@router.get("/{order_no}/tracking")
async def get_order_tracking(
    order_no: str,
    refresh: bool = Query(False, description="Ignore the in-memory cache and re-query couriers."),
) -> dict:
    """Live courier status for every tracking reference attached to the order."""
    if refresh:
        tracking.clear_cache()

    order = _find_order(order_no)
    detail = _detail(order)
    groups = detail.get("tracking_groups", [])

    shipments = [
        {
            "tracking_ref": group["tracking_ref"],
            "tracking_no": group["tracking_no"],
            "carrier_name": group["carrier_name"],
            "provider": group["provider"],
            "test_data": group["test_data"],
        }
        for group in groups
    ]

    results = await tracking.fetch_many(shipments)
    by_ref = {result.get("tracking_ref"): result for result in results}

    merged = []
    for group in groups:
        result = by_ref.get(group["tracking_ref"]) or {
            "tracking_ref": group["tracking_ref"],
            "tracking_no": group["tracking_no"],
            "carrier_name": group["carrier_name"],
            "provider": group["provider"],
            "test_data": group["test_data"],
            "state": "unavailable",
            "status": None,
            "status_code": "unavailable",
            "last_update": None,
            "events": [],
            "articles": [],
            "cached": False,
            "http_status": None,
            "message": "No tracking record is configured for this reference.",
        }
        merged.append(
            {
                **result,
                "skus": group["skus"],
                "unit_count": group["unit_count"],
                "line_count": group["line_count"],
            }
        )

    available = [item for item in merged if item.get("state") == "available"]
    return {
        "order_no": detail["order_no"],
        "checked_at": merged[0]["fetched_at"] if merged else None,
        "summary": {
            "total": len(merged),
            "available": len(available),
            "unavailable": len(merged) - len(available),
        },
        "shipments": merged,
    }
