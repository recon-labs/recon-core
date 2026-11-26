"""Private stable scratch namespace and directory qualification candidate.

This composes opened-directory filesystem facts and native directory privacy
with the existing lease coordinator. It is not yet production admission:
Full native ticket identity, equivalent providers
for other filesystems and worker-owned qualification remain prerequisites.
"""

import ctypes as ct
import errno
import hashlib
import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path

from recon_core.adapters._resource_scratch import _RootExistsError, _ScratchRoot
from recon_core.adapters._scratch_filesystem import (
    _FilesystemEvidence,
    _observe_posix_file_filesystem,
    _observe_scratch_filesystem,
)
from recon_core.adapters._windows_scratch_security import (
    _create_private_directory,
    _libraries,
    _process_user,
    _verify_ancestor_directory,
    _verify_private_directory,
    _verify_private_file,
)


class _NamespaceError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Private scratch namespace could not be verified.")


def _user_identity() -> bytes:
    if os.name == "posix":
        uid = os.getuid()
        if uid != os.geteuid():
            raise _NamespaceError()
        return f"posix:{uid}".encode("ascii")
    if os.name == "nt":
        kernel, security = _libraries()
        with _process_user(kernel, security) as (_, sid):
            return f"windows:{sid}".encode("ascii")
    raise _NamespaceError()


def _namespace_path(base: Path, project: Path) -> Path:
    """Stable scope from canonical project location and native user identity."""
    if not base.is_absolute() or base.resolve(strict=True) != base:
        raise _NamespaceError()
    canonical = project.resolve(strict=True)
    if not canonical.is_dir():
        raise _NamespaceError()
    digest = hashlib.sha256(b"recon-scratch-v1\0" + _user_identity())
    digest.update(b"\0")
    digest.update(os.fsencode(canonical))
    return base / ("recon-scratch-" + digest.hexdigest())


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


def _directory_info(path: Path) -> os.stat_result:
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or path.resolve(strict=True) != path
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise _NamespaceError()
    return info


def _posix_ancestor_check(path: Path) -> None:
    """Trusted owner and protected rename boundary for cooperative local use."""
    uid = os.geteuid()
    for ancestor in (path, *path.parents):
        info = _directory_info(ancestor)
        if info.st_uid not in (0, uid):
            raise _NamespaceError()
        if info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX:
            raise _NamespaceError()
        # Darwin extended ACL grants can exceed traditional mode permissions.
        if sys.platform == "darwin" and not _darwin_no_acl_grants(ancestor, info):
            raise _NamespaceError()


def _usable(facts: _FilesystemEvidence) -> bool:
    return (
        facts.local_candidate is True
        and facts.ownership_supported is True
        and facts.writable is True
        and facts.mount_identity is not None
    )


@dataclass(frozen=True, slots=True)
class _NamespaceDirectoryPolicy:
    base: Path = field(repr=False)
    namespace: Path = field(repr=False)
    user_identity: bytes = field(repr=False)
    facts: _FilesystemEvidence = field(repr=False)

    def _verify_base(self) -> None:
        _directory_info(self.base)
        if _user_identity() != self.user_identity:
            raise _NamespaceError()
        current = _observe_scratch_filesystem(self.base)
        if not _usable(current) or current != self.facts:
            raise _NamespaceError()
        if os.name == "posix":
            _posix_ancestor_check(self.base)
        elif os.name == "nt":
            for ancestor in (self.base, *self.base.parents):
                _verify_ancestor_directory(ancestor)
        else:
            raise _NamespaceError()

    def _within_namespace(self, path: Path) -> None:
        if not path.is_absolute() or not path.is_relative_to(self.namespace):
            raise _NamespaceError()
        if ".." in path.parts or path.resolve(strict=False) != path:
            raise _NamespaceError()

    def create_directory(self, path: Path) -> None:
        self._verify_base()
        self._within_namespace(path)
        if path != self.namespace:
            self.verify_directory(path.parent)
        if os.name == "nt":
            _create_private_directory(path)
        elif os.name == "posix":
            path.mkdir(mode=0o700)
        else:
            raise _NamespaceError()
        self.verify_directory(path)

    def verify_directory(self, path: Path) -> None:
        try:
            self._verify_directory(path)
        except Exception:
            raise _NamespaceError() from None

    def verify_file(self, path: Path, *, fd: int | None = None) -> None:
        """Revalidate a private leaf using native file and filesystem evidence."""
        try:
            self._within_namespace(path)
            if path == self.namespace:
                raise _NamespaceError()
            if os.name == "nt":
                _verify_private_file(path, fd=fd)
            elif sys.platform in ("linux", "darwin"):
                actual = _observe_posix_file_filesystem(path, fd=fd)
                if not _usable(actual) or actual != self.facts:
                    raise _NamespaceError()
                if sys.platform == "darwin" and not _darwin_no_acl_grants(
                    path, path.lstat(), fd=fd
                ):
                    raise _NamespaceError()
            else:
                raise _NamespaceError()
        except Exception:
            raise _NamespaceError() from None

    def _verify_directory(self, path: Path) -> None:
        self._verify_base()
        self._within_namespace(path)
        for directory in (path, *(p for p in path.parents if p.is_relative_to(self.namespace))):
            info = _directory_info(directory)
            actual = _observe_scratch_filesystem(directory)
            if not _usable(actual) or actual != self.facts:
                raise _NamespaceError()
            if os.name == "nt":
                _verify_private_directory(directory)
            elif os.name == "posix":
                if info.st_uid != os.geteuid() or info.st_mode & 0o077:
                    raise _NamespaceError()
                if sys.platform == "darwin" and not _darwin_no_acl_grants(directory, info):
                    raise _NamespaceError()
            else:
                raise _NamespaceError()


def _open_namespace(base: Path, project: Path) -> _ScratchRoot:
    """Open or exclusively create a stable, verified candidate namespace.

    An unqualified storage candidate is an explicit uncertainty, not a
    global decision to block Recon or permission to switch locations.
    Never adopt, modify or remove an unrelated directory.
    """
    try:
        path = _namespace_path(base, project)
        facts = _observe_scratch_filesystem(base)
        if not _usable(facts):
            raise _NamespaceError()
        policy = _NamespaceDirectoryPolicy(base, path, _user_identity(), facts)
        policy._verify_base()
        try:
            path.lstat()
        except FileNotFoundError:
            try:
                return _ScratchRoot.create(path, directory_policy=policy)
            except _RootExistsError:
                # Another creator won exclusive mkdir. Reopen only a fully
                # verified, published root; never repair a partial directory.
                pass
        return _ScratchRoot.reopen(path, directory_policy=policy)
    except Exception:
        raise _NamespaceError() from None
