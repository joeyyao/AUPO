"""Money and GST rules from section 4 of the brief."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services import pricing


def test_ex_gst_unit_price_removes_the_10_percent_gst():
    assert pricing.ex_gst_unit_price("88.00") == Decimal("80.00")
    assert pricing.ex_gst_unit_price("121.00") == Decimal("110.00")
    assert pricing.ex_gst_unit_price("198.00") == Decimal("180.00")


def test_ex_gst_unit_price_rounds_half_up_to_cents():
    # 120 / 1.10 = 109.0909... and 129 / 1.10 = 117.2727...
    assert pricing.ex_gst_unit_price("120.00") == Decimal("109.09")
    assert pricing.ex_gst_unit_price("129.00") == Decimal("117.27")
    assert pricing.ex_gst_unit_price("99.00") == Decimal("90.00")


def test_line_subtotal_multiplies_the_rounded_unit_price_by_quantity():
    unit = pricing.ex_gst_unit_price("120.00")
    assert pricing.line_subtotal(unit, 2) == Decimal("218.18")


def test_order_level_gst_and_total():
    subtotal = Decimal("1930.00")
    gst = pricing.order_gst(subtotal)
    total = pricing.order_total(subtotal, gst, Decimal("13.50"))
    assert gst == Decimal("193.00")
    assert total == Decimal("2136.50")


def test_gst_is_rounded_to_cents():
    assert pricing.order_gst(Decimal("488.18")) == Decimal("48.82")
    assert pricing.order_gst(Decimal("913.63")) == Decimal("91.36")


def test_unparsable_price_is_rejected_instead_of_silently_zero():
    assert pricing.ex_gst_unit_price(None) is None
    assert pricing.ex_gst_unit_price("not-a-price") is None


@pytest.mark.parametrize("value", ["0.00", 0, Decimal("0")])
def test_zero_rrp_is_zero(value):
    assert pricing.ex_gst_unit_price(value) == Decimal("0.00")
