"""Health / diagnostics endpoint.

Exposes only configuration *state* (configured / not configured), never the
credential values, so it is safe to call from the browser.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..data_store import DataFileError, store

router = APIRouter(prefix="/api", tags=["meta"])


def _file_status(name: str, loader) -> dict:
    try:
        payload = loader()
        size = len(payload) if isinstance(payload, (list, dict)) else None
        return {"file": name, "ok": True, "items": size}
    except DataFileError as exc:
        return {"file": name, "ok": False, "error": str(exc)}


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.env,
        "data_files": [
            _file_status("orders.json", store.orders),
            _file_status("products.json", store.products),
            _file_status("shipments.json", store.shipments),
            _file_status("shipping_rates.json", store.shipping_rates),
        ],
        "couriers": {
            "auspost": {
                "implemented": True,
                "live_tracking_enabled": settings.enable_live_tracking,
                "credentials_configured": settings.auspost_configured,
                "endpoint": f"{settings.auspost_api_base}/track",
            },
            "tnt": {
                "implemented": False,
                "reason": "Optional bonus work in the assessment brief; not implemented.",
            },
        },
        "shipping": {
            "origin_postcode": settings.shipping_origin_postcode,
            "method": "weight_and_volume_formula",
        },
    }
