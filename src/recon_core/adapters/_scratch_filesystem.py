"""Handle-bound scratch filesystem facts, not admission or quota proof."""

import ctypes as ct
import os
import re
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from recon_core.adapters._windows_scratch_security import _api, _libraries

# Local Linux implementations for which kernel ownership and local flock
# semantics are known. Unknown/stacked filesystems need equivalent evidence;
# this is not a list of supported OS versions or a runtime admission rule.
_LINUX_LOCAL: Final = frozenset({"ext2", "ext3", "ext4", "xfs", "btrfs", "f2fs", "tmpfs"})
_LINUX_REMOTE: Final = frozenset({"nfs", "nfs4", "cifs", "smb3", "9p", "ceph"})


@dataclass(frozen=True, slots=True)
class _FilesystemEvidence:
    local_candidate: bool | None = None
    ownership_supported: bool | None = None
    writable: bool | None = None
    filesystem: str | None = None
    # Native mount/volume identity is only meaningful in its observation
    # scope. Never include it or source paths in user diagnostics.
    mount_identity: tuple[int, ...] | None = field(default=None, repr=False)


def _linux_mount_evidence(
    fdinfo: str, mountinfo: str, device: tuple[int, int]
) -> _FilesystemEvidence:
    ids = [
        line.partition(":")[2].strip() for line in fdinfo.splitlines() if line.startswith("mnt_id:")
    ]
    if len(ids) != 1 or not re.fullmatch(r"[0-9]{1,20}", ids[0]):
        return _FilesystemEvidence()
    matches = []
    for line in mountinfo.splitlines():
        left, sep, right = line.partition(" - ")
        fields, details = left.split(), right.split()
        if fields and fields[0] == ids[0]:
            if not sep or len(fields) < 6 or len(details) != 3:
                return _FilesystemEvidence()
            matches.append((fields, details))
    if len(matches) != 1:
        return _FilesystemEvidence()
    fields, details = matches[0]
    if fields[2] != f"{device[0]}:{device[1]}":
        return _FilesystemEvidence()
    options = set(fields[5].split(",")) | set(details[2].split(","))
    kind = details[0]
    local = True if kind in _LINUX_LOCAL else False if kind in _LINUX_REMOTE else None
    writable = False if "ro" in options else True if "rw" in options else None
    return _FilesystemEvidence(
        local_candidate=local,
        ownership_supported=True if local is True else None,
        writable=writable,
        filesystem=kind,
        mount_identity=(int(ids[0]),),
    )


def _linux_facts(fd: int, info: os.stat_result) -> _FilesystemEvidence:
    fdinfo = Path(f"/proc/self/fdinfo/{fd}").read_text(encoding="utf-8")
    mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    facts = _linux_mount_evidence(fdinfo, mountinfo, (os.major(info.st_dev), os.minor(info.st_dev)))
    # A remount or disappearing namespace cannot establish stable evidence.
    if fdinfo != Path(f"/proc/self/fdinfo/{fd}").read_text(encoding="utf-8"):
        return _FilesystemEvidence()
    return facts


class _DarwinStatfs(ct.Structure):
    """Darwin 64-bit inode statfs ABI; current arm64 and x86_64."""

    _fields_ = [
        ("block_size", ct.c_uint32),
        ("io_size", ct.c_int32),
        ("blocks", ct.c_uint64),
        ("free", ct.c_uint64),
        ("available", ct.c_uint64),
        ("files", ct.c_uint64),
        ("files_free", ct.c_uint64),
        ("fsid", ct.c_int32 * 2),
        ("owner", ct.c_uint32),
        ("kind", ct.c_uint32),
        ("flags", ct.c_uint32),
        ("subtype", ct.c_uint32),
        ("name", ct.c_char * 16),
        ("mountpoint", ct.c_char * 1024),
        ("source", ct.c_char * 1024),
        ("reserved", ct.c_uint32 * 8),
    ]


def _darwin_facts(fd: int, info: os.stat_result) -> _FilesystemEvidence:
    if ct.sizeof(ct.c_void_p) != 8:
        return _FilesystemEvidence()
    libc = ct.CDLL(None, use_errno=True)
    # On Intel, the unsuffixed legacy ABI can differ. The explicit
    # 64-bit-inode symbol is preferable where it is exported.
    function = getattr(libc, "fstatfs$INODE64", None)
    if function is None:
        import platform

        if platform.machine() != "arm64":
            return _FilesystemEvidence()
        function = libc.fstatfs
    function.argtypes = [ct.c_int, ct.POINTER(_DarwinStatfs)]
    function.restype = ct.c_int
    data = _DarwinStatfs()
    if function(fd, ct.byref(data)) != 0:
        return _FilesystemEvidence()
    kind = data.name.decode("ascii")
    if not kind or data.block_size == 0 or not data.mountpoint.startswith(b"/"):
        return _FilesystemEvidence()
    local = bool(data.flags & 0x1000)  # MNT_LOCAL
    ownership = not bool(data.flags & 0x200000)  # MNT_IGNORE_OWNERSHIP
    return _FilesystemEvidence(
        local_candidate=local,
        ownership_supported=ownership,
        writable=not bool(data.flags & 1),  # MNT_RDONLY
        filesystem=kind,
        mount_identity=(info.st_dev, *data.fsid),
    )


def _windows_facts(path: Path) -> _FilesystemEvidence:
    from ctypes import wintypes as wt

    kernel, _ = _libraries()
    open_file = _api(
        kernel,
        "CreateFileW",
        wt.HANDLE,
        wt.LPCWSTR,
        wt.DWORD,
        wt.DWORD,
        ct.c_void_p,
        wt.DWORD,
        wt.DWORD,
        wt.HANDLE,
    )
    close = _api(kernel, "CloseHandle", wt.BOOL, wt.HANDLE)
    volume = _api(
        kernel,
        "GetVolumeInformationByHandleW",
        wt.BOOL,
        wt.HANDLE,
        wt.LPWSTR,
        wt.DWORD,
        ct.POINTER(wt.DWORD),
        ct.POINTER(wt.DWORD),
        ct.POINTER(wt.DWORD),
        wt.LPWSTR,
        wt.DWORD,
    )
    final_name = _api(
        kernel, "GetFinalPathNameByHandleW", wt.DWORD, wt.HANDLE, wt.LPWSTR, wt.DWORD, wt.DWORD
    )
    drive_type = _api(kernel, "GetDriveTypeW", wt.UINT, wt.LPCWSTR)
    handle = open_file(str(path), 0x80, 3, None, 3, 0x02200000, None)
    if handle in (None, ct.c_void_p(-1).value):
        return _FilesystemEvidence()
    try:
        flags, serial = wt.DWORD(), wt.DWORD()
        kind = ct.create_unicode_buffer(256)
        if not volume(handle, None, 0, ct.byref(serial), None, ct.byref(flags), kind, len(kind)):
            return _FilesystemEvidence()
        name = ct.create_unicode_buffer(32768)
        length = final_name(handle, name, len(name), 1)
        # Mount-manager GUID volume paths are not provided for SMB. A
        # missing GUID does not itself establish that a volume is remote.
        from uuid import UUID

        match = re.match(r"^\\\\\?\\Volume\{([0-9a-fA-F-]{36})\}\\", name.value)
        identity = None
        local = None
        if 0 < length < len(name) and match is not None:
            identity = (UUID(match[1]).int, serial.value)
            kind_of_drive = drive_type(match[0])
            if kind_of_drive in (2, 3, 6):
                local = True
            elif kind_of_drive == 4:
                local = False
        return _FilesystemEvidence(
            local_candidate=local,
            ownership_supported=bool(flags.value & 8),  # FILE_PERSISTENT_ACLS
            writable=not bool(flags.value & 0x80000),  # FILE_READ_ONLY_VOLUME
            filesystem=kind.value or None,
            mount_identity=identity,
        )
    finally:
        close(handle)


def _observe_scratch_filesystem(path: Path) -> _FilesystemEvidence:
    """Read actual existing directory facts without writing or probing data."""
    try:
        before = path.lstat()
        if (
            not path.is_absolute()
            or path.resolve(strict=True) != path
            or not stat.S_ISDIR(before.st_mode)
            or getattr(before, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            return _FilesystemEvidence()
        if sys.platform == "win32":
            facts = _windows_facts(path)
        elif sys.platform in ("linux", "darwin"):
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                info = os.fstat(fd)
                if (info.st_dev, info.st_ino) != (before.st_dev, before.st_ino):
                    return _FilesystemEvidence()
                facts = (
                    _linux_facts(fd, info) if sys.platform == "linux" else _darwin_facts(fd, info)
                )
            finally:
                os.close(fd)
        else:
            return _FilesystemEvidence()
        after = path.lstat()
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            return _FilesystemEvidence()
        return facts
    except Exception:
        return _FilesystemEvidence()
