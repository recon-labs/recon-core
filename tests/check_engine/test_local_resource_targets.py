"""Pure policy tests: observations are inputs, not admission proof."""

from fractions import Fraction

import pytest

from recon_core.check_engine.scan_budget import (
    _calculate_local_resource_targets,
    _LocalResourceInputs,
    _LocalResourceTuning,
)
from recon_core.config._local_resource_policy import _LocalResourcePolicy

_MIB = 1 << 20
_TUNING = _LocalResourceTuning(memory_reserve_divisor=4, disk_reserve_divisor=10)


@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_adaptive_targets_follow_effective_environment() -> None:
    small = _calculate_local_resource_targets(
        _LocalResourcePolicy(),
        _LocalResourceInputs(
            memory_headroom_bytes=512 * _MIB,
            cpu_capacity=Fraction(1, 2),
            scratch_free_bytes=4096 * _MIB,
            scratch_memory_backed=False,
            native_memory_bytes=12 * 1024 * _MIB,
            native_threads=8,
        ),
        _TUNING,
    )
    large = _calculate_local_resource_targets(
        _LocalResourcePolicy(),
        _LocalResourceInputs(
            memory_headroom_bytes=32 * 1024 * _MIB,
            cpu_capacity=Fraction(12),
            scratch_free_bytes=100 * 1024 * _MIB,
            scratch_memory_backed=False,
            native_memory_bytes=24 * 1024 * _MIB,
            native_threads=16,
        ),
        _TUNING,
    )
    assert small.managed_memory_bytes == 384 * _MIB
    assert small.threads == 1
    assert small.memory_reserve_bytes == 128 * _MIB
    assert small.spill_bytes == 4096 * _MIB - (4096 * _MIB + 9) // 10
    assert large.managed_memory_bytes == 24 * 1024 * _MIB
    assert large.threads == 12
    assert large.spill_bytes == 90 * 1024 * _MIB


def test_local_resource_policy_precedence() -> None:
    policy = _LocalResourcePolicy(
        managed_memory_bytes=900,
        threads=8,
        spill_bytes=700,
        memory_reserve_bytes=100,
        disk_reserve_bytes=200,
    )
    inputs = _LocalResourceInputs(
        memory_headroom_bytes=800,
        cpu_capacity=Fraction(5, 2),
        scratch_free_bytes=600,
        scratch_memory_backed=False,
        native_memory_bytes=200,
        native_threads=1,
        native_spill_ceiling_bytes=300,
    )
    targets = _calculate_local_resource_targets(policy, inputs, _TUNING)
    assert targets.managed_memory_bytes == 700
    assert targets.threads == 3
    assert targets.spill_bytes == 300
    assert targets.reduced_authored_targets == ("managed-memory-mib", "threads", "spill-mib")


def test_authored_targets_can_exceed_native_recommendations() -> None:
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(managed_memory_bytes=800, threads=4),
        _LocalResourceInputs(
            memory_headroom_bytes=1000,
            cpu_capacity=Fraction(8),
            scratch_free_bytes=1000,
            scratch_memory_backed=False,
            native_memory_bytes=100,
            native_threads=1,
        ),
        _TUNING,
    )
    assert targets.managed_memory_bytes == 750
    assert targets.threads == 4
    assert targets.reduced_authored_targets == ("managed-memory-mib",)


@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_unknown_is_not_zero_or_unlimited() -> None:
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(managed_memory_bytes=100, threads=4, spill_bytes=100),
        _LocalResourceInputs(),
        _TUNING,
    )
    assert targets.managed_memory_bytes is None
    assert targets.threads is None
    assert targets.spill_bytes is None
    assert targets.memory_reserve_bytes is None
    assert targets.disk_reserve_bytes is None

    exhausted = _calculate_local_resource_targets(
        _LocalResourcePolicy(),
        _LocalResourceInputs(
            memory_headroom_bytes=0,
            cpu_capacity=Fraction(0),
            scratch_free_bytes=0,
            scratch_memory_backed=False,
        ),
        _TUNING,
    )
    assert exhausted.managed_memory_bytes == 0
    assert exhausted.threads == 0
    assert exhausted.spill_bytes == 0


@pytest.mark.parametrize(
    ("memory", "native", "expected"),
    [(1000, 200, 550), (1000, None, 0), (0, 100, 0), (None, 100, None)],
)
@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_memory_backed_scratch_cannot_double_count_headroom(
    memory: int | None, native: int | None, expected: int | None
) -> None:
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(),
        _LocalResourceInputs(
            memory_headroom_bytes=memory,
            native_memory_bytes=native,
            scratch_free_bytes=1000,
            scratch_memory_backed=True,
        ),
        _TUNING,
    )
    assert targets.spill_bytes == expected


def test_unknown_scratch_kind_is_not_disk_backed() -> None:
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(),
        _LocalResourceInputs(memory_headroom_bytes=1000, scratch_free_bytes=1000),
        _TUNING,
    )
    assert targets.spill_bytes is None


@pytest.mark.parametrize("headroom", [1, 2, 3, 4, 5, 7])
def test_resource_reserves_round_up_not_workload_limits(headroom: int) -> None:
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(),
        _LocalResourceInputs(
            memory_headroom_bytes=headroom,
            cpu_capacity=Fraction(1, 100),
            scratch_free_bytes=headroom,
            scratch_memory_backed=False,
        ),
        _TUNING,
    )
    assert targets.managed_memory_bytes == headroom - (headroom + 3) // 4
    assert targets.spill_bytes == headroom - (headroom + 9) // 10
    assert targets.threads == 1


def test_tuning_is_adapter_supplied_not_universal() -> None:
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(),
        _LocalResourceInputs(
            memory_headroom_bytes=1000,
            scratch_free_bytes=1000,
            scratch_memory_backed=False,
        ),
        _LocalResourceTuning(memory_reserve_divisor=2, disk_reserve_divisor=5),
    )
    assert targets.managed_memory_bytes == 500
    assert targets.spill_bytes == 800
