"""Private requested local resource policy and strict project YAML decoding."""

from dataclasses import dataclass, field
from typing import Final

_MIB: Final = 1 << 20
_MAX_INTEGER: Final = (1 << 63) - 1


@dataclass(frozen=True, slots=True)
class _LocalResourcePolicy:
    """Authored ceilings and reserves; absence is not an effective limit."""

    max_database_bytes: int | None = None
    warn_estimated_input_rows: int | None = None
    managed_memory_bytes: int | None = None
    threads: int | None = None
    spill_bytes: int | None = None
    memory_reserve_bytes: int | None = None
    disk_reserve_bytes: int | None = None
    scratch_directory: str | None = field(default=None, repr=False)


_INTEGER_FIELDS: Final = {
    "max-database-mib": _MIB,
    "warn-estimated-input-rows": 1,
    "managed-memory-mib": _MIB,
    "threads": 1,
    "spill-mib": _MIB,
    "memory-reserve-mib": _MIB,
    "disk-reserve-mib": _MIB,
}


class _InvalidResourcePolicyError(ValueError):
    """Safe configuration error; never retain or interpolate input values."""


def _mapping(value: object, *, allowed: frozenset[str], location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _InvalidResourcePolicyError(f"Project config field `{location}` must be a mapping.")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str) or key not in allowed:
            raise _InvalidResourcePolicyError(f"Unknown or invalid field in `{location}`.")
        result[key] = item
    return result


def _parse_local_resource_policy(execution: object) -> _LocalResourcePolicy:
    root = _mapping(execution, allowed=frozenset({"scan-budget"}), location="execution")
    scan = _mapping(
        root.get("scan-budget", {}),
        allowed=frozenset({"local"}),
        location="execution.scan-budget",
    )
    local = _mapping(
        scan.get("local", {}),
        allowed=frozenset(_INTEGER_FIELDS) | {"scratch-directory"},
        location="execution.scan-budget.local",
    )
    integers: dict[str, int] = {}
    for key, multiplier in _INTEGER_FIELDS.items():
        if key not in local:
            continue
        value = local[key]
        if type(value) is not int or not 0 < value <= _MAX_INTEGER // multiplier:
            raise _InvalidResourcePolicyError(
                f"Project resource field `{key}` must be a positive integer within its range."
            )
        integers[key] = value * multiplier
    scratch: str | None = None
    if "scratch-directory" in local:
        value = local["scratch-directory"]
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise _InvalidResourcePolicyError(
                "Project resource field `scratch-directory` must be a non-empty path string."
            )
        scratch = value
    return _LocalResourcePolicy(
        max_database_bytes=integers.get("max-database-mib"),
        warn_estimated_input_rows=integers.get("warn-estimated-input-rows"),
        managed_memory_bytes=integers.get("managed-memory-mib"),
        threads=integers.get("threads"),
        spill_bytes=integers.get("spill-mib"),
        memory_reserve_bytes=integers.get("memory-reserve-mib"),
        disk_reserve_bytes=integers.get("disk-reserve-mib"),
        scratch_directory=scratch,
    )
