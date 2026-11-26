"""Private result transport preserves native numeric domains and bounds."""

import io
import struct
from decimal import Decimal, localcontext

import pytest

from recon_core.adapters._aggregate_runtime import _AggregateQueryResult, _NumericDomain
from recon_core.adapters._project_binding import _InvalidAggregateResultError
from recon_core.adapters.duckdb._worker_result_codec import (
    _MAX_INTEGER_BYTES,
    _read_result,
    _write_result,
)

_INTEGER = _NumericDomain.EXACT_INTEGER
_DECIMAL = _NumericDomain.EXACT_DECIMAL
_FLOAT = _NumericDomain.NATIVE_FLOAT


def _roundtrip(result: _AggregateQueryResult) -> _AggregateQueryResult:
    stream = io.BytesIO()
    _write_result(stream, result, expected_columns=result.columns)
    stream.seek(0)
    actual = _read_result(stream, expected_columns=result.columns)
    assert stream.read() == b""
    return actual


@pytest.mark.regression_capture("duckdb-worker-lossless-result-transport")
@pytest.mark.parametrize(
    "value",
    [0, 1, -1, 2**128 - 1, -(2**127), 10**5000, -(10**5000)],
    ids=["zero", "one", "negative", "uhugeint", "hugeint", "large", "large-negative"],
)
def test_integer_transport_is_lossless(value: int) -> None:
    result = _AggregateQueryResult(("n",), (_INTEGER,), (value,))
    assert _roundtrip(result) == result


def test_native_maximum_integer_magnitude_is_supported() -> None:
    value = 1 << (_MAX_INTEGER_BYTES * 8 - 1)
    result = _AggregateQueryResult(("n",), (_INTEGER,), (value,))
    assert _roundtrip(result).row[0] == value
    with pytest.raises(_InvalidAggregateResultError):
        _roundtrip(_AggregateQueryResult(("n",), (_INTEGER,), (value << 8,)))


@pytest.mark.parametrize(
    "value",
    [Decimal("0.00"), Decimal("-0.000"), Decimal("9" * 38), Decimal("0." + "0" * 37 + "1")],
)
def test_decimal_transport_preserves_tuple(value: Decimal) -> None:
    with localcontext() as ctx:
        ctx.prec = 2
        actual = _roundtrip(_AggregateQueryResult(("n",), (_DECIMAL,), (value,))).row[0]
    assert isinstance(actual, Decimal)
    assert actual.as_tuple() == value.as_tuple()


@pytest.mark.parametrize(
    "bits", [0, 1, 1 << 63, 0x7FF0000000000000, 0xFFF0000000000000, 0x7FF8000000000001]
)
def test_float_transport_preserves_ieee_bits(bits: int) -> None:
    raw = bits.to_bytes(8, "big")
    value = struct.unpack(">d", raw)[0]
    actual = _roundtrip(_AggregateQueryResult(("n",), (_FLOAT,), (value,))).row[0]
    assert type(actual) is float
    assert struct.pack(">d", actual) == raw


def test_nullable_mixed_domains_and_fixed_arity() -> None:
    result = _AggregateQueryResult(
        ("count", "minimum", "maximum"), (_INTEGER, _DECIMAL, _FLOAT), (7, None, -0.0)
    )
    assert _roundtrip(result) == result


@pytest.mark.parametrize(
    ("domain", "value"),
    [
        (_INTEGER, True),
        (_INTEGER, 1.0),
        (_FLOAT, 1),
        (_DECIMAL, Decimal("NaN")),
        (_DECIMAL, Decimal("1e-39")),
        (_DECIMAL, Decimal("9" * 39)),
    ],
)
def test_wrong_domain_rejected(domain: _NumericDomain, value: object) -> None:
    with pytest.raises(_InvalidAggregateResultError):
        _roundtrip(_AggregateQueryResult(("n",), (domain,), (value,)))  # type: ignore[arg-type]


@pytest.mark.regression_capture("duckdb-worker-lossless-result-transport")
def test_truncated_and_oversized_frame_rejected_before_payload_read() -> None:
    result = _AggregateQueryResult(("n",), (_INTEGER,), (123,))
    stream = io.BytesIO()
    _write_result(stream, result, expected_columns=result.columns)
    payload = stream.getvalue()
    for end in range(len(payload)):
        with pytest.raises(_InvalidAggregateResultError):
            _read_result(io.BytesIO(payload[:end]), expected_columns=("n",))
    # Header: unsigned 32-bit body length, then arity and tagged fields.
    oversized = struct.pack(">I", 0xFFFFFFFF)
    with pytest.raises(_InvalidAggregateResultError):
        _read_result(io.BytesIO(oversized), expected_columns=("n",))


def test_frame_cannot_consume_next_frame_or_accept_trailing_bytes() -> None:
    result = _AggregateQueryResult(("n",), (_INTEGER,), (123,))
    stream = io.BytesIO()
    _write_result(stream, result, expected_columns=("n",))
    first = stream.getvalue()
    _write_result(stream, result, expected_columns=("n",))
    stream.seek(0)
    assert _read_result(stream, expected_columns=("n",)) == result
    assert stream.tell() == len(first)
    assert _read_result(stream, expected_columns=("n",)) == result
    malformed = struct.pack(">I", len(first) - 3) + first[4:] + b"x"
    with pytest.raises(_InvalidAggregateResultError):
        _read_result(io.BytesIO(malformed), expected_columns=("n",))
