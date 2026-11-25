"""Shared private interpretation of finite absolute numeric tolerance."""

import math
from collections.abc import Mapping
from decimal import Decimal


def absolute_tolerance(value: object) -> Decimal | None:
    """Return an exact threshold for a supported explicit policy, or None if invalid."""
    if isinstance(value, Mapping):
        if set(value) != {"type", "value"} or value.get("type") != "absolute":
            return None
        value = value.get("value")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Decimal(value) if value >= 0 else None
    if isinstance(value, float):
        if not math.isfinite(value) or value < 0:
            return None
        return Decimal(str(value))
    if isinstance(value, Decimal):
        if not value.is_finite() or value < 0:
            return None
        return value
    return None
