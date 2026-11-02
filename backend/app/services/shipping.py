"""Shipment-fee estimation.

The brief allows either a courier pricing API or "a reasonable formula based on
weight and volume". A courier pricing API call needs shipping accounts and parcel
definitions that the supplied testbed does not rate, so this module implements a
deterministic, fully configurable Australia Post eParcel-style estimate.

Formula (every constant comes from ``data/shipping_rates.json``):

    unit net weight      = max(weight field, net content)         [grams]
    unit actual weight   = unit net weight + packaging allowance  [grams]
    unit cubic weight    = length x width x height / 5000         [kg]
    unit billable weight = max(actual, cubic, minimum per unit)   [kg]
    group billable       = sum(unit billable x quantity)
    base fee             covers the first ``included_weight_kg``
    extra weight fee     = ceil(billable - included) x per_extra_kg_aud
    surcharges           = interstate and/or remote postcode
    group fee            = base + extra + surcharges

The ``Size`` column in ``product_list`` is unit-less: for dried herb and oils it is
grams or millilitres, but the catalogue also contains pack sizes well above 1 kg.
Only values inside the configured ``net_content_min_g``/``net_content_max_g`` window
are treated as net content, so a strange value can never inflate the estimate.

The fee is calculated per order: line items are grouped by their assigned tracking
reference, each group is priced, and the order shipment fee is the sum of the
groups. A group with no priceable line (for example every SKU is unmatched) is
reported at A$0.00 instead of inventing a consignment, and couriers that are not
implemented (TNT) also contribute A$0.00 with an explicit reason.

Shipment fees are treated as GST-exclusive amounts: the brief defines
``Total = Subtotal + GST + Shipment Fee`` where GST is 10% of the order subtotal
only, so the courier charge carries no additional GST in this calculation.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Iterable

from . import measures
from .pricing import as_float, money

DEFAULT_UNIT_MIN_WEIGHT_KG = 0.05
ZERO_COMPONENTS = {
    "base_fee": 0.0,
    "extra_weight_fee": 0.0,
    "interstate_surcharge": 0.0,
    "remote_surcharge": 0.0,
}


def _rule(rules: dict[str, Any], name: str, default: float) -> float:
    value = rules.get(name)
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def net_content_g(product: dict[str, Any], rules: dict[str, Any]) -> float:
    """Best-effort net content of one unit, in grams (or millilitres, 1:1).

    ``weight`` is the packaged unit weight recorded in the catalogue and is always
    used. ``Size`` is only added when it looks like a plausible net content for a
    single dispensed unit.
    """
    weight_g = measures.parse_mass_g(product.get("weight")) or 0.0
    size_value = measures.parse_size_g_or_ml(product.get("Size"))

    minimum = _rule(rules, "net_content_min_g", 1.0)
    maximum = _rule(rules, "net_content_max_g", 200.0)
    if size_value is not None and minimum <= size_value <= maximum:
        return max(weight_g, size_value)
    return weight_g


def _unit_billable_weight_kg(product: dict[str, Any], rules: dict[str, Any]) -> float:
    packaging_g = _rule(rules, "packaging_weight_g_per_unit", 40.0)
    divisor = _rule(rules, "cubic_divisor", 5000.0) or 5000.0

    actual_kg = (net_content_g(product, rules) + packaging_g) / 1000.0

    length_mm = measures.parse_length_mm(product.get("length"))
    width_mm = measures.parse_length_mm(product.get("width"))
    height_mm = measures.parse_length_mm(product.get("height"))

    cubic_kg = 0.0
    if length_mm and width_mm and height_mm:
        cubic_kg = (length_mm / 10.0) * (width_mm / 10.0) * (height_mm / 10.0) / divisor

    return max(actual_kg, cubic_kg, DEFAULT_UNIT_MIN_WEIGHT_KG)


def _destination_is_remote(postcode: str, rules: dict[str, Any]) -> bool:
    prefixes = rules.get("remote_postcode_prefixes") or []
    postcode = str(postcode or "").strip()
    if not postcode:
        return False
    return any(postcode.startswith(str(prefix)) for prefix in prefixes)


def _zero_breakdown(breakdown: dict[str, Any], reason: str, supported: bool) -> dict[str, Any]:
    breakdown.update(
        {
            "billable_weight_kg": 0.0,
            "components": dict(ZERO_COMPONENTS),
            "fee": 0.0,
            "chargeable": False,
            "supported": supported,
            "reason": reason,
        }
    )
    return breakdown


def _group_breakdown(
    group: dict[str, Any],
    destination: dict[str, Any],
    origin: dict[str, Any],
    rates: dict[str, Any],
) -> dict[str, Any]:
    rules = rates.get("rules", {})
    provider_rules = (rates.get("provider_rules") or {}).get(group.get("provider", ""), {})
    lines = [line for line in group.get("lines", []) if int(line.get("quantity") or 0) > 0]

    breakdown: dict[str, Any] = {
        "tracking_ref": group.get("tracking_ref"),
        "carrier_name": group.get("carrier_name"),
        "provider": group.get("provider"),
        "currency": rates.get("currency", "AUD"),
        "supported": bool(provider_rules.get("supported", True)),
        "line_count": len(group.get("lines", [])),
        "unit_count": sum(int(line.get("quantity") or 0) for line in group.get("lines", [])),
    }

    if not provider_rules.get("chargeable", True):
        return _zero_breakdown(
            breakdown,
            provider_rules.get("reason", "Shipment fee is not available for this courier."),
            supported=bool(provider_rules.get("supported", False)),
        )

    if not lines:
        # Nothing priceable in this consignment: never invent a shipment fee.
        return _zero_breakdown(
            breakdown,
            "No priceable line items in this consignment (SKU unmatched or quantity invalid).",
            supported=True,
        )

    billable_kg = 0.0
    for line in lines:
        product = line.get("product") or {}
        quantity = int(line.get("quantity") or 0)
        billable_kg += _unit_billable_weight_kg(product, rules) * quantity

    minimum = _rule(rules, "minimum_billable_weight_kg", 0.5)
    billable_kg = max(billable_kg, minimum)

    base_fee = money(_rule(rules, "base_fee_aud", 8.95))
    included = _rule(rules, "included_weight_kg", 5.0)
    per_extra = _rule(rules, "per_extra_kg_aud", 1.10)
    extra_kg = max(0.0, billable_kg - included)
    extra_units = math.ceil(round(extra_kg, 3)) if extra_kg > 0 else 0
    extra_fee = money(per_extra * extra_units)

    interstate = 0.0
    origin_state = str(origin.get("state", "")).strip().upper()
    destination_state = str(destination.get("state", "")).strip().upper()
    if origin_state and destination_state and destination_state != origin_state:
        interstate = _rule(rules, "interstate_surcharge_aud", 0.0)

    remote = 0.0
    if _destination_is_remote(destination.get("postcode", ""), rules):
        remote = _rule(rules, "remote_surcharge_aud", 0.0)

    fee = money(base_fee + extra_fee + money(interstate) + money(remote))

    notes: list[str] = []
    if extra_units:
        notes.append(f"{extra_units} kg over the {included:g} kg included weight")
    if interstate:
        notes.append(
            f"Interstate delivery {origin.get('state', '')} to {destination.get('state', '')}"
        )
    if remote:
        notes.append(f"Remote postcode {destination.get('postcode', '')}")

    breakdown.update(
        {
            "billable_weight_kg": round(billable_kg, 3),
            "components": {
                "base_fee": as_float(base_fee),
                "extra_weight_fee": as_float(extra_fee),
                "interstate_surcharge": as_float(money(interstate)),
                "remote_surcharge": as_float(money(remote)),
            },
            "fee": as_float(fee),
            "chargeable": True,
            "reason": "; ".join(notes) or f"Base fee covers the first {included:g} kg",
        }
    )
    return breakdown


def estimate_order_shipment_fee(
    groups: Iterable[dict[str, Any]],
    destination: dict[str, Any],
    rates: dict[str, Any],
) -> dict[str, Any]:
    """Price every tracking group of one order and total them."""
    origin = rates.get("origin", {})
    group_breakdowns = [_group_breakdown(group, destination, origin, rates) for group in groups]

    total = Decimal("0.00")
    for group in group_breakdowns:
        total += money(group["fee"])

    return {
        "currency": rates.get("currency", "AUD"),
        "method": rates.get("method", "weight_and_volume_formula"),
        "description": rates.get("description", ""),
        "origin": origin,
        "destination": destination,
        "total": as_float(money(total)),
        "gst_treatment": rates.get(
            "gst_treatment", "Shipment fee is treated as GST-exclusive (not taxed twice)."
        ),
        "groups": group_breakdowns,
    }
