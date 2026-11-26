"""Private local resource facts, independent of native settings and admission."""

import os
import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Final, TypeVar

_MAX: Final = (1 << 63) - 1
_MOUNT_ESCAPE: Final = re.compile(r"\\(040|011|012|134)")
_MEMORY_FS: Final = frozenset({"tmpfs", "ramfs", "devtmpfs"})
_DISK_FS: Final = frozenset({"ext2", "ext3", "ext4", "xfs", "btrfs", "f2fs", "zfs"})
_Read = Callable[[Path], str]


@dataclass(frozen=True, slots=True)
class _Mount:
    root: PurePosixPath
    point: PurePosixPath
    filesystem: str
    options: frozenset[str]


@dataclass(frozen=True, slots=True)
class _LinuxConstraints:
    memory_headroom_bytes: int | None = None
    cpu_capacity: Fraction | None = None
    cpuset_count: int | None = None
    memory_incomplete: bool = True
    cpu_incomplete: bool = True
    cpuset_incomplete: bool = True
    # Namespace visibility is not proof of the entire host hierarchy.
    full_hierarchy_proven: bool = False


@dataclass(frozen=True, slots=True)
class _LocalObservation:
    """Observed bounds only; unknown and incomplete are not unlimited."""

    host_available_bytes: int | None
    platform_cpu_count: int | None
    affinity_count: int | None
    linux_constraints: _LinuxConstraints | None
    scratch_free_bytes: int | None
    scratch_memory_backed: bool | None
    platform: str

    @property
    def memory_headroom_bytes(self) -> int | None:
        return _minimum(
            self.host_available_bytes,
            self.linux_constraints.memory_headroom_bytes if self.linux_constraints else None,
        )

    @property
    def cpu_capacity(self) -> Fraction | None:
        candidates = (
            Fraction(self.platform_cpu_count) if self.platform_cpu_count is not None else None,
            Fraction(self.affinity_count) if self.affinity_count is not None else None,
            self.linux_constraints.cpu_capacity if self.linux_constraints else None,
            (
                Fraction(self.linux_constraints.cpuset_count)
                if self.linux_constraints and self.linux_constraints.cpuset_count is not None
                else None
            ),
        )
        return _minimum(*candidates)


_T = TypeVar("_T", int, Fraction)


def _minimum(*values: _T | None) -> _T | None:
    known = [value for value in values if value is not None]
    return min(known) if known else None


def _unsigned(value: str) -> int | None:
    text = value.strip()
    if not re.fullmatch(r"[0-9]{1,19}", text):
        return None
    number = int(text)
    return number if number <= _MAX else None


def _safe_read(read: _Read, path: PurePosixPath) -> str | None:
    try:
        return read(Path(str(path)))
    except (OSError, ValueError, KeyError):
        return None


def _absolute_path(value: str) -> PurePosixPath | None:
    path = PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts or "\x00" in value:
        return None
    return path


def _unescape(value: str) -> str:
    return _MOUNT_ESCAPE.sub(lambda match: chr(int(match[1], 8)), value)


def _mounts(text: str) -> tuple[_Mount, ...]:
    mounts = []
    for line in text.splitlines():
        left, sep, right = line.partition(" - ")
        fields, details = left.split(), right.split()
        if not sep or len(fields) < 6 or len(details) != 3:
            continue
        root = _absolute_path(_unescape(fields[3]))
        point = _absolute_path(_unescape(fields[4]))
        if root is not None and point is not None:
            mounts.append(_Mount(root, point, details[0], frozenset(details[2].split(","))))
    return tuple(mounts)


def _membership(text: str) -> dict[str, PurePosixPath]:
    result: dict[str, PurePosixPath] = {}
    for line in text.splitlines():
        fields = line.split(":", 2)
        if len(fields) != 3 or _unsigned(fields[0]) is None:
            return {}
        path = _absolute_path(fields[2])
        if path is None:
            return {}
        for controller in fields[1].split(","):
            if controller in result:
                return {}
            result[controller] = path
    return result


def _controller_paths(
    controller: str, membership: dict[str, PurePosixPath], mounts: tuple[_Mount, ...]
) -> tuple[bool, tuple[PurePosixPath, ...]]:
    unified = controller not in membership
    member = membership.get("" if unified else controller)
    if member is None:
        return unified, ()
    matches = [
        mount
        for mount in mounts
        if member.is_relative_to(mount.root)
        and (
            mount.filesystem == "cgroup2"
            if unified
            else mount.filesystem == "cgroup" and controller in mount.options
        )
    ]
    if not matches:
        return unified, ()
    # The broadest visible root exposes the greatest number of ancestors.
    mount = min(matches, key=lambda item: len(item.root.parts))
    leaf = mount.point / member.relative_to(mount.root)
    return unified, (leaf, *(p for p in leaf.parents if p.is_relative_to(mount.point)))


def _memory_limits(
    unified: bool, paths: tuple[PurePosixPath, ...], read: _Read, page_size: int
) -> tuple[int | None, bool]:
    headroom = None
    incomplete = not paths
    for path in paths:
        limit_text = _safe_read(read, path / ("memory.max" if unified else "memory.limit_in_bytes"))
        if limit_text is None:
            incomplete = True
            continue
        if unified and limit_text.strip() == "max":
            continue
        limit = _unsigned(limit_text)
        if limit is None:
            incomplete = True
            continue
        if not unified and page_size > 0 and limit >= (_MAX // page_size) * page_size:
            continue
        current_text = _safe_read(
            read, path / ("memory.current" if unified else "memory.usage_in_bytes")
        )
        current = _unsigned(current_text) if current_text is not None else None
        if current is None:
            incomplete = True
            continue
        headroom = _minimum(headroom, max(0, limit - current))
    return headroom, incomplete


def _cpu_limits(
    unified: bool, paths: tuple[PurePosixPath, ...], read: _Read
) -> tuple[Fraction | None, bool]:
    capacity = None
    incomplete = not paths
    for path in paths:
        if unified:
            raw = _safe_read(read, path / "cpu.max")
            parts = raw.split() if raw is not None else []
            if len(parts) != 2:
                incomplete = True
                continue
            quota_text, period_text = parts
        else:
            quota_text = _safe_read(read, path / "cpu.cfs_quota_us") or ""
            period_text = _safe_read(read, path / "cpu.cfs_period_us") or ""
        period = _unsigned(period_text)
        if period is None or period == 0:
            incomplete = True
            continue
        if quota_text.strip() == ("max" if unified else "-1"):
            continue
        quota = _unsigned(quota_text)
        if quota is None:
            incomplete = True
            continue
        capacity = _minimum(capacity, Fraction(quota, period))
    return capacity, incomplete


def _parse_cpu_set(value: str) -> int | None:
    ranges = []
    for item in value.strip().split(","):
        parts = item.split("-")
        if len(parts) not in {1, 2}:
            return None
        start, end = _unsigned(parts[0]), _unsigned(parts[-1])
        if start is None or end is None or start > end:
            return None
        ranges.append((start, end))
    # Count the union without allocating a set proportional to CPU IDs.
    count = 0
    previous_end = -1
    for start, end in sorted(ranges):
        count += max(0, end - max(start, previous_end + 1) + 1)
        previous_end = max(previous_end, end)
    return count


def _observe_linux_constraints(
    membership_text: str, mountinfo: str, read: _Read, page_size: int
) -> _LinuxConstraints:
    membership, mounts = _membership(membership_text), _mounts(mountinfo)
    memory_v2, memory_paths = _controller_paths("memory", membership, mounts)
    cpu_v2, cpu_paths = _controller_paths("cpu", membership, mounts)
    cpuset_v2, cpuset_paths = _controller_paths("cpuset", membership, mounts)
    memory, memory_incomplete = _memory_limits(memory_v2, memory_paths, read, page_size)
    cpu, cpu_incomplete = _cpu_limits(cpu_v2, cpu_paths, read)
    cpuset = None
    if cpuset_paths:
        name = "cpuset.cpus.effective" if cpuset_v2 else "cpuset.effective_cpus"
        raw = _safe_read(read, cpuset_paths[0] / name)
        cpuset = _parse_cpu_set(raw) if raw is not None else None
    return _LinuxConstraints(
        memory_headroom_bytes=memory,
        cpu_capacity=cpu,
        cpuset_count=cpuset,
        memory_incomplete=memory_incomplete,
        cpu_incomplete=cpu_incomplete,
        cpuset_incomplete=cpuset is None,
    )


def _parse_available_memory(text: str) -> int | None:
    values = [line.split() for line in text.splitlines() if line.startswith("MemAvailable:")]
    if len(values) != 1 or len(values[0]) != 3 or values[0][2] != "kB":
        return None
    amount = _unsigned(values[0][1])
    return amount * 1024 if amount is not None and amount <= _MAX // 1024 else None


def _scratch_memory_backed(path: PurePosixPath, mountinfo: str) -> bool | None:
    posix = PurePosixPath(path.as_posix())
    matches = [mount for mount in _mounts(mountinfo) if posix.is_relative_to(mount.point)]
    if not matches:
        return None
    length = max(len(mount.point.parts) for mount in matches)
    kinds = {mount.filesystem for mount in matches if len(mount.point.parts) == length}
    if kinds <= _MEMORY_FS:
        return True
    if kinds <= _DISK_FS:
        return False
    # Overlay, network and unknown filesystems are not proven disk-backed.
    return None


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _observe_local_resources(scratch: Path) -> _LocalObservation:
    """Observe the current process and actual existing scratch filesystem."""

    host_available = None
    constraints = None
    scratch_kind = None
    affinity = None
    free = None
    if sys.platform == "linux":
        meminfo = _safe_read(_read_text, PurePosixPath("/proc/meminfo"))
        mountinfo = _safe_read(_read_text, PurePosixPath("/proc/self/mountinfo"))
        membership_path = PurePosixPath("/proc/self/cgroup")
        membership = _safe_read(_read_text, membership_path)
        host_available = _parse_available_memory(meminfo) if meminfo is not None else None
        if mountinfo is not None and membership is not None:
            constraints = _observe_linux_constraints(
                membership, mountinfo, _read_text, os.sysconf("SC_PAGE_SIZE")
            )
            if membership != _safe_read(_read_text, membership_path):
                constraints = _LinuxConstraints()
        try:
            affinity = len(os.sched_getaffinity(0))
        except OSError:
            pass
    else:
        mountinfo = None
    try:
        resolved = scratch.resolve(strict=True)
        if resolved.is_dir():
            free = shutil.disk_usage(resolved).free
            if mountinfo is not None:
                scratch_kind = _scratch_memory_backed(resolved, mountinfo)
    except (OSError, RuntimeError, ValueError):
        pass
    return _LocalObservation(
        host_available_bytes=host_available,
        platform_cpu_count=os.cpu_count(),
        affinity_count=affinity,
        linux_constraints=constraints,
        scratch_free_bytes=free,
        scratch_memory_backed=scratch_kind,
        platform=sys.platform,
    )
