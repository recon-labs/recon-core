"""Private DuckDB resource-policy schema and normalized authored values."""

from dataclasses import dataclass, field, replace
from typing import Final

_MIB: Final = 1 << 20
_MAX_INTEGER: Final = (1 << 63) - 1


@dataclass(frozen=True, slots=True)
class _LocalResourcePolicy:
    """Normalized requested values; absence is not an effective resource limit."""

    max_database_bytes: int | None = None
    warn_estimated_input_rows: int | None = None
    managed_memory_bytes: int | None = None
    threads: int | None = None
    spill_bytes: int | None = None
    # Parked calculation inputs; remove with the superseded reserve arithmetic.
    memory_reserve_bytes: int | None = None
    disk_reserve_bytes: int | None = None
    scratch_directory: str | None = field(default=None, repr=False)
    managed_memory_percent: int | None = None
    spill_percent: int | None = None


@dataclass(frozen=True, slots=True)
class _LocalResourceLayer:
    """Authored normalized values and presence, including explicit resets."""

    policy: _LocalResourcePolicy = field(default_factory=_LocalResourcePolicy, repr=False)
    authored_fields: frozenset[str] = frozenset()


class _InvalidResourcePolicyError(ValueError):
    """Safe configuration error; never retain or interpolate input values."""


def _mapping(value: object, *, allowed: frozenset[str], location: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _InvalidResourcePolicyError(f"Resource policy field {location} must be a mapping.")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str) or key not in allowed:
            raise _InvalidResourcePolicyError(f"Unknown or invalid field in {location}.")
        result[key] = item
    return result


def _positive_integer(value: object, *, maximum: int, location: str) -> int:
    if type(value) is not int or not 0 < value <= maximum:
        raise _InvalidResourcePolicyError(
            f"Resource policy field {location} must be a positive integer within its range."
        )
    return value


def _managed_mode(value: object, *, location: str) -> tuple[int | None, int | None]:
    if isinstance(value, str) and value == "auto":
        return None, None
    mode = _mapping(value, allowed=frozenset({"mib", "percent"}), location=location)
    if len(mode) != 1:
        raise _InvalidResourcePolicyError(
            f"Resource policy field {location} requires exactly one of mib or percent."
        )
    if "mib" in mode:
        fixed = _positive_integer(mode["mib"], maximum=_MAX_INTEGER // _MIB, location=location)
        return fixed * _MIB, None
    return None, _positive_integer(mode["percent"], maximum=100, location=location)


def _parse_duckdb_resource_layer(value: object) -> _LocalResourceLayer:
    integers = {
        "max-database-mib": ("max_database_bytes", _MIB, "none"),
        "warn-estimated-input-rows": ("warn_estimated_input_rows", 1, "none"),
        "threads": ("threads", 1, "auto"),
    }
    modes = {"managed-memory": "managed_memory", "spill": "spill"}
    settings = _mapping(
        value,
        allowed=frozenset(integers) | frozenset(modes) | {"scratch-directory"},
        location="DuckDB resource policy",
    )
    changes: dict[str, int | None] = {}
    for key, (attribute, multiplier, reset) in integers.items():
        if key in settings:
            authored = settings[key]
            changes[attribute] = (
                None
                if isinstance(authored, str) and authored == reset
                else _positive_integer(authored, maximum=_MAX_INTEGER // multiplier, location=key)
                * multiplier
            )
    for key, prefix in modes.items():
        if key in settings:
            fixed, percent = _managed_mode(settings[key], location=key)
            changes[f"{prefix}_bytes"] = fixed
            changes[f"{prefix}_percent"] = percent
    scratch_directory: str | None = None
    if "scratch-directory" in settings:
        scratch = settings["scratch-directory"]
        if not isinstance(scratch, str) or not scratch.strip() or "\x00" in scratch:
            raise _InvalidResourcePolicyError(
                "Resource policy scratch-directory must be auto or a non-empty path string."
            )
        scratch_directory = None if scratch == "auto" else scratch
    authored_fields = frozenset(changes)
    if "scratch-directory" in settings:
        authored_fields |= {"scratch_directory"}
    return _LocalResourceLayer(
        policy=_LocalResourcePolicy(
            max_database_bytes=changes.get("max_database_bytes"),
            warn_estimated_input_rows=changes.get("warn_estimated_input_rows"),
            managed_memory_bytes=changes.get("managed_memory_bytes"),
            managed_memory_percent=changes.get("managed_memory_percent"),
            threads=changes.get("threads"),
            spill_bytes=changes.get("spill_bytes"),
            spill_percent=changes.get("spill_percent"),
            scratch_directory=scratch_directory,
        ),
        authored_fields=authored_fields,
    )


def _merge_local_resource_layers(*layers: _LocalResourceLayer) -> _LocalResourcePolicy:
    """Resolve whole logical settings without retaining inherited mode members."""

    result = _LocalResourcePolicy()
    for layer in layers:
        result = replace(
            result,
            **{name: getattr(layer.policy, name) for name in layer.authored_fields},
        )
    return result
