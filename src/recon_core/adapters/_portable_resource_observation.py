"""Optional portable host and process observations, not hard resource guarantees."""

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path, PurePath
from typing import Any

_MAX = (1 << 63) - 1
_DISK_FILESYSTEMS = frozenset({"apfs", "hfs", "hfs+", "hfsplus"})
_MEMORY_FILESYSTEMS = frozenset({"tmpfs", "ramfs", "devtmpfs"})


@dataclass(frozen=True, slots=True)
class _PortableFacts:
    host_available_bytes: int | None = None
    affinity_count: int | None = None
    scratch_memory_backed: bool | None = None
    # These optional hints do not establish the full process resource scope.
    scope_complete: bool = False


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


def _read_portable_facts(provider: Any, platform: str, scratch: PurePath | None) -> _PortableFacts:
    memory = _attempt(lambda: provider.virtual_memory().available)
    affinity = _attempt(lambda: provider.Process().cpu_affinity())
    affinity_count = None
    if (
        isinstance(affinity, tuple | list)
        and affinity
        and all(type(cpu) is int and cpu >= 0 for cpu in affinity)
    ):
        affinity_count = len(set(affinity))

    scratch_kind = None
    if platform == "darwin" and scratch is not None:
        mounts = _attempt(
            lambda: tuple(
                (item.mountpoint, item.fstype) for item in provider.disk_partitions(all=True)
            )
        )
        if mounts is not None:
            scratch_kind = _attempt(lambda: _classify_mounted_filesystem(scratch, mounts))

    return _PortableFacts(
        host_available_bytes=_bounded_integer(memory),
        affinity_count=affinity_count,
        scratch_memory_backed=scratch_kind,
    )


def _load_provider() -> Any:
    return _attempt(lambda: import_module("psutil"))


def _observe_portable_resources(
    scratch: Path | None, platform: str, *, loader: Callable[[], Any] = _load_provider
) -> _PortableFacts:
    provider = _attempt(loader)
    if provider is None:
        return _PortableFacts()
    return _read_portable_facts(provider, platform, scratch)
