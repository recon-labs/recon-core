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

from recon_core.adapters._portable_resource_observation import (
    _bounded_integer,
    _observe_portable_resources,
)

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


@dataclass(frozen=True, slots=True)
class _LinuxConstraints:
    memory_headroom_bytes: int | None = None
    cpu_capacity: Fraction | None = None
    memory_incomplete: bool = True
    cpu_incomplete: bool = True
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
            mounts.append(_Mount(root, point, details[0]))
    return tuple(mounts)


def _visible_v2_path(membership: str, mounts: tuple[_Mount, ...]) -> PurePosixPath | None:
    # Only the unified membership is relevant. Never guess a mount root or
    # inspect other controllers or ancestors.
    members = [line[3:] for line in membership.splitlines() if line.startswith("0::")]
    if len(members) != 1:
        return None
    member = _absolute_path(members[0])
    if member is None:
        return None
    matches = [
        mount
        for mount in mounts
        if mount.filesystem == "cgroup2" and member.is_relative_to(mount.root)
    ]
    if len(matches) != 1:
        return None
    mount = matches[0]
    leaf = mount.point / member.relative_to(mount.root)
    # A different mount covering the selected leaf makes the mapping ambiguous.
    if any(
        other != mount
        and other.point.is_relative_to(mount.point)
        and leaf.is_relative_to(other.point)
        for other in mounts
    ):
        return None
    return leaf


def _visible_memory(path: PurePosixPath, read: _Read) -> tuple[int | None, bool]:
    raw = _safe_read(read, path / "memory.max")
    if raw is None:
        return None, True
    if raw.strip() == "max":
        return None, False
    limit = _unsigned(raw)
    usage = _safe_read(read, path / "memory.current")
    current = _unsigned(usage) if usage is not None else None
    if limit is None or current is None:
        return None, True
    return max(0, limit - current), False


def _visible_cpu(path: PurePosixPath, read: _Read) -> tuple[Fraction | None, bool]:
    raw = _safe_read(read, path / "cpu.max")
    parts = raw.split() if raw is not None else []
    if len(parts) != 2:
        return None, True
    quota_text, period_text = parts
    period = _unsigned(period_text)
    if period is None or period == 0:
        return None, True
    if quota_text == "max":
        return None, False
    quota = _unsigned(quota_text)
    if quota is None or quota == 0:
        return None, True
    return Fraction(quota, period), False


def _observe_linux_constraints(
    membership_text: str, mountinfo: str, read: _Read
) -> _LinuxConstraints:
    path = _visible_v2_path(membership_text, _mounts(mountinfo))
    if path is None:
        return _LinuxConstraints()
    memory, memory_incomplete = _visible_memory(path, read)
    cpu, cpu_incomplete = _visible_cpu(path, read)
    return _LinuxConstraints(
        memory_headroom_bytes=memory,
        cpu_capacity=cpu,
        memory_incomplete=memory_incomplete,
        cpu_incomplete=cpu_incomplete,
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
    free = None
    resolved_scratch = None
    if sys.platform == "linux":
        meminfo = _safe_read(_read_text, PurePosixPath("/proc/meminfo"))
        mountinfo = _safe_read(_read_text, PurePosixPath("/proc/self/mountinfo"))
        membership_path = PurePosixPath("/proc/self/cgroup")
        membership = _safe_read(_read_text, membership_path)
        host_available = _parse_available_memory(meminfo) if meminfo is not None else None
        if mountinfo is not None and membership is not None:
            constraints = _observe_linux_constraints(membership, mountinfo, _read_text)
            if membership != _safe_read(_read_text, membership_path):
                constraints = _LinuxConstraints()
    else:
        mountinfo = None
    try:
        resolved = scratch.resolve(strict=True)
        if resolved.is_dir():
            resolved_scratch = resolved
            free = _bounded_integer(shutil.disk_usage(resolved).free)
            if mountinfo is not None:
                scratch_kind = _scratch_memory_backed(PurePosixPath(resolved.as_posix()), mountinfo)
    except (OSError, RuntimeError, ValueError):
        pass
    portable = _observe_portable_resources(resolved_scratch, sys.platform)
    if host_available is None:
        host_available = portable.host_available_bytes
    if sys.platform != "linux":
        scratch_kind = portable.scratch_memory_backed
    return _LocalObservation(
        host_available_bytes=host_available,
        platform_cpu_count=_bounded_integer(os.cpu_count()),
        affinity_count=portable.affinity_count,
        linux_constraints=constraints,
        scratch_free_bytes=free,
        scratch_memory_backed=scratch_kind,
        platform=sys.platform,
    )
