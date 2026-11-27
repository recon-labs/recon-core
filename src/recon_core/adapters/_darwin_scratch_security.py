"""Targeted Darwin ACL verification for newly created private scratch."""

import ctypes as ct
import errno
import os
import stat
from pathlib import Path


def _darwin_no_acl_grants(path: Path, expected: os.stat_result, *, fd: int | None = None) -> bool:
    """Require absent or non-granting Darwin ACL on an unchanged open object."""
    try:
        if fd is None:
            return _darwin_no_acl_grants_native(path, expected)
        return _darwin_no_acl_grants_native(path, expected, fd=fd)
    except Exception:
        return False


def _darwin_no_acl_grants_native(
    path: Path, expected: os.stat_result, *, fd: int | None = None
) -> bool:
    libc = ct.CDLL(None, use_errno=True)
    get_acl = libc.acl_get_fd_np
    get_acl.argtypes = [ct.c_int, ct.c_int]
    get_acl.restype = ct.c_void_p
    valid = libc.acl_valid
    valid.argtypes = [ct.c_void_p]
    valid.restype = ct.c_int
    get_entry = libc.acl_get_entry
    get_entry.argtypes = [ct.c_void_p, ct.c_int, ct.POINTER(ct.c_void_p)]
    get_entry.restype = ct.c_int
    get_tag = libc.acl_get_tag_type
    get_tag.argtypes = [ct.c_void_p, ct.POINTER(ct.c_int)]
    get_tag.restype = ct.c_int
    free = libc.acl_free
    free.argtypes = [ct.c_void_p]
    free.restype = ct.c_int

    def identity(info: os.stat_result) -> tuple[int, ...]:
        links = info.st_nlink if stat.S_ISREG(info.st_mode) else 0
        return info.st_dev, info.st_ino, info.st_uid, info.st_mode, links

    own_fd = fd is None
    if fd is None:
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        if stat.S_ISDIR(expected.st_mode):
            flags |= os.O_DIRECTORY
        fd = os.open(path, flags)
    try:
        if identity(os.fstat(fd)) != identity(expected):
            return False
        ct.set_errno(0)
        acl = get_acl(fd, 0x100)  # ACL_TYPE_EXTENDED
        if acl is None:
            # On a verified existing Darwin fd, the native filesec ACL
            # property returns ENOENT for absence. Other errors are unknown.
            safe = ct.get_errno() == errno.ENOENT
        elif acl in (1, ct.c_void_p(-1).value):
            return False
        else:
            try:
                if valid(acl) != 0:
                    return False
                entry_id = 0  # ACL_FIRST_ENTRY
                while True:
                    entry = ct.c_void_p()
                    ct.set_errno(0)
                    if get_entry(acl, entry_id, ct.byref(entry)) != 0:
                        # Darwin returns EINVAL at end of a valid ACL.
                        safe = ct.get_errno() == errno.EINVAL
                        break
                    tag = ct.c_int()
                    if not entry or get_tag(entry, ct.byref(tag)) != 0 or tag.value != 2:
                        # Only ACL_EXTENDED_DENY cannot add permissions.
                        return False
                    entry_id = -1  # ACL_NEXT_ENTRY
            finally:
                free(acl)
        return (
            safe
            and identity(os.fstat(fd)) == identity(expected)
            and identity(path.lstat()) == identity(expected)
        )
    finally:
        if own_fd:
            os.close(fd)
