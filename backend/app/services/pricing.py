"""GST and pricing rules.

Confirmed tax treatment from the brief:
    RRP is the SKU price and INCLUDES GST.
    Ex-GST unit price  = RRP / 1.10
    Line subtotal      = Ex-GST unit price x quantity   (ex GST)
    Order subtotal     = sum of line subtotals          (ex GST)
    GST                = order subtotal x 10%
    Order total        = subtotal + GST + shipment fee

All arithmetic uses ``Decimal`` with ``ROUND_HALF_UP`` and is quantised to cents so
that what is displayed on screen always adds up exactly.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

GST_RATE = Decimal("0.10")
GST_MULTIPLIER = Decimal("1.10")  # RRP includes GST => divide to remove it

CENT = Decimal("0.01")


def to_decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def money(value: Decimal | int | float | str | None) -> Decimal:
    """Quantise to cents using commercial rounding."""
    amount = to_decimal(value)
    if amount is None:
        return Decimal("0.00")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def ex_gst_unit_price(rrp_incl_gst: object) -> Optional[Decimal]:
    """Convert a GST-inclusive RRP into an ex-GST unit price."""
    rrp = to_decimal(rrp_incl_gst)
    if rrp is None:
        return None
    return money(rrp / GST_MULTIPLIER)


def line_subtotal(ex_gst_price: Decimal, quantity: int) -> Decimal:
    return money(ex_gst_price * Decimal(quantity))


def order_gst(subtotal_ex_gst: Decimal) -> Decimal:
    return money(subtotal_ex_gst * GST_RATE)


def order_total(subtotal_ex_gst: Decimal, gst: Decimal, shipment_fee: Decimal) -> Decimal:
    return money(subtotal_ex_gst + gst + shipment_fee)


def as_float(value: Decimal) -> float:
    """JSON friendly representation; 2dp floats are exact enough for cent amounts."""
    return float(value.quantize(CENT, rounding=ROUND_HALF_UP))
