"""Private aggregate admission and shared numeric policy tests."""

from decimal import Decimal, localcontext

import pytest

from recon_core._numeric_policy import absolute_tolerance
from recon_core.compiler.policies import validate_tolerance


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, Decimal(0)),
        (-0.0, Decimal(0)),
        (0.1, Decimal("0.1")),
        (2**100 + 1, Decimal(2**100 + 1)),
        (Decimal("123456789.000000000000000001"), Decimal("123456789.000000000000000001")),
        ({"type": "absolute", "value": 0.1}, Decimal("0.1")),
    ],
)
def test_absolute_tolerance_is_context_independent(value: object, expected: Decimal) -> None:
    with localcontext() as context:
        context.prec = 3
        assert absolute_tolerance(value) == expected
        assert validate_tolerance(value, resource_type="metric", resource_name="m").succeeded


@pytest.mark.parametrize(
    "value",
    [
        None,
        False,
        -1,
        "0.1",
        float("nan"),
        float("inf"),
        Decimal("NaN"),
        Decimal("-Infinity"),
        {"type": "absolute"},
        {"type": "absolute", "value": {"type": "absolute", "value": 1}},
        {"type": "absolute", "value": True},
        {"type": "absolute", "value": 1, 2: 3},
        {"type": "percentage", "value": 1},
    ],
)
def test_invalid_explicit_tolerance_agrees_with_compiler(value: object) -> None:
    assert absolute_tolerance(value) is None
    assert not validate_tolerance(value, resource_type="metric", resource_name="m").succeeded
