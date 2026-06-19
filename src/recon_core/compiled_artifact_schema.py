"""Shared schema helpers for compiled artifacts."""

from typing import Final

_TYPED_OPERATION_PAYLOAD_FIELDS: Final[dict[str, frozenset[str]]] = {
    "row_count": frozenset({"side"}),
    "compare_counts": frozenset(),
    "key_diff": frozenset({"direction", "identity"}),
    "null_key": frozenset({"side", "identity"}),
    "duplicate_key": frozenset({"side", "identity"}),
    "aggregate": frozenset({"side", "aggregate", "column"}),
    "grouped_aggregate": frozenset({"side", "aggregate", "column", "group_by"}),
    "compare_aggregates": frozenset(),
    "compare_grouped_aggregates": frozenset(),
}


def typed_operation_payload_fields(operation_type: str) -> frozenset[str] | None:
    """Return allowed payload fields for a compiled-check typed operation."""
    return _TYPED_OPERATION_PAYLOAD_FIELDS.get(operation_type)
