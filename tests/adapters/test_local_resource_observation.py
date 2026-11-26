"""Independent local resource observations; no native query or policy decision."""

from fractions import Fraction
from pathlib import Path

import pytest

from recon_core.adapters._local_resource_observation import (
    _observe_linux_constraints,
    _parse_available_memory,
    _parse_cpu_set,
    _scratch_memory_backed,
)

_MOUNTS = (
    "29 20 0:26 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n"
    "30 20 8:1 / / rw - ext4 /dev/root rw\n"
)
_MEMBERSHIP = "0::/team/job\n"


def _reader(files: dict[str, str]):
    def read(path: Path) -> str:
        return files[str(path)]

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
def test_effective_memory_evidence_ancestor_headroom() -> None:
    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, _reader(_v2_files()), 4096)
    assert result.memory_headroom_bytes == 148
    assert result.cpu_capacity == Fraction(3, 2)
    assert result.cpuset_count == 4
    assert not result.memory_incomplete
    assert not result.cpu_incomplete
    assert not result.cpuset_incomplete
    # A visible namespace does not establish that all host ancestors are visible.
    assert not result.full_hierarchy_proven


@pytest.mark.regression_capture("local-resource-observation-hierarchy")
def test_missing_ancestor_is_not_unlimited() -> None:
    files = _v2_files()
    del files["/sys/fs/cgroup/team/memory.current"]
    del files["/sys/fs/cgroup/team/cpu.max"]
    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, _reader(files), 4096)
    assert result.memory_headroom_bytes == 924
    assert result.memory_incomplete
    assert result.cpu_capacity is None
    assert result.cpu_incomplete


def test_effective_memory_evidence_exhaustion() -> None:
    files = _v2_files()
    files["/sys/fs/cgroup/team/memory.current"] = "2100"
    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, _reader(files), 4096)
    assert result.memory_headroom_bytes == 0


def test_v1_separate_controllers_and_unlimited_sentinel() -> None:
    mounts = (
        "29 20 0:26 / /cg/mem rw - cgroup cgroup rw,memory\n"
        "30 20 0:27 / /cg/cpu rw - cgroup cgroup rw,cpu,cpuacct\n"
        "31 20 0:28 / /cg/set rw - cgroup cgroup rw,cpuset\n"
    )
    membership = "5:memory:/job\n4:cpu,cpuacct:/job\n3:cpuset:/job\n"
    files = {
        "/cg/mem/job/memory.limit_in_bytes": "1000",
        "/cg/mem/job/memory.usage_in_bytes": "400",
        "/cg/mem/memory.limit_in_bytes": str((1 << 63) - 4096),
        "/cg/cpu/job/cpu.cfs_quota_us": "50000",
        "/cg/cpu/job/cpu.cfs_period_us": "100000",
        "/cg/cpu/cpu.cfs_quota_us": "-1",
        "/cg/cpu/cpu.cfs_period_us": "100000",
        "/cg/set/job/cpuset.effective_cpus": "2-3",
    }
    result = _observe_linux_constraints(membership, mounts, _reader(files), 4096)
    assert result.memory_headroom_bytes == 600
    assert result.cpu_capacity == Fraction(1, 2)
    assert result.cpuset_count == 2


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
    result = _observe_linux_constraints(_MEMBERSHIP, mounts, _reader(files), 4096)
    assert result.memory_headroom_bytes == 5
    assert not result.full_hierarchy_proven


@pytest.mark.parametrize("membership", ["0::/../job\n", "broken", "0::/different/job\n"])
def test_unresolved_cgroup_does_not_guess_mount_root(membership: str) -> None:
    mounts = "29 20 0:26 /team /cg rw - cgroup2 cgroup rw\n"
    result = _observe_linux_constraints(membership, mounts, _reader({}), 4096)
    assert result.memory_headroom_bytes is None
    assert result.memory_incomplete
    assert result.cpu_incomplete


@pytest.mark.parametrize("value", ["-1", "oops", "100.0", "9223372036854775808"])
def test_malformed_memory_evidence_is_incomplete(value: str) -> None:
    files = _v2_files()
    files["/sys/fs/cgroup/team/memory.max"] = value
    result = _observe_linux_constraints(_MEMBERSHIP, _MOUNTS, _reader(files), 4096)
    assert result.memory_headroom_bytes == 924
    assert result.memory_incomplete


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0-3,8,10-11", 7), ("0-3,2-5", 6), ("", None), ("2-1", None), ("0,x", None), ("-1", None)],
)
def test_effective_cpu_evidence_cpuset(value: str, expected: int | None) -> None:
    assert _parse_cpu_set(value) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [("MemTotal: 100 kB\nMemAvailable: 20 kB\n", 20480),
     ("MemFree: 20 kB\n", None), ("MemAvailable: 0 kB\n", 0),
     ("MemAvailable: 20 MB\n", None), ("MemAvailable: -1 kB\n", None)],
)
def test_host_memory_is_available_not_total_or_free(text: str, expected: int | None) -> None:
    assert _parse_available_memory(text) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [(Path("/tmp/owned"), True), (Path("/tmp-other/owned"), False),
     (Path("/network/owned"), None), (Path("/unusual/owned"), None)],
)
def test_scratch_filesystem_evidence(path: Path, expected: bool | None) -> None:
    mounts = _MOUNTS + (
        "31 20 0:28 / /tmp rw - tmpfs tmpfs rw\n"
        "32 20 0:29 / /network rw - nfs server rw\n"
        "33 20 0:30 / /unusual rw - mystery none rw\n"
    )
    assert _scratch_memory_backed(path, mounts) is expected
