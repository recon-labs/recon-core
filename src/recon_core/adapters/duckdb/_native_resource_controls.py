"""Private DuckDB control assignment; readback is not enforcement proof."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

_MAX: Final = (1 << 63) - 1
_UNITS: Final = {
    **{unit: 1024**i for i, unit in enumerate(("KiB", "MiB", "GiB", "TiB", "PiB"), 1)},
    **{unit: 1000**i for i, unit in enumerate(("kB", "MB", "GB", "TB", "PB"), 1)},
}
_DISPLAY: Final = re.compile(r"([0-9]{1,19})(?:\.([0-9]))? (byte|bytes|[kKMGTP]i?B)")
_READ_SETTING: Final = {
    "memory_limit": "SELECT current_setting('memory_limit')",
    "threads": "SELECT current_setting('threads')",
    "max_temp_directory_size": "SELECT current_setting('max_temp_directory_size')",
    "temp_directory": "SELECT current_setting('temp_directory')",
}


class _NativeControlError(RuntimeError):
    """Fixed safe failure; no native error text or authored values."""


@dataclass(frozen=True, slots=True)
class _NativeSizeInterval:
    """Inclusive integer interval for a native human-formatted byte count."""

    lower_bytes: int
    upper_bytes: int

    def contains(self, target: int) -> bool:
        return self.lower_bytes <= target <= self.upper_bytes


def _parse_native_size(value: object) -> _NativeSizeInterval | None:
    # The tested DuckDB formatter truncates to one decimal digit. Byte
    # counts below the first unit are exact. Never interpret prose defaults
    # (including percentage or unlimited descriptions) as finite sizes.
    if not isinstance(value, str):
        return None
    match = _DISPLAY.fullmatch(value)
    if match is None:
        return None
    whole_text, fractional, unit = match.groups()
    whole = int(whole_text)
    if unit in {"byte", "bytes"}:
        if fractional is not None or whole > _MAX:
            return None
        return _NativeSizeInterval(whole, whole)
    multiplier = _UNITS.get(unit)
    if multiplier is None or fractional is None or whole == 0:
        return None
    tenths = whole * 10 + int(fractional)
    lower = (tenths * multiplier + 9) // 10
    upper = ((tenths + 1) * multiplier - 1) // 10
    if lower > _MAX:
        return None
    return _NativeSizeInterval(lower, min(upper, _MAX))


def _native_integer(value: object, *, minimum: int) -> int | None:
    if type(value) is int and minimum <= value <= _MAX:
        return value
    return None


def _representable_bytes(value: int) -> int:
    # Native string parsing uses binary64. Round down to an exactly
    # representable integer rather than risking upward rounding at large
    # byte counts. This is precision handling, not a workload ceiling.
    shift = max(0, value.bit_length() - 53)
    return (value >> shift) << shift


@dataclass(frozen=True, slots=True)
class _NativeControlRequest:
    """Effective targets provided by policy; scratch ownership is external."""

    memory_bytes: int
    threads: int
    spill_bytes: int
    scratch_directory: Path = field(repr=False)

    def __post_init__(self) -> None:
        if _native_integer(self.memory_bytes, minimum=1) is None:
            raise _NativeControlError("Native managed memory target is invalid.")
        if _native_integer(self.threads, minimum=1) is None:
            raise _NativeControlError("Native thread target is invalid.")
        if _native_integer(self.spill_bytes, minimum=0) is None:
            raise _NativeControlError("Native spill target is invalid.")
        if (
            not isinstance(self.scratch_directory, Path)
            or not self.scratch_directory.is_absolute()
            or ".." in self.scratch_directory.parts
            or "\x00" in str(self.scratch_directory)
        ):
            raise _NativeControlError("Native scratch directory is invalid.")
        object.__setattr__(self, "memory_bytes", _representable_bytes(self.memory_bytes))
        object.__setattr__(self, "spill_bytes", _representable_bytes(self.spill_bytes))


@dataclass(frozen=True, slots=True)
class _NativeRecommendations:
    memory_bytes: int | None
    threads: int | None


@dataclass(frozen=True, slots=True)
class _NativeControlReadback:
    """Reported settings only, never a hard cap or independent native proof."""

    memory: _NativeSizeInterval
    threads: int
    spill: _NativeSizeInterval
    enforcement_proven: bool = field(default=False, init=False)


def _setting(connection: Any, name: str) -> object:
    try:
        rows = connection.execute(_READ_SETTING[name]).fetchmany(2)
    except Exception:
        return None
    if (
        not isinstance(rows, list | tuple)
        or len(rows) != 1
        or not isinstance(rows[0], list | tuple)
        or len(rows[0]) != 1
    ):
        return None
    return rows[0][0]


def _read_native_recommendations(connection: Any) -> _NativeRecommendations:
    """Read auto settings from a caller-owned empty isolated native instance."""

    memory = _parse_native_size(_setting(connection, "memory_limit"))
    return _NativeRecommendations(
        memory_bytes=memory.lower_bytes if memory and memory.lower_bytes > 0 else None,
        threads=_native_integer(_setting(connection, "threads"), minimum=1),
    )


def _native_startup_config(request: _NativeControlRequest) -> dict[str, str]:
    """Only memory, threads and private scratch belong in connect config."""

    return {
        "memory_limit": f"{request.memory_bytes} bytes",
        "threads": str(request.threads),
        "temp_directory": str(request.scratch_directory),
    }


def _apply_native_controls(connection: Any, request: _NativeControlRequest) -> _NativeControlReadback:
    """Set spill before any transaction/metadata, then verify native reports.

    Only the isolated owned connection may be supplied. A failed assignment
    or unreadable/mismatched setting does not permit data work. The worker
    must additionally establish scope, effect capability and monitored
    protection; this collaborator does not admit or execute checks.
    """

    try:
        connection.execute(f"SET max_temp_directory_size = '{request.spill_bytes} bytes'")
    except Exception:
        raise _NativeControlError("Native spill control could not be applied.") from None

    memory = _parse_native_size(_setting(connection, "memory_limit"))
    if memory is None or not memory.contains(request.memory_bytes):
        raise _NativeControlError("Native managed memory setting could not be verified.")
    threads = _native_integer(_setting(connection, "threads"), minimum=1)
    if threads is None or threads != request.threads:
        raise _NativeControlError("Native thread setting could not be verified.")
    spill = _parse_native_size(_setting(connection, "max_temp_directory_size"))
    if spill is None or not spill.contains(request.spill_bytes):
        raise _NativeControlError("Native spill setting could not be verified.")
    scratch = _setting(connection, "temp_directory")
    if not isinstance(scratch, str) or Path(scratch) != request.scratch_directory:
        raise _NativeControlError("Native scratch setting could not be verified.")
    return _NativeControlReadback(memory=memory, threads=threads, spill=spill)
