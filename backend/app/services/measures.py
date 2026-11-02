"""Tolerant parsers for the measurement strings used by the product data.

The ``product_list`` extract stores physical dimensions as human readable strings
(``"10.0mm"``, ``"0.2g"``, ``"1000.0mm³"``). Real order feeds are rarely perfectly
clean, so every parser returns ``None`` instead of raising when a value cannot be
understood; callers then fall back to documented defaults.
"""

from __future__ import annotations

import re
from typing import Optional

_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")

# millimetres per unit
_LENGTH_FACTORS = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}
# grams per unit
_MASS_FACTORS = {"mg": 0.001, "g": 1.0, "kg": 1000.0}
# millilitres per unit
_VOLUME_FACTORS = {"mm3": 0.001, "cm3": 1.0, "ml": 1.0, "l": 1000.0}


def _number(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:  # pragma: no cover - defensive
        return None


def _unit(value: object) -> str:
    """Normalised unit suffix, e.g. ``"1000.0mm³"`` -> ``"1000mm3"``."""
    if value is None:
        return ""
    text = str(value).lower().replace("\u00b3", "3")
    return re.sub(r"[\s.]", "", text)


def parse_length_mm(value: object) -> Optional[float]:
    """``"10.0mm"`` -> ``10.0`` millimetres."""
    number = _number(value)
    if number is None:
        return None
    unit = _unit(value)
    for suffix, factor in _LENGTH_FACTORS.items():
        if unit.endswith(suffix):
            return number * factor
    # unit-less values in this data set are millimetres
    return number


def parse_mass_g(value: object) -> Optional[float]:
    """``"0.2g"`` -> ``0.2`` grams, ``"0.2kg"`` -> ``200.0`` grams."""
    number = _number(value)
    if number is None:
        return None
    unit = _unit(value)
    for suffix in ("mg", "kg", "g"):
        if unit.endswith(suffix):
            return number * _MASS_FACTORS[suffix]
    return number


def parse_volume_ml(value: object) -> Optional[float]:
    """``"1000.0mm³"`` -> ``1.0`` millilitre (1 cm³ = 1 mL)."""
    number = _number(value)
    if number is None:
        return None
    unit = _unit(value)
    for suffix in ("mm3", "cm3", "ml", "l"):
        if unit.endswith(suffix):
            return number * _VOLUME_FACTORS[suffix]
    return number


def parse_size_g_or_ml(value: object) -> Optional[float]:
    """``Size`` is unit-less in the source data: grams for dried herb, mL for liquids."""
    return _number(value)
