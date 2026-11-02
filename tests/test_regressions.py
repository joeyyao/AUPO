"""Regression tests for issues found during code review.

Covered here:
  * a consignment whose lines are all invalid must never be charged a base fee
  * tracking references are normalised so pricing and grouping always agree
  * a `Size` value from the real catalogue that is not a plausible unit net content
    must not inflate the shipment-fee estimate
"""

from __future__ import annotations

from app.data_store import store
from app.services.orders import build_index, build_order, normalise_ref
from app.services.shipping import estimate_order_shipment_fee, net_content_g

RATES = store.shipping_rates()

VIC = {"line1": "125 Toorak Road", "suburb": "South Yarra", "state": "VIC", "postcode": "3141"}


def _synthetic_order(items: list[dict]) -> dict:
    return {
        "order_no": "PO-TEST-0001",
        "order_date": "2026-01-05",
        "status": "Pending",
        "company": "Test Pharmacy",
        "customer": {"name": "Test Patient", "phone": "0400 000 000", "email": "t@example.com"},
        "shipping_address": VIC,
        "items": items,
    }


def test_order_with_only_invalid_lines_has_no_shipment_fee():
    products, shipments = build_index(store.products(), store.shipments())
    detail = build_order(
        _synthetic_order(
            [
                {"sku": "DOES-NOT-EXIST", "quantity": 2, "tracking_ref": "Track 1"},
                {"sku": "GROOGKU10", "quantity": 0, "tracking_ref": "Track 1"},
            ]
        ),
        products,
        shipments,
        RATES,
    )

    assert detail["totals"]["subtotal_ex_gst"] == 0.0
    assert detail["totals"]["gst"] == 0.0
    assert detail["totals"]["shipment_fee"] == 0.0
    assert detail["totals"]["total"] == 0.0
    # the consignment is still visible so the UI can explain why nothing is priced
    group = detail["shipment_estimate"]["groups"][0]
    assert group["fee"] == 0.0
    assert group["chargeable"] is False
    assert "no priceable line items" in group["reason"].lower()


def test_shipment_fee_never_charged_for_empty_group():
    fee = estimate_order_shipment_fee(
        [
            {
                "tracking_ref": "Track 1",
                "carrier_name": "Australia Post",
                "provider": "auspost",
                "lines": [],
            }
        ],
        VIC,
        RATES,
    )
    assert fee["total"] == 0.0
    assert fee["groups"][0]["fee"] == 0.0


def test_tracking_reference_is_normalised_once():
    assert normalise_ref("  Track 1  ") == "Track 1"
    assert normalise_ref(None) is None
    assert normalise_ref("   ") is None

    products, shipments = build_index(store.products(), store.shipments())
    detail = build_order(
        _synthetic_order([{"sku": "FLW0012", "quantity": 1, "tracking_ref": "  Track 1 "}]),
        products,
        shipments,
        RATES,
    )
    line = detail["line_items"][0]
    group = detail["tracking_groups"][0]
    assert line["tracking_ref"] == "Track 1"
    assert group["tracking_ref"] == "Track 1"
    assert group["known"] is True
    # the priced group must contain the line, so the weight is actually billed
    assert detail["shipment_estimate"]["groups"][0]["unit_count"] == 1
    assert detail["shipment_estimate"]["groups"][0]["fee"] > 0.0


def test_unrealistic_size_value_is_not_treated_as_net_content_weight():
    """The real catalogue contains Size values such as 1350 for multi-unit packs."""
    pastille = next(row for row in store.products() if row["SKU"] == "WL-PAS-ZSMPIN-30-30-1")
    assert float(pastille["Size"]) > 200

    # only the packaged unit weight counts, not the 1350 "Size"
    assert net_content_g(pastille, RATES["rules"]) < 1.0

    fee = estimate_order_shipment_fee(
        [
            {
                "tracking_ref": "Track 1",
                "carrier_name": "Australia Post",
                "provider": "auspost",
                "lines": [{"quantity": 1, "product": pastille}],
            }
        ],
        VIC,
        RATES,
    )
    assert fee["groups"][0]["billable_weight_kg"] <= 0.5
    assert fee["total"] == 13.5  # base fee + interstate surcharge only


def test_real_catalogue_row_still_prices_a_normal_parcel():
    herb = next(row for row in store.products() if row["SKU"] == "NUBKIKP10")
    assert net_content_g(herb, RATES["rules"]) == 10.0  # 10 g flower inside a 40 g pack
    fee = estimate_order_shipment_fee(
        [
            {
                "tracking_ref": "Track 1",
                "carrier_name": "Australia Post",
                "provider": "auspost",
                "lines": [{"quantity": 6, "product": herb}],
            }
        ],
        {"line1": "1 Test", "suburb": "Ryde", "state": "NSW", "postcode": "2111"},
        RATES,
    )
    # 6 x 50 g = 0.3 kg -> minimum billable 0.5 kg, same-state so base fee only
    assert fee["groups"][0]["billable_weight_kg"] == 0.5
    assert fee["total"] == 8.95


def test_shipment_estimate_documents_its_gst_treatment():
    fee = estimate_order_shipment_fee([], VIC, RATES)
    assert "gst" in fee["gst_treatment"].lower()


def test_reference_casing_and_spacing_do_not_split_a_consignment():
    products, shipments = build_index(store.products(), store.shipments())
    detail = build_order(
        _synthetic_order(
            [
                {"sku": "FLW0012", "quantity": 1, "tracking_ref": "Track 1"},
                {"sku": "FLW0013", "quantity": 2, "tracking_ref": " track 1 "},
            ]
        ),
        products,
        shipments,
        RATES,
    )
    assert len(detail["tracking_groups"]) == 1
    group = detail["shipment_estimate"]["groups"][0]
    assert group["unit_count"] == 3
    assert group["line_count"] == 2
    # one consignment == one base fee, not two
    assert detail["totals"]["shipment_fee"] == 13.5


def test_missing_destination_state_does_not_trigger_interstate_surcharge():
    herb = {"weight": "0.2g", "Size": "10", "length": "10.0mm", "width": "15.0mm", "height": "10.0mm"}
    fee = estimate_order_shipment_fee(
        [
            {
                "tracking_ref": "Track 1",
                "carrier_name": "Australia Post",
                "provider": "auspost",
                "lines": [{"quantity": 1, "product": herb}],
            }
        ],
        {"line1": "1 Test", "suburb": "", "state": "", "postcode": "2000"},
        RATES,
    )
    assert fee["groups"][0]["components"]["interstate_surcharge"] == 0.0
