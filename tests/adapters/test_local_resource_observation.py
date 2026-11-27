"""Independent local resource observations; no native query or policy decision."""

from collections.abc import Callable
from fractions import Fraction
from pathlib import Path, PurePosixPath

import pytest

from recon_core.adapters._local_resource_observation import (
    _observe_linux_constraints,
    _observe_local_resources,
    _parse_available_memory,
    _scratch_memory_backed,
)

_MOUNTS = (
    "29 20 0:26 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n30 20 8:1 / / rw - ext4 /dev/root rw\n"
)
_MEMBERSHIP = "0::/team/job\n"


def _reader(files: dict[str, str]) -> Callable[[Path], str]:
    def read(path: Path) -> str:
        return files[path.as_posix()]

    return read


def _v2_files() -> dict[str, str]:
    return {
        "/sys/fs/cgroup/team/job/memory.max": "1024",
        "/sys/fs/cgroup/team/job/memory.current": "100",
        "/sys/fs/cgroup/team/memory.max": "2048",
        "/sys/fs/cgroup/team/memory.current": "1900",
        "/sys/fs/cgroup/memory.max": "max",
        "/sys/fs/cgroup/team/job/cpu.max": "max 100000",
        "/sys/fs/cgroup/team/cpu.max": "150000 100000",
        "/sys/fs/cgroup/cpu.max": "max 100000",
        "/sys/fs/cgroup/team/job/cpuset.cpus.effective": "0-3",
    }


@pytest.mark.regression_capture("local-resource-observation-hierarchy")
def test_effective_memory_evidence_visible_headroom() -> None:
    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, _reader(_v2_files()))
    assert result.memory_headroom_bytes == 924
    assert result.cpu_capacity is None
    assert not result.memory_incomplete
    assert not result.cpu_incomplete
    # A visible namespace does not establish that all host ancestors are visible.
    assert not result.full_hierarchy_proven


@pytest.mark.regression_capture("local-resource-observation-hierarchy")
def test_missing_visible_limit_is_not_unlimited() -> None:
    files = _v2_files()
    del files["/sys/fs/cgroup/team/job/memory.current"]
    del files["/sys/fs/cgroup/team/job/cpu.max"]
    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, _reader(files))
    assert result.memory_headroom_bytes is None
    assert result.memory_incomplete
    assert result.cpu_capacity is None
    assert result.cpu_incomplete


def test_effective_memory_evidence_exhaustion() -> None:
    files = _v2_files()
    files["/sys/fs/cgroup/team/job/memory.current"] = "2100"
    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, _reader(files))
    assert result.memory_headroom_bytes == 0


def test_mount_root_and_escaped_path() -> None:
    mounts = r"29 20 0:26 /team /cg\040space rw - cgroup2 cgroup rw" + "\n"
    files = {
        "/cg space/job/memory.max": "100",
        "/cg space/job/memory.current": "50",
        "/cg space/memory.max": "70",
        "/cg space/memory.current": "65",
        "/cg space/job/cpu.max": "100000 100000",
        "/cg space/cpu.max": "max 100000",
        "/cg space/job/cpuset.cpus.effective": "0",
    }
    result = _observe_linux_constraints(_MEMBERSHIP, mounts, _reader(files))
    assert result.memory_headroom_bytes == 50
    assert not result.full_hierarchy_proven


@pytest.mark.parametrize("membership", ["0::/../job\n", "broken", "0::/different/job\n"])
def test_unresolved_cgroup_does_not_guess_mount_root(membership: str) -> None:
    mounts = "29 20 0:26 /team /cg rw - cgroup2 cgroup rw\n"
    result = _observe_linux_constraints(membership, mounts, _reader({}))
    assert result.memory_headroom_bytes is None
    assert result.memory_incomplete
    assert result.cpu_incomplete


@pytest.mark.parametrize("value", ["-1", "oops", "100.0", "9223372036854775808"])
def test_malformed_memory_evidence_is_incomplete(value: str) -> None:
    files = _v2_files()
    files["/sys/fs/cgroup/team/job/memory.max"] = value
    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, _reader(files))
    assert result.memory_headroom_bytes is None
    assert result.memory_incomplete


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MemTotal: 100 kB\nMemAvailable: 20 kB\n", 20480),
        ("MemFree: 20 kB\n", None),
        ("MemAvailable: 0 kB\n", 0),
        ("MemAvailable: 20 MB\n", None),
        ("MemAvailable: -1 kB\n", None),
    ],
)
def test_host_memory_is_available_not_total_or_free(text: str, expected: int | None) -> None:
    assert _parse_available_memory(text) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (PurePosixPath("/tmp/owned"), True),
        (PurePosixPath("/tmp-other/owned"), False),
        (PurePosixPath("/network/owned"), None),
        (PurePosixPath("/unusual/owned"), None),
    ],
)
def test_scratch_filesystem_evidence(path: PurePosixPath, expected: bool | None) -> None:
    mounts = _MOUNTS + (
        "31 20 0:28 / /tmp rw - tmpfs tmpfs rw\n"
        "32 20 0:29 / /network rw - nfs server rw\n"
        "33 20 0:30 / /unusual rw - mystery none rw\n"
    )
    assert _scratch_memory_backed(path, mounts) is expected


def test_memory_high_is_not_a_hard_memory_limit() -> None:
    files = _v2_files()
    files["/sys/fs/cgroup/team/job/memory.high"] = "50"
    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, _reader(files))
    assert result.memory_headroom_bytes == 924


def test_observe_real_scratch_without_creating_files(tmp_path: Path) -> None:
    result = _observe_local_resources(tmp_path)
    assert result.scratch_free_bytes is not None
    assert result.scratch_free_bytes >= 0
    assert result.memory_headroom_bytes is None or result.memory_headroom_bytes >= 0
    assert result.cpu_capacity is None or result.cpu_capacity >= 0
    assert not list(tmp_path.iterdir())
    missing = _observe_local_resources(tmp_path / "missing")
    assert missing.scratch_free_bytes is None
    assert missing.scratch_memory_backed is None
    assert not (tmp_path / "missing").exists()


@pytest.mark.regression_capture("local-resource-observation-hierarchy")
def test_visible_v2_scope_reads_only_matched_membership() -> None:
    files = _v2_files()
    files["/sys/fs/cgroup/team/job/cpu.max"] = "150000 100000"
    seen: list[str] = []

    def read(path: Path) -> str:
        seen.append(path.as_posix())
        return files[path.as_posix()]

    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, read)

    assert result.memory_headroom_bytes == 924
    assert result.cpu_capacity == Fraction(3, 2)
    assert not result.full_hierarchy_proven
    assert set(seen) == {
        "/sys/fs/cgroup/team/job/memory.max",
        "/sys/fs/cgroup/team/job/memory.current",
        "/sys/fs/cgroup/team/job/cpu.max",
    }


@pytest.mark.regression_capture("local-resource-observation-hierarchy")
def test_ambiguous_v2_mount_mapping_does_not_guess() -> None:
    mounts = _MOUNTS + "31 20 0:27 /team /alternate rw - cgroup2 cgroup rw\n"
    seen: list[Path] = []

    def read(path: Path) -> str:
        seen.append(path)
        return "100"

    result = _observe_linux_constraints(_MEMBERSHIP, mounts, read)

    assert result.memory_headroom_bytes is None
    assert result.cpu_capacity is None
    assert result.memory_incomplete
    assert result.cpu_incomplete
    assert not seen


@pytest.mark.regression_capture("local-resource-observation-hierarchy")
def test_v1_controller_is_optional_unknown_not_guessed() -> None:
    mounts = "29 20 0:26 / /cg/mem rw - cgroup cgroup rw,memory\n"
    seen: list[Path] = []

    def read(path: Path) -> str:
        seen.append(path)
        return "100"

    result = _observe_linux_constraints("5:memory:/job\n", mounts, read)

    assert result.memory_headroom_bytes is None
    assert result.cpu_capacity is None
    assert not result.full_hierarchy_proven
    assert not seen


@pytest.mark.parametrize("failure", [PermissionError, FileNotFoundError, ValueError])
@pytest.mark.regression_capture("local-resource-observation-hierarchy")
def test_visible_v2_memory_probe_failure_preserves_cpu(failure: type[Exception]) -> None:
    files = _v2_files()
    files["/sys/fs/cgroup/team/job/cpu.max"] = "25000 100000"

    def read(path: Path) -> str:
        if path.name == "memory.current":
            raise failure("PRIVATE_SENTINEL")
        return files[path.as_posix()]

    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, read)

    assert result.memory_headroom_bytes is None
    assert result.cpu_capacity == Fraction(1, 4)
    assert result.memory_incomplete
    assert not result.full_hierarchy_proven
    assert "PRIVATE_SENTINEL" not in repr(result)


@pytest.mark.parametrize("quota", ["max 100000", "0 100000", "10 0", "bad", "1 -2"])
@pytest.mark.regression_capture("local-resource-observation-hierarchy")
def test_unusable_or_unlimited_cpu_hint_preserves_memory(quota: str) -> None:
    files = _v2_files()
    files["/sys/fs/cgroup/team/job/cpu.max"] = quota
    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, _reader(files))

    assert result.memory_headroom_bytes == 924
    assert result.cpu_capacity is None
    assert not result.full_hierarchy_proven


@pytest.mark.parametrize(
    ("limit", "current", "expected"),
    [
        ("max", "10", None),
        ("100", "100", 0),
        ("100", "101", 0),
        ("100", "30", 70),
        ("broken", "10", None),
    ],
)
@pytest.mark.regression_capture("local-resource-observation-hierarchy")
def test_visible_v2_memory_is_saturated_or_unknown(
    limit: str, current: str, expected: int | None
) -> None:
    files = _v2_files()
    files["/sys/fs/cgroup/team/job/memory.max"] = limit
    files["/sys/fs/cgroup/team/job/memory.current"] = current
    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, _reader(files))

    assert result.memory_headroom_bytes == expected
    assert not result.full_hierarchy_proven
