"""Courier tracking.

Design rules taken from the brief:
  * Use the appropriate courier service for each tracking number where practical.
  * Show the current status and last update when the API returns them.
  * Never break the application when an API is missing, invalid or unavailable.
  * Never fabricate a live tracking event: report an explicit unavailable /
    not-implemented state and explain the limitation in the README.

Australia Post / StarTrack is integrated against the supplied testbed. TNT is
deliberately *not* implemented (optional bonus work) and always answers with a
``not_implemented`` state, so the UI can show an honest placeholder.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx

from ..config import settings


# ---------------------------------------------------------------------------
# status normalisation
# ---------------------------------------------------------------------------
_TERMINAL_WORDS = ("delivered", "collected")
_IN_TRANSIT_WORDS = (
    "in transit",
    "transit",
    "processed",
    "onboard for delivery",
    "out for delivery",
    "received by",
    "shipping information",
    "arrived",
    "sorted",
    "awaiting",
)


def normalise_status(raw_status: str | None, events: Iterable[dict[str, Any]]) -> str:
    """Map a courier's wording onto a small UI vocabulary."""
    text = (raw_status or "").strip().lower()
    if any(word in text for word in _TERMINAL_WORDS):
        return "delivered"
    if "awaiting collection" in text:
        return "awaiting_collection"
    if any(word in text for word in _IN_TRANSIT_WORDS):
        return "in_transit"
    if not text:
        newest = next(iter(events), None)
        if newest:
            return normalise_status(newest.get("description"), [])
        return "unknown"
    return "in_transit"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = asyncio.Lock()


async def _cache_get(key: str) -> dict[str, Any] | None:
    async with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        expires_at, payload = entry
        if expires_at < time.monotonic():
            _CACHE.pop(key, None)
            return None
        return {**payload, "cached": True}


async def _cache_put(key: str, payload: dict[str, Any]) -> None:
    async with _CACHE_LOCK:
        _CACHE[key] = (time.monotonic() + settings.tracking_cache_seconds, payload)


def clear_cache() -> None:
    _CACHE.clear()


# ---------------------------------------------------------------------------
# result shapes
# ---------------------------------------------------------------------------
def _base_result(shipment: dict[str, Any]) -> dict[str, Any]:
    return {
        "tracking_ref": shipment.get("tracking_ref"),
        "tracking_no": shipment.get("tracking_no"),
        "carrier_name": shipment.get("carrier_name"),
        "provider": shipment.get("provider"),
        "test_data": bool(shipment.get("test_data", False)),
        "state": "unavailable",
        "status": None,
        "status_code": "unknown",
        "last_update": None,
        "events": [],
        "articles": [],
        "cached": False,
        "fetched_at": _utc_now_iso(),
        "http_status": None,
        "message": "",
    }


def _unavailable(shipment: dict[str, Any], message: str, state: str = "unavailable", **extra: Any) -> dict[str, Any]:
    result = _base_result(shipment)
    result.update({"state": state, "status_code": "unavailable", "message": message})
    result.update(extra)
    return result


# ---------------------------------------------------------------------------
# Australia Post / StarTrack
# ---------------------------------------------------------------------------
def _parse_auspost(shipment: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    result = _base_result(shipment)
    tracking_no = str(shipment.get("tracking_no", ""))
    results = payload.get("tracking_results") or []
    match = next(
        (item for item in results if str(item.get("tracking_id", "")) == tracking_no),
        results[0] if results else None,
    )

    if not match:
        message = "Australia Post returned no tracking record for this number."
        errors = payload.get("errors")
        if errors:
            message = "; ".join(str(err.get("message", err)) for err in errors)
        return _unavailable(shipment, message, state="unavailable")

    consignment = match.get("consignment") or {}
    articles = match.get("trackable_items") or []

    events: list[dict[str, Any]] = []
    for event in consignment.get("events") or []:
        events.append(
            {
                "description": event.get("description"),
                "location": event.get("location") or "",
                "date": event.get("date"),
                "article_id": None,
            }
        )
    if not events:
        for article in articles:
            for event in article.get("events") or []:
                events.append(
                    {
                        "description": event.get("description"),
                        "location": event.get("location") or "",
                        "date": event.get("date"),
                        "article_id": article.get("article_id"),
                    }
                )

    events.sort(key=lambda item: item.get("date") or "", reverse=True)
    deduped: list[dict[str, Any]] = []
    seen = set()
    for event in events:
        key = (event.get("description"), event.get("date"), event.get("location"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)

    raw_status = match.get("status") or consignment.get("status")
    status_code = normalise_status(raw_status, deduped)

    result.update(
        {
            "state": "available",
            "status": raw_status,
            "status_code": status_code,
            "last_update": deduped[0] if deduped else None,
            "events": deduped,
            "articles": [
                {
                    "article_id": article.get("article_id"),
                    "product_type": article.get("product_type"),
                    "status": article.get("status"),
                    "event_count": len(article.get("events") or []),
                }
                for article in articles
            ],
            "message": "Live Australia Post testbed response.",
        }
    )
    return result


async def _fetch_auspost(shipment: dict[str, Any]) -> dict[str, Any]:
    if not settings.enable_live_tracking:
        return _unavailable(
            shipment,
            "Live tracking is disabled (ENABLE_LIVE_TRACKING=false).",
        )
    if not settings.auspost_configured:
        return _unavailable(
            shipment,
            "Australia Post credentials are not configured. Set AUSPOST_API_KEY and "
            "AUSPOST_API_PASSWORD in .env (see .env.example).",
        )

    tracking_no = str(shipment.get("tracking_no", "")).strip()
    if not tracking_no:
        return _unavailable(shipment, "This shipment has no tracking number.")

    url = f"{settings.auspost_api_base}/track"
    try:
        async with httpx.AsyncClient(timeout=settings.tracking_timeout_seconds) as client:
            response = await client.get(
                url,
                params={"tracking_ids": tracking_no},
                auth=(settings.auspost_api_key, settings.auspost_api_password),
                headers={"Accept": "application/json"},
            )
    except httpx.TimeoutException:
        return _unavailable(
            shipment,
            f"Australia Post API timed out after {settings.tracking_timeout_seconds:g}s.",
            state="error",
        )
    except httpx.HTTPError as exc:
        return _unavailable(shipment, f"Australia Post API request failed: {exc}", state="error")

    if response.status_code == 401:
        return _unavailable(
            shipment,
            "Australia Post rejected the credentials (HTTP 401). The assessment brief warns "
            "that the testbed currently has permission issues.",
            state="unavailable",
            http_status=401,
        )
    if response.status_code >= 400:
        detail = ""
        try:
            payload = response.json()
            errors = payload.get("errors") or []
            detail = "; ".join(
                str(err.get("message") or err.get("name") or err) for err in errors
            )
        except ValueError:
            detail = (response.text or "")[:180]
        return _unavailable(
            shipment,
            f"Australia Post API returned HTTP {response.status_code}. {detail}".strip(),
            state="error",
            http_status=response.status_code,
        )

    try:
        payload = response.json()
    except ValueError:
        return _unavailable(
            shipment,
            "Australia Post API returned a response that was not valid JSON.",
            state="error",
            http_status=response.status_code,
        )

    result = _parse_auspost(shipment, payload)
    result["http_status"] = response.status_code
    return result


# ---------------------------------------------------------------------------
# TNT (not implemented - optional bonus work)
# ---------------------------------------------------------------------------
async def _fetch_tnt(shipment: dict[str, Any]) -> dict[str, Any]:
    return _unavailable(
        shipment,
        "TNT integration was not implemented (optional bonus work in the brief). "
        "Research scope was TNT Rated Transit Times (RTT) for pricing and Consignment "
        "tracking for events; both require XML/Secured Weblinking setup against a live "
        "TNT UAT account, which is out of scope for this submission. The related "
        "shipment fee is therefore shown as A$0.00.",
        state="not_implemented",
    )


_PROVIDERS = {
    "auspost": _fetch_auspost,
    "tnt": _fetch_tnt,
}


async def fetch_tracking(shipment: dict[str, Any]) -> dict[str, Any]:
    """Resolve one shipment, using the cache when possible. Never raises."""
    cache_key = f"{shipment.get('provider')}:{shipment.get('tracking_no')}"
    cached = await _cache_get(cache_key)
    if cached:
        return cached

    provider = str(shipment.get("provider", "")).lower()
    handler = _PROVIDERS.get(provider)
    if handler is None:
        result = _unavailable(
            shipment,
            f"No tracking integration is available for provider '{provider}'.",
            state="not_implemented",
        )
    else:
        try:
            result = await handler(shipment)
        except Exception as exc:  # pragma: no cover - last-resort guard
            result = _unavailable(
                shipment,
                f"Unexpected error while resolving tracking: {exc}",
                state="error",
            )

    if result.get("state") == "available":
        await _cache_put(cache_key, result)
    return result


async def fetch_many(shipments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for shipment in shipments:
        key = f"{shipment.get('provider')}:{shipment.get('tracking_no')}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(shipment)
    return list(await asyncio.gather(*(fetch_tracking(item) for item in unique)))
