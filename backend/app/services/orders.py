"""Order assembly: joins orders + product_list + shipments and computes money.

Everything here is data driven: order numbers, SKUs, quantities, prices and
courier assignments all come from the JSON files. No business value is hard-coded,
so the same code path handles the supplied sample orders, the additional test
orders and any future real order that follows the documented input structure.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from . import pricing
from .measures import parse_length_mm, parse_mass_g, parse_size_g_or_ml, parse_volume_ml
from .shipping import estimate_order_shipment_fee


def format_display_date(raw: str | None) -> str:
    """ISO ``2025-11-30`` (or ``30/11/25``) -> ``30/11/2025``."""
    if not raw:
        return ""
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%y", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        return parsed.strftime("%d/%m/%Y")
    return text


def normalise_ref(raw: Any) -> str | None:
    """Canonical tracking reference as displayed to the user (whitespace trimmed)."""
    text = str(raw or "").strip()
    return text or None


def ref_key(raw: Any) -> str:
    """Matching key for a tracking reference: trimmed and case-folded.

    Consignments are grouped, priced and looked up by this key so ``"Track 1 "``,
    ``"track 1"`` and ``"Track 1"`` always resolve to one consignment instead of
    being billed as separate parcels.
    """
    return str(raw or "").strip().casefold()


def _coerce_quantity(raw: Any) -> tuple[int | None, str | None]:
    """Return ``(quantity, issue)``.

    Real feeds send quantities as ints, floats or numeric strings; anything that is
    not a positive whole number is rejected on that line only, so a single bad row
    can never break the rest of the order.
    """
    if raw is None or raw == "":
        return None, "Quantity is missing."
    if isinstance(raw, bool):
        return None, f"Quantity '{raw}' is not a whole number."
    try:
        number = float(str(raw).strip())
    except (TypeError, ValueError):
        return None, f"Quantity '{raw}' is not a number."
    if number != int(number):
        return None, f"Quantity '{raw}' is not a whole number."
    quantity = int(number)
    if quantity <= 0:
        return None, f"Quantity {quantity} is not a positive whole number."
    return quantity, None


def product_public_view(product: dict[str, Any] | None) -> dict[str, Any] | None:
    if not product:
        return None
    return {
        "sku": product.get("SKU"),
        "name": product.get("ProductName"),
        "description": (product.get("Description") or "").strip(),
        "dosage_type": (product.get("DosageType") or "").strip(),
        "product_type": product.get("ProductType"),
        "size": product.get("Size"),
        "schedule": product.get("Schedule"),
        "tga_category": product.get("TGACategory"),
        "plant_species": product.get("PlantSpecies"),
        "spectrum": product.get("Spectrum"),
        "max_storage_per_container": product.get("MaxStoragePerContainer"),
        "status": product.get("Status"),
        "dimensions": {
            "length_mm": parse_length_mm(product.get("length")),
            "width_mm": parse_length_mm(product.get("width")),
            "height_mm": parse_length_mm(product.get("height")),
            "volume_ml": parse_volume_ml(product.get("volume")),
        },
        "weight_g": parse_mass_g(product.get("weight")),
        "size_value": parse_size_g_or_ml(product.get("Size")),
        "data_source": product.get("data_source", "query_export"),
    }


def _build_tracking_groups(
    line_items: list[dict[str, Any]],
    shipments_by_ref: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    group_order: list[str] = []

    for item in line_items:
        ref = item.get("tracking_ref")
        key = ref_key(ref)
        group = groups.get(key)
        if group is None:
            shipment = shipments_by_ref.get(key, {})
            group = {
                "tracking_ref": ref,
                "tracking_no": shipment.get("tracking_no"),
                "carrier_name": shipment.get("carrier_name"),
                "provider": shipment.get("provider"),
                "test_data": bool(shipment.get("test_data", False)),
                "known": bool(shipment),
                "skus": [],
                "unit_count": 0,
                "line_count": 0,
            }
            groups[key] = group
            group_order.append(key)
        group["line_count"] += 1
        group["skus"].append(item.get("sku"))
        if item.get("valid"):
            group["unit_count"] += int(item.get("quantity") or 0)

    return [groups[key] for key in group_order]


def build_order(
    order: dict[str, Any],
    products_by_sku: dict[str, dict[str, Any]],
    shipments_by_ref: dict[str, dict[str, Any]],
    rates: dict[str, Any],
    *,
    include_tracking_groups: bool = True,
) -> dict[str, Any]:
    raw_items = order.get("items") or []
    warnings: list[str] = []
    line_items: list[dict[str, Any]] = []
    subtotal = Decimal("0.00")
    priced_line_count = 0
    total_units = 0

    for index, item in enumerate(raw_items, start=1):
        sku = str(item.get("sku") or "").strip()
        tracking_ref = normalise_ref(item.get("tracking_ref"))
        quantity, quantity_issue = _coerce_quantity(item.get("quantity"))
        product = products_by_sku.get(sku.upper()) if sku else None

        issues: list[str] = []
        if not sku:
            issues.append("Line item has no SKU.")
        if quantity_issue:
            issues.append(quantity_issue)
        if sku and product is None:
            issues.append(f"SKU '{sku}' was not found in product_list.")

        rrp = pricing.to_decimal(product.get("RRP")) if product else None
        if product is not None and rrp is None:
            issues.append(f"SKU '{sku}' has no usable RRP in product_list.")

        ex_unit = pricing.ex_gst_unit_price(rrp) if rrp is not None else None
        line_total = (
            pricing.line_subtotal(ex_unit, quantity) if ex_unit is not None and quantity else None
        )

        valid = not issues and ex_unit is not None and quantity is not None
        if valid:
            subtotal += line_total  # type: ignore[operator]
            priced_line_count += 1
            total_units += quantity  # type: ignore[operator]
        else:
            warnings.extend(f"Line {index} ({sku or 'no SKU'}): {issue}" for issue in issues)

        line_items.append(
            {
                "line_no": index,
                "sku": sku,
                "tracking_ref": tracking_ref,
                "quantity": quantity if quantity is not None else item.get("quantity"),
                "valid": valid,
                "issues": issues,
                "product": product_public_view(product),
                "rrp_incl_gst": pricing.as_float(rrp) if rrp is not None else None,
                "ex_gst_unit_price": pricing.as_float(ex_unit) if ex_unit is not None else None,
                "line_subtotal_ex_gst": (
                    pricing.as_float(line_total) if line_total is not None else None
                ),
            }
        )

    destination = order.get("shipping_address") or {}
    groups = _build_tracking_groups(line_items, shipments_by_ref)

    priced_groups = [
        {
            "tracking_ref": group["tracking_ref"],
            "carrier_name": group["carrier_name"],
            "provider": group["provider"],
            "lines": [
                {
                    "quantity": item["quantity"] or 0,
                    # raw product record: the shipping service parses weight/dimensions itself
                    "product": products_by_sku.get(str(item["sku"]).upper(), {}),
                }
                for item in line_items
                if item["valid"] and ref_key(item["tracking_ref"]) == ref_key(group["tracking_ref"])
            ],
        }
        for group in groups
    ]

    shipment = estimate_order_shipment_fee(priced_groups, destination, rates)
    shipment_fee = pricing.money(shipment["total"])

    subtotal = pricing.money(subtotal)
    gst = pricing.order_gst(subtotal)
    total = pricing.order_total(subtotal, gst, shipment_fee)

    for group in groups:
        if not group["known"]:
            warnings.append(
                f"Tracking reference '{group['tracking_ref'] or 'unassigned'}' has no shipment record."
            )

    if not raw_items:
        warnings.append("This order has no line items.")

    payload: dict[str, Any] = {
        "order_no": order.get("order_no"),
        "order_date": order.get("order_date"),
        "order_date_display": format_display_date(order.get("order_date")),
        "status": order.get("status"),
        "company": order.get("company"),
        "customer": order.get("customer") or {},
        "shipping_address": destination,
        "test_order_purpose": order.get("test_order_purpose"),
        "line_items": line_items,
        "totals": {
            "currency": "AUD",
            "subtotal_ex_gst": pricing.as_float(subtotal),
            "gst": pricing.as_float(gst),
            "gst_rate": float(pricing.GST_RATE),
            "shipment_fee": pricing.as_float(shipment_fee),
            "total": pricing.as_float(total),
            "unit_count": total_units,
            "line_count": len(line_items),
            "priced_line_count": priced_line_count,
        },
        "shipment_estimate": shipment,
        "warnings": warnings,
        "counts": {
            "lines": len(line_items),
            "invalid_lines": len(line_items) - priced_line_count,
            "units": total_units,
        },
    }
    if include_tracking_groups:
        payload["tracking_groups"] = groups
    return payload


def build_order_list_item(order: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "order_no": detail["order_no"],
        "order_date": detail["order_date"],
        "order_date_display": detail["order_date_display"],
        "status": detail["status"],
        "company": detail["company"],
        "customer_name": (order.get("customer") or {}).get("name"),
        "suburb": (order.get("shipping_address") or {}).get("suburb"),
        "state": (order.get("shipping_address") or {}).get("state"),
        "postcode": (order.get("shipping_address") or {}).get("postcode"),
        "totals": detail["totals"],
        "warning_count": len(detail["warnings"]),
        "tracking_refs": [group["tracking_ref"] for group in detail.get("tracking_groups", [])],
    }


def build_index(
    products: list[dict[str, Any]], shipments: list[dict[str, Any]]
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    products_by_sku = {
        str(product.get("SKU", "")).strip().upper(): product
        for product in products
        if str(product.get("SKU", "")).strip()
    }
    shipments_by_ref = {
        ref_key(shipment.get("tracking_ref")): shipment
        for shipment in shipments
        if ref_key(shipment.get("tracking_ref"))
    }
    return products_by_sku, shipments_by_ref
