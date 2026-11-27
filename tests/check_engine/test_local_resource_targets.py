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

# Use the approved adapter-local automatic ratios in the replacement cases.
_APPROVED_TUNING = _LocalResourceTuning(memory_reserve_divisor=2, disk_reserve_divisor=10)


@pytest.mark.parametrize(
    ("headroom_gib", "free_gib", "expected_memory_gib", "expected_spill_gib"),
    [(16, 20, 12, 16), (32, 40, 24, 32), (8, 10, 6, 8)],
)
@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_relative_targets_follow_changing_capacity(
    headroom_gib: int, free_gib: int, expected_memory_gib: int, expected_spill_gib: int
) -> None:
    gib = 1024 * _MIB
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(managed_memory_percent=75, spill_percent=80),
        _LocalResourceInputs(
            memory_headroom_bytes=headroom_gib * gib,
            scratch_free_bytes=free_gib * gib,
            scratch_memory_backed=False,
            cpu_capacity=Fraction(8),
            native_memory_bytes=2 * gib,
            native_threads=4,
        ),
        _APPROVED_TUNING,
    )
    assert targets.managed_memory_bytes == expected_memory_gib * gib
    assert targets.spill_bytes == expected_spill_gib * gib
    assert targets.threads == 4


@pytest.mark.parametrize(
    ("percent", "capacity"),
    [(1, 101), (50, 101), (75, 101), (90, 101), (100, 101), (100, (1 << 63) - 1)],
)
@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_percentage_targets_floor_exactly(percent: int, capacity: int) -> None:
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(managed_memory_percent=percent, spill_percent=percent),
        _LocalResourceInputs(
            memory_headroom_bytes=capacity,
            scratch_free_bytes=capacity,
            scratch_memory_backed=False,
        ),
        _APPROVED_TUNING,
    )
    assert targets.managed_memory_bytes == capacity * percent // 100
    assert targets.spill_bytes == capacity * percent // 100


@pytest.mark.parametrize(
    ("headroom_gib", "expected_gib"),
    [(16, 12), (32, 12), (8, 8)],
)
@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_fixed_targets_only_reduce_at_known_capacity(headroom_gib: int, expected_gib: int) -> None:
    gib = 1024 * _MIB
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(managed_memory_bytes=12 * gib, spill_bytes=12 * gib),
        _LocalResourceInputs(
            memory_headroom_bytes=headroom_gib * gib,
            scratch_free_bytes=headroom_gib * gib,
            scratch_memory_backed=False,
            native_memory_bytes=gib,
        ),
        _APPROVED_TUNING,
    )
    assert targets.managed_memory_bytes == expected_gib * gib
    assert targets.spill_bytes == expected_gib * gib
    if expected_gib == 12:
        assert not targets.reduced_authored_targets
    else:
        assert len(targets.reduced_authored_targets) == 2


@pytest.mark.parametrize(
    ("memory", "native_memory", "expected"),
    [(1000, 300, 300), (1000, 900, 500), (1000, None, 500), (None, 300, 300), (0, 300, 0)],
)
@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_automatic_memory_uses_available_headroom_and_native_recommendation(
    memory: int | None, native_memory: int | None, expected: int
) -> None:
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(),
        _LocalResourceInputs(memory_headroom_bytes=memory, native_memory_bytes=native_memory),
        _APPROVED_TUNING,
    )
    assert targets.managed_memory_bytes == expected


@pytest.mark.parametrize(
    "policy",
    [
        _LocalResourcePolicy(managed_memory_percent=75),
        _LocalResourcePolicy(spill_percent=80),
    ],
    ids=["unknown-memory", "unknown-spill"],
)
@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_unknown_explicit_percentage_denominator_refuses(policy: _LocalResourcePolicy) -> None:
    with pytest.raises(ValueError, match="(?i)(memory|spill)"):
        _calculate_local_resource_targets(policy, _LocalResourceInputs(), _APPROVED_TUNING)


@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_unknown_capacity_preserves_independent_explicit_fixed_requests() -> None:
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(managed_memory_bytes=1234, spill_bytes=5678, threads=7),
        _LocalResourceInputs(native_memory_bytes=1000, native_threads=3),
        _APPROVED_TUNING,
    )
    assert targets.managed_memory_bytes == 1234
    assert targets.spill_bytes == 5678
    assert targets.threads == 7
    assert targets.reduced_authored_targets == ()


@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_missing_cpu_hint_keeps_native_recommendation() -> None:
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(),
        _LocalResourceInputs(native_threads=8, scratch_free_bytes=101),
        _APPROVED_TUNING,
    )
    assert targets.threads == 8
    assert targets.spill_bytes == 90


@pytest.mark.parametrize(
    ("policy", "expected_memory", "expected_spill"),
    [
        (_LocalResourcePolicy(managed_memory_percent=75, spill_bytes=600), 750, 600),
        (_LocalResourcePolicy(managed_memory_bytes=700, spill_percent=80), 700, 800),
        (_LocalResourcePolicy(spill_percent=80), 500, 800),
        (_LocalResourcePolicy(managed_memory_percent=75), 750, 900),
    ],
)
@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_memory_and_spill_choose_modes_independently(
    policy: _LocalResourcePolicy, expected_memory: int, expected_spill: int
) -> None:
    targets = _calculate_local_resource_targets(
        policy,
        _LocalResourceInputs(
            memory_headroom_bytes=1000,
            scratch_free_bytes=1000,
            scratch_memory_backed=False,
        ),
        _APPROVED_TUNING,
    )
    assert targets.managed_memory_bytes == expected_memory
    assert targets.spill_bytes == expected_spill


@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_zero_percentage_capacity_is_known_zero() -> None:
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(managed_memory_percent=100, spill_percent=100),
        _LocalResourceInputs(
            memory_headroom_bytes=0,
            scratch_free_bytes=0,
            scratch_memory_backed=False,
            cpu_capacity=Fraction(0),
        ),
        _APPROVED_TUNING,
    )
    assert targets.managed_memory_bytes == 0
    assert targets.spill_bytes == 0
    assert targets.threads == 0


@pytest.mark.regression_capture("local-adaptive-resource-targets")
def test_relative_memory_backed_spill_does_not_double_count_capacity() -> None:
    targets = _calculate_local_resource_targets(
        _LocalResourcePolicy(managed_memory_percent=75, spill_percent=100),
        _LocalResourceInputs(
            memory_headroom_bytes=1000,
            scratch_free_bytes=1000,
            scratch_memory_backed=True,
        ),
        _APPROVED_TUNING,
    )
    assert targets.managed_memory_bytes == 750
    assert targets.spill_bytes is not None
    assert 0 <= targets.spill_bytes <= 250
