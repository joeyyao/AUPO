"""Order assembly against the supplied sample data (sections 2, 4 and 8)."""

from __future__ import annotations

import pytest

from app.data_store import store
from app.services.orders import build_index, build_order


@pytest.fixture(scope="module")
def context():
    products, shipments = build_index(store.products(), store.shipments())
    return products, shipments, store.shipping_rates()


def _order(order_no: str) -> dict:
    for order in store.orders():
        if order["order_no"] == order_no:
            return order
    raise AssertionError(f"missing order {order_no}")


def _build(order_no: str, context) -> dict:
    products, shipments, rates = context
    return build_order(_order(order_no), products, shipments, rates)


def test_supplied_order_1_totals(context):
    detail = _build("PO-20251130-00072", context)
    totals = detail["totals"]
    # 240.00 + 180.00 + 170.00 + 440.00 + 900.00 (all ex GST)
    assert totals["subtotal_ex_gst"] == 1930.00
    assert totals["gst"] == 193.00
    assert totals["shipment_fee"] == 13.50  # base 8.95 + interstate 4.55
    assert totals["total"] == 2136.50
    assert totals["unit_count"] == 15
    assert totals["priced_line_count"] == 5


def test_supplied_order_1_line_prices(context):
    detail = _build("PO-20251130-00072", context)
    by_sku = {line["sku"]: line for line in detail["line_items"]}
    assert by_sku["TBAMET10"]["ex_gst_unit_price"] == 80.00
    assert by_sku["TBAMET10"]["line_subtotal_ex_gst"] == 240.00
    assert by_sku["LELCBD100"]["line_subtotal_ex_gst"] == 900.00
    assert by_sku["HARNIG"]["quantity"] == 4


def test_supplied_order_2_totals_include_tnt_zero_fee(context):
    detail = _build("PO-20251203-00046", context)
    totals = detail["totals"]
    assert totals["subtotal_ex_gst"] == 2510.00
    assert totals["gst"] == 251.00
    assert totals["shipment_fee"] == 13.50  # Track 2 estimate + Track 3 (TNT) at 0.00
    assert totals["total"] == 2774.50

    groups = {group["tracking_ref"]: group for group in detail["shipment_estimate"]["groups"]}
    assert groups["Track 3"]["provider"] == "tnt"
    assert groups["Track 3"]["fee"] == 0.0
    assert groups["Track 3"]["chargeable"] is False


def test_orders_are_computed_independently(context):
    first = _build("PO-20251130-00072", context)
    second = _build("PO-20251203-00046", context)
    assert first["totals"]["subtotal_ex_gst"] != second["totals"]["subtotal_ex_gst"]
    assert first["customer"]["name"] == "Jason Hu"
    assert second["customer"]["name"] == "Bella Dari"


def test_missing_sku_is_reported_and_excluded_from_totals(context):
    detail = _build("PO-20251205-00088", context)
    unmatched = [line for line in detail["line_items"] if not line["valid"]]
    assert len(unmatched) == 1
    assert unmatched[0]["sku"] == "SKU-NOT-IN-CATALOGUE"
    assert unmatched[0]["product"] is None
    assert "not found" in unmatched[0]["issues"][0].lower()

    assert detail["totals"]["subtotal_ex_gst"] == 488.18  # valid lines only
    assert detail["totals"]["priced_line_count"] == 2
    assert any("SKU-NOT-IN-CATALOGUE" in warning for warning in detail["warnings"])


def test_invalid_quantities_are_rejected_per_line(context):
    detail = _build("PO-20251208-00091", context)
    invalid = [line for line in detail["line_items"] if not line["valid"]]
    assert {line["sku"] for line in invalid} == {"GROOGKU10", "GROSTRC10"}
    assert all("positive whole number" in line["issues"][0] for line in invalid)

    valid = [line for line in detail["line_items"] if line["valid"]]
    assert len(valid) == 1
    assert detail["totals"]["subtotal_ex_gst"] == 90.00
    assert detail["totals"]["total"] == 112.50


def test_unavailable_courier_order_has_zero_shipment_fee(context):
    detail = _build("PO-20251210-00095", context)
    assert detail["totals"]["shipment_fee"] == 0.0
    assert detail["totals"]["subtotal_ex_gst"] == 913.63
    assert detail["totals"]["gst"] == 91.36
    assert detail["totals"]["total"] == 1004.99


def test_display_date_is_converted_to_australian_format(context):
    detail = _build("PO-20251130-00072", context)
    assert detail["order_date_display"] == "30/11/2025"


def test_business_logic_does_not_depend_on_specific_skus(context):
    """A brand new order built from catalogue SKUs must price correctly with no code change."""
    products, shipments, rates = context
    synthetic = {
        "order_no": "PO-99999999-TEST",
        "order_date": "2026-01-15",
        "status": "Pending",
        "company": "Any Pharmacy",
        "customer": {"name": "Test", "phone": "0", "email": "t@example.com"},
        "shipping_address": {"line1": "1 Test St", "suburb": "Ryde", "state": "NSW", "postcode": "2111"},
        "items": [{"sku": "FLW0012", "quantity": 2, "tracking_ref": "Track 1"}],
    }
    detail = build_order(synthetic, products, shipments, rates)
    assert detail["totals"]["priced_line_count"] == 1
    assert detail["totals"]["subtotal_ex_gst"] == 234.54  # 117.27 x 2
