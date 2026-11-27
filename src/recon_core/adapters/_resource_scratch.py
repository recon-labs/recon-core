"""Private current-check temporary storage; no persistent recovery or leases."""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from recon_core.adapters._windows_scratch_security import _windows_ticket_identity


class _ScratchError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Owned scratch storage could not be verified.")


@dataclass(frozen=True, slots=True)
class _Identity:
    device: int
    inode: int


def _identity(info: os.stat_result) -> _Identity:
    if info.st_ino <= 0:
        raise _ScratchError()
    return _Identity(info.st_dev, info.st_ino)


def _object_identity(path: Path, info: os.stat_result, *, fd: int | None = None) -> _Identity:
    """Use full native Windows identity; preserve POSIX device/inode identity."""
    baseline = _identity(info)
    if fd is not None and _identity(os.fstat(fd)) != baseline:
        raise _ScratchError()
    if os.name == "nt":
        native = _Identity(
            *_windows_ticket_identity(path, directory=stat.S_ISDIR(info.st_mode), fd=fd)
        )
        if _identity(path.lstat()) != baseline:
            raise _ScratchError()
        return native
    return baseline


def _check_scratch_directory(path: Path) -> os.stat_result:
    info = path.lstat()
    if (
        not path.is_absolute()
        or path.resolve(strict=True) != path
        or not stat.S_ISDIR(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    ):
        raise _ScratchError()
    return info


def _check_scratch_base(base: Path) -> _Identity:
    """Check the selected existing cooperative parent, not filesystem locality."""

    info = _check_scratch_directory(base)
    if os.name == "posix":
        uid = os.geteuid()
        for directory in (base, *base.parents):
            parent = _check_scratch_directory(directory)
            if parent.st_uid not in (0, uid):
                raise _ScratchError()
            if parent.st_mode & 0o022 and not parent.st_mode & stat.S_ISVTX:
                raise _ScratchError()
    elif os.name == "nt":
        from recon_core.adapters._windows_scratch_security import _verify_ancestor_directory

        _verify_ancestor_directory(base)
    else:
        raise _ScratchError()
    return _object_identity(base, info)


def _check_private_scratch(path: Path) -> _Identity:
    info = _check_scratch_directory(path)
    if os.name == "posix":
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise _ScratchError()
        if sys.platform == "darwin":
            from recon_core.adapters._darwin_scratch_security import _darwin_no_acl_grants

            if not _darwin_no_acl_grants(path, info):
                raise _ScratchError()
    elif os.name == "nt":
        from recon_core.adapters._windows_scratch_security import _verify_private_directory

        _verify_private_directory(path)
    else:
        raise _ScratchError()
    return _object_identity(path, info)


@dataclass(slots=True)
class _CheckScratch:
    """One current private directory; no adoption, persistent ticket or sweep."""

    path: Path = field(repr=False)
    _base_identity: _Identity = field(repr=False)
    _directory_identity: _Identity = field(repr=False)
    _removed: bool = field(default=False, init=False, repr=False)

    def cleanup(self, *, native_closed: bool) -> None:
        """Remove current storage only after the owning native session closed."""

        if native_closed is not True:
            raise _ScratchError()
        if self._removed:
            return
        try:
            if (
                _check_scratch_base(self.path.parent) != self._base_identity
                or _check_private_scratch(self.path) != self._directory_identity
            ):
                raise _ScratchError()
            # Standard rmtree does not traverse directory symlinks (or Windows
            # junctions). This is a trusted cooperative parent, not a hostile
            # same-user or privileged mount/rename sandbox.
            shutil.rmtree(self.path)
            self._removed = True
        except Exception:
            raise _ScratchError() from None


def _create_check_scratch(base: Path) -> _CheckScratch:
    """Exclusively create one private empty directory under the selected base.

    A failed or interrupted creation may leave residue. Never sweep or adopt
    existing directories, and never switch to a different temporary location.
    """

    try:
        base_identity = _check_scratch_base(base)
        if os.name == "nt":
            from recon_core.adapters._windows_scratch_security import _create_private_directory

            # The protected-DACL primitive works on supported older Python
            # versions too, unlike relying on Windows mkdir's mode argument.
            path = base / ("recon-scratch-" + uuid4().hex)
            _create_private_directory(path)
        else:
            path = Path(tempfile.mkdtemp(prefix="recon-scratch-", dir=base))
            if sys.platform == "darwin":
                from recon_core.adapters._darwin_scratch_security import _darwin_no_acl_grants

                info = _check_scratch_directory(path)
                if not _darwin_no_acl_grants(path, info):
                    # Only the newly created empty directory is modified.
                    subprocess.run(
                        ["/bin/chmod", "-N", str(path)],
                        capture_output=True,
                        check=True,
                        timeout=15,
                    )
        identity = _check_private_scratch(path)
        if _check_scratch_base(base) != base_identity:
            raise _ScratchError()
        return _CheckScratch(path, base_identity, identity)
    except Exception:
        raise _ScratchError() from None
