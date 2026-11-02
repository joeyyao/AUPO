"""HTTP API contract tests.

Tracking tests run with live calls disabled so the suite never depends on the
network; a separate opt-in test exercises the real Australia Post testbed
(``RUN_LIVE_TRACKING_TEST=1 pytest tests/test_api.py``).
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import tracking

client = TestClient(app)


@pytest.fixture()
def offline_tracking(monkeypatch):
    monkeypatch.setattr(settings, "enable_live_tracking", False)
    tracking.clear_cache()


def test_health_reports_data_files_and_courier_state():
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert all(item["ok"] for item in payload["data_files"])
    assert payload["couriers"]["auspost"]["implemented"] is True
    assert payload["couriers"]["tnt"]["implemented"] is False
    # credentials must never be echoed back
    assert "AUSPOST_API_KEY" not in response.text
    if settings.auspost_api_key:
        assert settings.auspost_api_key not in response.text


def test_order_list_matches_the_supplied_orders():
    response = client.get("/api/orders")
    assert response.status_code == 200
    payload = response.json()
    order_numbers = [order["order_no"] for order in payload["orders"]]
    assert "PO-20251130-00072" in order_numbers
    assert "PO-20251203-00046" in order_numbers
    assert payload["count"] == len(payload["orders"])


def test_order_detail_returns_line_items_and_totals():
    response = client.get("/api/orders/PO-20251130-00072")
    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"]["subtotal_ex_gst"] == 1930.00
    assert payload["totals"]["gst"] == 193.00
    assert payload["totals"]["shipment_fee"] == 13.50
    assert payload["totals"]["total"] == 2136.50

    first = payload["line_items"][0]
    for field in ("sku", "quantity", "rrp_incl_gst", "ex_gst_unit_price", "line_subtotal_ex_gst"):
        assert first[field] is not None
    assert first["product"]["name"]


def test_unknown_order_returns_404():
    response = client.get("/api/orders/DOES-NOT-EXIST")
    assert response.status_code == 404


def test_products_endpoint_is_searchable():
    response = client.get("/api/products", params={"search": "TBAMET"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] >= 1
    assert all("TBAMET" in product["sku"] for product in payload["products"])


def test_unknown_sku_returns_404():
    assert client.get("/api/products/NO-SUCH-SKU").status_code == 404


def test_tracking_reports_unavailable_state_without_live_calls(offline_tracking):
    response = client.get("/api/orders/PO-20251130-00072/tracking")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total"] == 1
    shipment = payload["shipments"][0]
    assert shipment["state"] == "unavailable"
    assert shipment["message"]
    assert shipment["events"] == []


def test_tnt_tracking_is_explicitly_not_implemented():
    tracking.clear_cache()
    response = client.get("/api/orders/PO-20251203-00046/tracking")
    assert response.status_code == 200
    shipments = {item["tracking_ref"]: item for item in response.json()["shipments"]}
    tnt = shipments["Track 3"]
    assert tnt["state"] == "not_implemented"
    assert tnt["provider"] == "tnt"
    assert "TNT" in tnt["message"]


def test_unknown_api_route_returns_json_404():
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404


@pytest.mark.skipif(
    os.getenv("RUN_LIVE_TRACKING_TEST") != "1",
    reason="set RUN_LIVE_TRACKING_TEST=1 to call the Australia Post testbed",
)
def test_live_auspost_tracking(monkeypatch):
    monkeypatch.setattr(settings, "enable_live_tracking", True)
    tracking.clear_cache()
    response = client.get("/api/orders/PO-20251130-00072/tracking", params={"refresh": True})
    assert response.status_code == 200
    shipment = response.json()["shipments"][0]
    assert shipment["state"] in {"available", "unavailable"}
    if shipment["state"] == "available":
        assert shipment["status"]
        assert shipment["last_update"]["date"]
