"""DuckDB-specific managed resource targets, independent of native execution."""

from dataclasses import dataclass
from fractions import Fraction
from math import ceil
from typing import Literal

from recon_core.config._local_resource_policy import _LocalResourcePolicy

# DuckDB's published minimum memory-per-thread rule of thumb (decimal MB).
# A best-effort automatic parallelism heuristic, never an admission floor.
# https://duckdb.org/docs/current/guides/performance/environment
_AUTO_MEMORY_PER_THREAD_BYTES = 125_000_000


@dataclass(frozen=True, slots=True)
class _LocalResourceInputs:
    """Effective observations: None is unavailable, not zero or unlimited."""

    memory_headroom_bytes: int | None = None
    cpu_capacity: Fraction | None = None
    scratch_free_bytes: int | None = None
    scratch_memory_backed: bool | None = None
    native_memory_bytes: int | None = None
    native_threads: int | None = None


@dataclass(frozen=True, slots=True)
class _LocalResourceTargets:
    """Requested managed targets, not proof of native enforcement."""

    managed_memory_bytes: int | None
    threads: int | None
    spill_bytes: int | None
    reduced_authored_targets: tuple[str, ...]
    automatic_threads_reduced: bool = False


def _minimum_known(*values: int | None) -> int | None:
    return min((value for value in values if value is not None), default=None)


class _UnknownPercentageCapacityError(ValueError):
    """A valid percentage has no trustworthy denominator."""

    def __init__(self, setting: Literal["managed-memory", "spill"]) -> None:
        self.setting = setting
        super().__init__(f"Unknown capacity for {setting} percentage; use auto or fixed MiB.")


def _percentage_request(
    percent: int | None, available: int | None, *, setting: Literal["managed-memory", "spill"]
) -> int | None:
    if percent is None:
        return None
    if type(percent) is not int or not 1 <= percent <= 100:
        raise ValueError(f"Invalid {setting} percentage.")
    if available is None:
        raise _UnknownPercentageCapacityError(setting)
    return available * percent // 100


def _validate_inputs(inputs: _LocalResourceInputs) -> None:
    for value in (
        inputs.memory_headroom_bytes,
        inputs.scratch_free_bytes,
        inputs.native_memory_bytes,
        inputs.native_threads,
    ):
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Invalid resource observation.")
    if inputs.cpu_capacity is not None and (
        type(inputs.cpu_capacity) is not Fraction or inputs.cpu_capacity < 0
    ):
        raise ValueError("Invalid resource observation.")
    if inputs.scratch_memory_backed is not None and type(inputs.scratch_memory_backed) is not bool:
        raise ValueError("Invalid resource observation.")


def _calculate_local_resource_targets(
    policy: _LocalResourcePolicy,
    inputs: _LocalResourceInputs,
) -> _LocalResourceTargets:
    """Calculate byte/thread targets; native range, effects and advice are separate."""

    _validate_inputs(inputs)
    headroom = inputs.memory_headroom_bytes
    free = inputs.scratch_free_bytes
    cpu = ceil(inputs.cpu_capacity) if inputs.cpu_capacity is not None else None

    memory_request = _percentage_request(
        policy.managed_memory_percent, headroom, setting="managed-memory"
    )
    if policy.managed_memory_bytes is not None:
        memory_request = policy.managed_memory_bytes
    if memory_request is None:
        memory = _minimum_known(
            headroom // 2 if headroom is not None else None, inputs.native_memory_bytes
        )
    else:
        memory = _minimum_known(memory_request, headroom)

    threads = _minimum_known(
        policy.threads if policy.threads is not None else inputs.native_threads, cpu
    )

    automatic_threads_reduced = False
    if (
        policy.threads is None
        and headroom is not None
        and memory is not None
        and memory > 0
        and threads is not None
        and threads > 0
    ):
        # Preserve a usable single-thread attempt and never invent missing
        # CPU capacity. Explicit thread requests retain their original semantics.
        tuned = min(threads, max(1, memory // _AUTO_MEMORY_PER_THREAD_BYTES))
        automatic_threads_reduced = tuned < threads
        threads = tuned

    spill_request = _percentage_request(policy.spill_percent, free, setting="spill")
    if policy.spill_bytes is not None:
        spill_request = policy.spill_bytes
    if spill_request is not None:
        spill = _minimum_known(spill_request, free)
    else:
        spill = free * 9 // 10 if free is not None else None
    # Known memory-backed scratch shares headroom with the managed memory target.
    # Missing facts are not grounds for inventing capacity or discarding valid
    # independent observations; the execution layer must advise on uncertainty.
    if inputs.scratch_memory_backed is True and headroom is not None and memory is not None:
        spill = _minimum_known(spill, max(0, headroom - memory))

    reduced = tuple(
        name
        for name, requested, effective in (
            ("managed-memory", memory_request, memory),
            ("threads", policy.threads, threads),
            ("spill", spill_request, spill),
        )
        if requested is not None and effective is not None and effective < requested
    )
    return _LocalResourceTargets(
        managed_memory_bytes=memory,
        threads=threads,
        spill_bytes=spill,
        reduced_authored_targets=reduced,
        automatic_threads_reduced=automatic_threads_reduced,
    )
