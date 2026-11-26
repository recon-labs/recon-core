"""Private length-delimited numeric result transport for owned DuckDB workers.

The caller binds the expected column names to its trusted rendered request.
No names, SQL, arbitrary objects, or native exception text are encoded.
"""

import struct
from decimal import Decimal
from typing import BinaryIO, Final

from recon_core.adapters._aggregate_runtime import (
    _AggregateQueryResult,
    _NumericDomain,
    _NumericValue,
)
from recon_core.adapters._project_binding import _InvalidAggregateResultError

# Native BIGNUM/VARINT uses a three-byte sign/length header, with 23 bits
# for magnitude length (also the documented native MAX_DATA_SIZE).
_MAX_INTEGER_BYTES: Final = (1 << 23) - 1
_MAX_COLUMNS: Final = 9  # Largest existing grouped aggregate summary.
_CHUNK_BYTES: Final = 64 * 1024  # I/O granularity, not a value limit.
_DOMAIN_TAGS: Final = {
    _NumericDomain.EXACT_INTEGER: 1,
    _NumericDomain.EXACT_DECIMAL: 2,
    _NumericDomain.NATIVE_FLOAT: 3,
}
_TAG_DOMAINS: Final = {tag: domain for domain, tag in _DOMAIN_TAGS.items()}
_FIELD_HEADER_BYTES: Final = 6  # domain, value/sign tag, uint32 size


def _validate_columns(columns: tuple[str, ...]) -> None:
    if (
        not isinstance(columns, tuple)
        or not 1 <= len(columns) <= _MAX_COLUMNS
        or any(not isinstance(name, str) or not name for name in columns)
        or len(set(columns)) != len(columns)
    ):
        raise _InvalidAggregateResultError()


def _write_all(stream: BinaryIO, data: bytes) -> None:
    view = memoryview(data)
    while view:
        part = view[:_CHUNK_BYTES]
        count = stream.write(part)
        if count is None or not 0 < count <= len(part):
            raise _InvalidAggregateResultError()
        view = view[count:]


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(min(size - len(data), _CHUNK_BYTES))
        if not chunk or len(chunk) > size - len(data):
            raise _InvalidAggregateResultError()
        data.extend(chunk)
    return bytes(data)


def _payload(domain: _NumericDomain, value: _NumericValue) -> tuple[int, bytes]:
    if value is None:
        return 0, b""
    if domain is _NumericDomain.EXACT_INTEGER and type(value) is int:
        size = (value.bit_length() + 7) // 8
        if size > _MAX_INTEGER_BYTES:
            raise _InvalidAggregateResultError()
        return (2 if value < 0 else 1), abs(value).to_bytes(size, "big")
    if domain is _NumericDomain.NATIVE_FLOAT and type(value) is float:
        return 1, struct.pack(">d", value)
    if domain is _NumericDomain.EXACT_DECIMAL and isinstance(value, Decimal):
        if not value.is_finite():
            raise _InvalidAggregateResultError()
        parts = value.as_tuple()
        exponent = parts.exponent
        if (
            not isinstance(exponent, int)
            or not -38 <= exponent <= 0
            or not 1 <= len(parts.digits) <= 38
        ):
            raise _InvalidAggregateResultError()
        # Preserve sign, coefficient digits and scale without context arithmetic.
        return 1, bytes((parts.sign, -exponent, *parts.digits))
    raise _InvalidAggregateResultError()


def _max_payload(domain: _NumericDomain) -> int:
    if domain is _NumericDomain.EXACT_INTEGER:
        return _MAX_INTEGER_BYTES
    if domain is _NumericDomain.EXACT_DECIMAL:
        return 40  # sign, scale, up to 38 native DECIMAL coefficient digits
    return 8


def _decode_payload(domain: _NumericDomain, tag: int, data: bytes) -> _NumericValue:
    if tag == 0 and not data:
        return None
    if domain is _NumericDomain.EXACT_INTEGER and tag in (1, 2):
        if (data and data[0] == 0) or (not data and tag == 2):
            raise _InvalidAggregateResultError()
        magnitude = int.from_bytes(data, "big")
        return -magnitude if tag == 2 else magnitude
    if domain is _NumericDomain.NATIVE_FLOAT and tag == 1 and len(data) == 8:
        return float(struct.unpack(">d", data)[0])
    if domain is _NumericDomain.EXACT_DECIMAL and tag == 1 and 3 <= len(data) <= 40:
        sign, scale, *digits = data
        if (
            sign not in (0, 1)
            or scale > 38
            or any(digit > 9 for digit in digits)
            or (len(digits) > 1 and digits[0] == 0)
        ):
            raise _InvalidAggregateResultError()
        return Decimal((sign, tuple(digits), -scale))
    raise _InvalidAggregateResultError()


def _valid_field_length(domain: _NumericDomain, tag: int, size: int) -> bool:
    if tag == 0:
        return size == 0
    if domain is _NumericDomain.EXACT_INTEGER:
        return tag in (1, 2) and size <= _MAX_INTEGER_BYTES and (tag != 2 or size > 0)
    if domain is _NumericDomain.EXACT_DECIMAL:
        return tag == 1 and 3 <= size <= _max_payload(domain)
    return tag == 1 and size == 8


def _write_result(
    stream: BinaryIO, result: _AggregateQueryResult, *, expected_columns: tuple[str, ...]
) -> None:
    _validate_columns(expected_columns)
    if (
        result.columns != expected_columns
        or len(result.domains) != len(expected_columns)
        or len(result.row) != len(expected_columns)
    ):
        raise _InvalidAggregateResultError()
    # Validate the complete row before writing any frame, but do not concatenate
    # large integer payloads into an additional aggregate-sized copy.
    fields: list[tuple[int, int, bytes]] = []
    for domain, value in zip(result.domains, result.row, strict=True):
        if not isinstance(domain, _NumericDomain):
            raise _InvalidAggregateResultError()
        tag, payload = _payload(domain, value)
        fields.append((_DOMAIN_TAGS[domain], tag, payload))
    size = 1 + sum(_FIELD_HEADER_BYTES + len(payload) for _, _, payload in fields)
    _write_all(stream, struct.pack(">IB", size, len(fields)))
    for domain_tag, tag, payload in fields:
        _write_all(stream, struct.pack(">BBI", domain_tag, tag, len(payload)))
        _write_all(stream, payload)


def _read_result(stream: BinaryIO, *, expected_columns: tuple[str, ...]) -> _AggregateQueryResult:
    _validate_columns(expected_columns)
    arity = len(expected_columns)
    size = int.from_bytes(_read_exact(stream, 4), "big")
    if (
        not 1 + arity * _FIELD_HEADER_BYTES
        <= size
        <= (1 + arity * (_FIELD_HEADER_BYTES + _MAX_INTEGER_BYTES))
    ):
        raise _InvalidAggregateResultError()
    if _read_exact(stream, 1)[0] != arity:
        raise _InvalidAggregateResultError()
    remaining = size - 1
    domains: list[_NumericDomain] = []
    values: list[_NumericValue] = []
    for index in range(arity):
        if remaining < _FIELD_HEADER_BYTES:
            raise _InvalidAggregateResultError()
        domain_tag, tag, length = struct.unpack(">BBI", _read_exact(stream, _FIELD_HEADER_BYTES))
        remaining -= _FIELD_HEADER_BYTES
        domain = _TAG_DOMAINS.get(domain_tag)
        future_headers = (arity - index - 1) * _FIELD_HEADER_BYTES
        if (
            domain is None
            or length > remaining - future_headers
            or not _valid_field_length(domain, tag, length)
        ):
            raise _InvalidAggregateResultError()
        values.append(_decode_payload(domain, tag, _read_exact(stream, length)))
        domains.append(domain)
        remaining -= length
    if remaining != 0:
        raise _InvalidAggregateResultError()
    return _AggregateQueryResult(expected_columns, tuple(domains), tuple(values))
