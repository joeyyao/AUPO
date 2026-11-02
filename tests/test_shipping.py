"""Shipment-fee estimation (section 7 of the brief)."""

from __future__ import annotations

from app.data_store import store
from app.services.measures import parse_length_mm, parse_mass_g, parse_volume_ml
from app.services.shipping import estimate_order_shipment_fee

RATES = store.shipping_rates()

HERB_10G = {
    "weight": "0.2g",
    "Size": "10",
    "length": "10.0mm",
    "width": "15.0mm",
    "height": "10.0mm",
}
OIL_30ML = {
    "weight": "0.2g",
    "Size": "30",
    "length": "10.0mm",
    "width": "10.0mm",
    "height": "10.0mm",
}

VIC = {"line1": "125 Toorak Road", "suburb": "South Yarra", "state": "VIC", "postcode": "3141"}
NSW = {"line1": "17 Church Street", "suburb": "Parramatta", "state": "NSW", "postcode": "2150"}
WA = {"line1": "5 Hay Street", "suburb": "Perth", "state": "WA", "postcode": "6000"}


def _group(provider: str, lines: list[dict], ref: str = "Track X") -> dict:
    return {
        "tracking_ref": ref,
        "carrier_name": "Test Carrier",
        "provider": provider,
        "lines": lines,
    }


def test_measurement_parsers_handle_the_source_formats():
    assert parse_length_mm("10.0mm") == 10.0
    assert parse_mass_g("0.2g") == 0.2
    assert parse_mass_g("0.2kg") == 200.0
    assert parse_volume_ml("1000.0mm\u00b3") == 1.0
    assert parse_mass_g("garbage") is None


def test_light_parcel_uses_base_fee_plus_interstate_surcharge():
    fee = estimate_order_shipment_fee(
        [_group("auspost", [{"quantity": 1, "product": HERB_10G}])], VIC, RATES
    )
    assert fee["groups"][0]["components"]["base_fee"] == 8.95
    assert fee["groups"][0]["components"]["interstate_surcharge"] == 4.55
    assert fee["total"] == 13.5


def test_same_state_delivery_has_no_interstate_surcharge():
    fee = estimate_order_shipment_fee(
        [_group("auspost", [{"quantity": 1, "product": HERB_10G}])], NSW, RATES
    )
    assert fee["groups"][0]["components"]["interstate_surcharge"] == 0.0
    assert fee["total"] == 8.95


def test_remote_postcode_adds_the_remote_surcharge():
    fee = estimate_order_shipment_fee(
        [_group("auspost", [{"quantity": 1, "product": HERB_10G}])], WA, RATES
    )
    components = fee["groups"][0]["components"]
    assert components["interstate_surcharge"] == 4.55
    assert components["remote_surcharge"] == 6.5
    assert fee["total"] == 20.0


def test_billable_weight_is_the_sum_of_unit_weights_times_quantity():
    fee = estimate_order_shipment_fee(
        [_group("auspost", [{"quantity": 6, "product": OIL_30ML}])], VIC, RATES
    )
    group = fee["groups"][0]
    # (30 g net + 40 g packaging) = 70 g per unit -> 0.42 kg for six units,
    # then lifted to the 0.5 kg minimum billable weight.
    assert group["billable_weight_kg"] == 0.5


def test_heavy_parcels_pay_an_extra_weight_fee():
    heavy = {
        "weight": "2.0kg",
        "Size": "1000",
        "length": "200.0mm",
        "width": "200.0mm",
        "height": "200.0mm",
    }
    fee = estimate_order_shipment_fee(
        [_group("auspost", [{"quantity": 3, "product": heavy}])], NSW, RATES
    )
    group = fee["groups"][0]
    assert group["billable_weight_kg"] > 5.0
    assert group["components"]["extra_weight_fee"] > 0.0


def test_tnt_group_is_zero_but_still_reported():
    fee = estimate_order_shipment_fee(
        [
            _group("tnt", [{"quantity": 2, "product": HERB_10G}], ref="Track 3"),
            _group("auspost", [{"quantity": 1, "product": HERB_10G}], ref="Track 2"),
        ],
        VIC,
        RATES,
    )
    tnt_group = next(g for g in fee["groups"] if g["provider"] == "tnt")
    assert tnt_group["supported"] is False
    assert tnt_group["chargeable"] is False
    assert tnt_group["fee"] == 0.0
    assert "implemented" in tnt_group["reason"].lower()
    assert "bonus" in tnt_group["reason"].lower()

    # order-level fee only counts the chargeable group
    assert fee["total"] == 13.5


def test_order_fee_is_the_sum_of_every_tracking_group():
    """Two AUSPOST consignments in one order are priced separately, then added."""
    fee = estimate_order_shipment_fee(
        [
            _group("auspost", [{"quantity": 1, "product": HERB_10G}], ref="Track 1"),
            _group("auspost", [{"quantity": 2, "product": OIL_30ML}], ref="Track 2"),
        ],
        VIC,
        RATES,
    )
    assert len(fee["groups"]) == 2
    first, second = fee["groups"]
    assert first["fee"] == 13.5
    assert second["fee"] == 13.5
    assert fee["total"] == 27.0


def test_shipment_fee_is_calculated_per_order_not_globally():
    lines_auspost = [_group("auspost", [{"quantity": 1, "product": HERB_10G}])]
    order_a = estimate_order_shipment_fee(lines_auspost, VIC, RATES)
    order_b = estimate_order_shipment_fee(lines_auspost, NSW, RATES)
    assert order_a["total"] != order_b["total"]
    assert order_a["total"] == 13.5
    assert order_b["total"] == 8.95
