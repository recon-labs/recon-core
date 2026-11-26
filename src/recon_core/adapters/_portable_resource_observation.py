"""Optional portable host and process observations, not hard resource guarantees."""

import ctypes
from collections.abc import Callable
from dataclasses import dataclass, replace
from importlib import import_module
from pathlib import Path, PurePath
from typing import Any

_MAX = (1 << 63) - 1
_DISK_FILESYSTEMS = frozenset({"apfs", "hfs", "hfs+", "hfsplus"})
_MEMORY_FILESYSTEMS = frozenset({"tmpfs", "ramfs", "devtmpfs"})


@dataclass(frozen=True, slots=True)
class _WindowsScope:
    """Read-only immediate-job evidence, not the complete nested-job hierarchy."""

    in_job: bool | None = None
    processor_group_count: int | None = None
    process_commit_limit_bytes: int | None = None
    job_commit_limit_bytes: int | None = None
    cpu_hard_rate: int | None = None


@dataclass(frozen=True, slots=True)
class _PortableFacts:
    host_available_bytes: int | None = None
    affinity_count: int | None = None
    process_rss_bytes: int | None = None
    process_virtual_bytes: int | None = None
    process_private_commit_bytes: int | None = None
    scratch_memory_backed: bool | None = None
    windows_scope: _WindowsScope | None = None
    process_address_space_limit_bytes: int | None = None
    process_data_limit_bytes: int | None = None
    # Neither host availability nor immediate-job evidence proves all limits.
    scope_complete: bool = False

    @property
    def process_commit_headroom_bytes(self) -> int | None:
        if self.windows_scope is None:
            return None
        limit = self.windows_scope.process_commit_limit_bytes
        current = self.process_private_commit_bytes
        if limit is None or current is None:
            return None
        return max(0, limit - current)


def _bounded_integer(value: object) -> int | None:
    return value if type(value) is int and 0 <= value <= _MAX else None


def _attempt(operation: Callable[[], Any]) -> Any:
    # Optional observation APIs can fail independently (including permission
    # and unsupported-platform errors). Never expose provider exception text.
    try:
        return operation()
    except Exception:
        return None


def _classify_mounted_filesystem(
    path: PurePath, mounts: tuple[tuple[str, str], ...]
) -> bool | None:
    matches: list[tuple[int, str]] = []
    for name, kind in mounts:
        mount = type(path)(name)
        if mount.is_absolute() and path.is_relative_to(mount):
            matches.append((len(mount.parts), kind.lower()))
    if not matches:
        return None
    depth = max(length for length, _ in matches)
    kinds = {kind for length, kind in matches if length == depth}
    if kinds <= _MEMORY_FILESYSTEMS:
        return True
    if kinds <= _DISK_FILESYSTEMS:
        # Filesystem type is advisory evidence, not physical backing or quota.
        return False
    return None


def _windows_drive_kind(kind: int | None) -> bool | None:
    if kind == 6:  # DRIVE_RAMDISK
        return True
    if kind in {2, 3}:  # DRIVE_REMOVABLE, DRIVE_FIXED
        return False
    return None


def _read_portable_facts(
    provider: Any,
    platform: str,
    scratch: PurePath | None,
    *,
    windows_scope: _WindowsScope | None = None,
    windows_drive: int | None = None,
) -> _PortableFacts:
    memory = _attempt(lambda: provider.virtual_memory().available)
    process = _attempt(provider.Process)
    info = _attempt(lambda: process.memory_info())
    affinity = _attempt(lambda: process.cpu_affinity())
    affinity_count = None
    if isinstance(affinity, (tuple, list)) and all(
        type(cpu) is int and cpu >= 0 for cpu in affinity
    ):
        affinity_count = len(set(affinity))
    if platform == "win32":
        # Single-group affinity cannot represent a multi-group process.
        if windows_scope is None or windows_scope.processor_group_count != 1:
            affinity_count = None
        scratch_kind = _windows_drive_kind(windows_drive)
    elif platform == "darwin":
        mounts = _attempt(
            lambda: tuple(
                (item.mountpoint, item.fstype) for item in provider.disk_partitions(all=True)
            )
        )
        scratch_kind = (
            _classify_mounted_filesystem(scratch, mounts)
            if mounts is not None and scratch is not None
            else None
        )
    else:
        scratch_kind = None
    return _PortableFacts(
        host_available_bytes=_bounded_integer(memory),
        affinity_count=affinity_count,
        process_rss_bytes=_bounded_integer(getattr(info, "rss", None)),
        process_virtual_bytes=(
            _bounded_integer(getattr(info, "vms", None)) if platform != "win32" else None
        ),
        process_private_commit_bytes=(
            _bounded_integer(getattr(info, "private", None)) if platform == "win32" else None
        ),
        scratch_memory_backed=scratch_kind,
        windows_scope=windows_scope,
    )


class _BasicJobLimits(ctypes.Structure):
    _fields_ = [
        ("process_time", ctypes.c_int64),
        ("job_time", ctypes.c_int64),
        ("flags", ctypes.c_uint32),
        ("min_working_set", ctypes.c_size_t),
        ("max_working_set", ctypes.c_size_t),
        ("active_process_limit", ctypes.c_uint32),
        ("affinity", ctypes.c_size_t),
        ("priority_class", ctypes.c_uint32),
        ("scheduling_class", ctypes.c_uint32),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "read_ops",
            "write_ops",
            "other_ops",
            "read_bytes",
            "write_bytes",
            "other_bytes",
        )
    ]


class _ExtendedJobLimits(ctypes.Structure):
    _fields_ = [
        ("basic", _BasicJobLimits),
        ("io", _IoCounters),
        ("process_limit", ctypes.c_size_t),
        ("job_limit", ctypes.c_size_t),
        ("peak_process", ctypes.c_size_t),
        ("peak_job", ctypes.c_size_t),
    ]


def _windows_scope(kernel: Any) -> _WindowsScope:
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    process = kernel.GetCurrentProcess()
    kernel.IsProcessInJob.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
    ]
    in_job = ctypes.c_int()
    membership = (
        bool(in_job.value) if kernel.IsProcessInJob(process, None, ctypes.byref(in_job)) else None
    )
    kernel.GetActiveProcessorGroupCount.restype = ctypes.c_uint16
    groups = kernel.GetActiveProcessorGroupCount()
    group_count = None
    if groups > 0:
        count = ctypes.c_uint16(groups)
        buffer = (ctypes.c_uint16 * groups)()
        kernel.GetProcessGroupAffinity.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(ctypes.c_uint16),
        ]
        if kernel.GetProcessGroupAffinity(process, ctypes.byref(count), buffer):
            group_count = count.value
    process_limit = job_limit = cpu_rate = None
    if membership is True:
        query = kernel.QueryInformationJobObject
        query.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        limits = _ExtendedJobLimits()
        if query(None, 9, ctypes.byref(limits), ctypes.sizeof(limits), None):
            if limits.basic.flags & 0x100:
                process_limit = _bounded_integer(limits.process_limit)
            if limits.basic.flags & 0x200:
                job_limit = _bounded_integer(limits.job_limit)
        rate = (ctypes.c_uint32 * 2)()
        if (
            query(None, 15, ctypes.byref(rate), ctypes.sizeof(rate), None)
            and rate[0] & 0x5 == 0x5
            and 0 < rate[1] <= 10000
        ):
            cpu_rate = rate[1]
    return _WindowsScope(
        in_job=membership,
        processor_group_count=group_count,
        process_commit_limit_bytes=process_limit,
        job_commit_limit_bytes=job_limit,
        cpu_hard_rate=cpu_rate,
    )


def _windows_drive(kernel: Any, scratch: Path) -> int | None:
    # Resolve the actual volume mount point, not just the drive letter.
    root = ctypes.create_unicode_buffer(32768)
    kernel.GetVolumePathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    if not kernel.GetVolumePathNameW(str(scratch), root, len(root)):
        return None
    kernel.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
    return _bounded_integer(kernel.GetDriveTypeW(root))


def _load_provider() -> Any:
    return _attempt(lambda: import_module("psutil"))


def _finite_rlimit(resource: Any, name: str) -> int | None:
    value = _attempt(lambda: resource.getrlimit(getattr(resource, name))[0])
    return None if value == resource.RLIM_INFINITY else _bounded_integer(value)


def _observe_portable_resources(
    scratch: Path | None, platform: str, *, loader: Callable[[], Any] = _load_provider
) -> _PortableFacts:
    provider = _attempt(loader)
    if provider is None:
        return _PortableFacts()
    scope = drive = None
    if platform == "win32":
        kernel = _attempt(lambda: import_module("ctypes").WinDLL("kernel32"))
        if kernel is not None:
            scope = _attempt(lambda: _windows_scope(kernel))
            if scratch is not None:
                drive = _attempt(lambda: _windows_drive(kernel, scratch))
    facts = _read_portable_facts(
        provider, platform, scratch, windows_scope=scope, windows_drive=drive
    )
    if platform == "darwin":
        resource = _attempt(lambda: import_module("resource"))
        if resource is not None:
            facts = replace(
                facts,
                process_address_space_limit_bytes=_finite_rlimit(resource, "RLIMIT_AS"),
                process_data_limit_bytes=_finite_rlimit(resource, "RLIMIT_DATA"),
            )
    return facts
