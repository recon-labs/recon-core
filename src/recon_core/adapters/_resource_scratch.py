"""Private scratch coordination on a caller-qualified local filesystem.

This collaborator does not qualify filesystem locking semantics, Windows ACLs
or the stable per-project namespace. Those are prerequisites to activation.
Only cooperative owners using the root lock may change the namespace.
"""

import ctypes as ct
import errno
import os
import stat
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, auto
from importlib import import_module
from pathlib import Path
from typing import IO, Protocol
from uuid import UUID, uuid4

from recon_core.adapters._windows_scratch_security import _api, _libraries


class _ScratchError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Owned scratch storage could not be verified.")


class _BusyError(_ScratchError):
    pass


class _Recovery(Enum):
    REMOVED = auto()
    LIVE = auto()
    RETAINED = auto()


@dataclass(frozen=True, slots=True)
class _RecoverySummary:
    removed: int = 0
    live: int = 0
    retained: int = 0
    complete: bool = True


@dataclass(frozen=True, slots=True)
class _Identity:
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class _RootTicket:
    path: Path = field(repr=False)
    nonce: UUID
    identity: _Identity
    lock_identity: _Identity


@dataclass(frozen=True, slots=True)
class _SessionTicket:
    path: Path = field(repr=False)
    nonce: UUID
    identity: _Identity
    parent_identity: _Identity
    worker_identity: _Identity
    spill_identity: _Identity


def _identity(info: os.stat_result) -> _Identity:
    if info.st_ino <= 0:
        raise _ScratchError()
    return _Identity(info.st_dev, info.st_ino)


def _inspect(
    path: Path, *, directory: bool, policy: "_DirectoryPolicy | None" = None
) -> os.stat_result:
    info = path.lstat()
    if (
        not path.is_absolute()
        or path.resolve(strict=True) != path
        or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
        or (not directory and info.st_nlink != 1)
    ):
        raise _ScratchError()
    # POSIX ownership/mode proof only. Windows ACL qualification remains
    # an explicit prerequisite of the eventual runtime root provider.
    if os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise _ScratchError()
    if not directory and policy is not None:
        policy.verify_file(path)
    return info


def _write_new(path: Path, data: bytes, policy: "_DirectoryPolicy | None" = None) -> None:
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
        if policy is not None:
            policy.verify_file(path, fd=stream.fileno())
        stream.write(data)


# The largest native file identity component is Windows FILE_ID_128.
# Bound marker reads by the closed schema, not by directory contents.
_IDENTITY_DIGITS = 39
_IDENTITY_MAX = (1 << 128) - 1


def _read_marker(
    path: Path,
    *,
    prefix: bytes,
    nonces: int,
    identities: int,
    policy: "_DirectoryPolicy | None" = None,
) -> list[str]:
    maximum = len(prefix) + nonces * 33 + identities * 2 * (1 + _IDENTITY_DIGITS)
    info = _inspect(path, directory=False, policy=policy)
    if not 0 < info.st_size <= maximum:
        raise _ScratchError()
    with path.open("rb") as stream:
        if _identity(os.fstat(stream.fileno())) != _identity(info):
            raise _ScratchError()
        if policy is not None:
            policy.verify_file(path, fd=stream.fileno())
        data = stream.read(maximum + 1)
    if len(data) != info.st_size or len(data) > maximum:
        raise _ScratchError()
    fields = data.decode("ascii").split(":")
    if fields[0] != prefix.decode("ascii") or len(fields) != 1 + nonces + 2 * identities:
        raise _ScratchError()
    return fields[1:]


def _marker_nonce(value: str) -> UUID:
    if len(value) != 32:
        raise _ScratchError()
    nonce = UUID(hex=value)
    if nonce.hex != value:
        raise _ScratchError()
    return nonce


def _marker_identity(device: str, inode: str) -> _Identity:
    if any(
        not 1 <= len(value) <= _IDENTITY_DIGITS or not value.isascii() or not value.isdecimal()
        for value in (device, inode)
    ):
        raise _ScratchError()
    result = _Identity(int(device), int(inode))
    if (
        not 0 <= result.device <= _IDENTITY_MAX
        or not 0 < result.inode <= _IDENTITY_MAX
        or (str(result.device), str(result.inode)) != (device, inode)
    ):
        raise _ScratchError()
    return result


def _marker(
    path: Path, expected: bytes, policy: "_DirectoryPolicy | None" = None
) -> None:
    info = _inspect(path, directory=False, policy=policy)
    if info.st_size != len(expected):
        raise _ScratchError()
    with path.open("rb") as stream:
        if _identity(os.fstat(stream.fileno())) != _identity(info):
            raise _ScratchError()
        if policy is not None:
            policy.verify_file(path, fd=stream.fileno())
        if stream.read(len(expected) + 1) != expected:
            raise _ScratchError()


def _identity_text(identity: _Identity) -> str:
    return f"{identity.device}:{identity.inode}"


def _root_marker(ticket: _RootTicket) -> bytes:
    return (
        f"RC-SCRATCH-1:{ticket.nonce.hex}:{_identity_text(ticket.identity)}:"
        f"{_identity_text(ticket.lock_identity)}"
    ).encode("ascii")


def _session_marker(root: _RootTicket, session: _SessionTicket) -> bytes:
    return (
        f"RC-SESSION-1:{root.nonce.hex}:{session.nonce.hex}:"
        + ":".join(
            _identity_text(identity)
            for identity in (
                session.identity,
                session.parent_identity,
                session.worker_identity,
                session.spill_identity,
            )
        )
    ).encode("ascii")


class _LockOverlapped(ct.Structure):
    # OVERLAPPED's union is represented by its two DWORD offset fields.
    _fields_ = [
        ("internal", ct.c_size_t),
        ("internal_high", ct.c_size_t),
        ("offset", ct.c_uint32),
        ("offset_high", ct.c_uint32),
        ("event", ct.c_void_p),
    ]


def _lock_exclusive(fd: int) -> None:
    """Only actual native lock conflict is evidence of an existing owner."""
    if os.name == "nt":
        kernel, _ = _libraries()
        handle = import_module("msvcrt").get_osfhandle(fd)
        lock = _api(
            kernel,
            "LockFileEx",
            ct.c_int,
            ct.c_void_p,
            ct.c_uint32,
            ct.c_uint32,
            ct.c_uint32,
            ct.c_uint32,
            ct.POINTER(_LockOverlapped),
        )
        state = _LockOverlapped()
        # Exclusive, fail immediately, offset 0, one byte. Closing the
        # noninherited handle releases the lock, including on process death.
        if not lock(handle, 3, 0, 1, 0, ct.byref(state)):
            if import_module("ctypes").get_last_error() == 33:  # ERROR_LOCK_VIOLATION
                raise _BusyError()
            raise _ScratchError()
    elif os.name == "posix":
        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                raise _BusyError() from None
            raise _ScratchError() from None
    else:
        raise _ScratchError()


class _FileLease:
    """An independent non-inherited OS lock on a pre-existing single-byte file."""

    def __init__(self, stream: IO[bytes]) -> None:
        self._stream = stream

    @classmethod
    def acquire(
        cls, path: Path, expected: _Identity, policy: "_DirectoryPolicy | None" = None
    ) -> "_FileLease":
        info = _inspect(path, directory=False, policy=policy)
        if info.st_size != 1 or _identity(info) != expected:
            raise _ScratchError()
        stream = path.open("r+b", buffering=0)
        try:
            if _identity(os.fstat(stream.fileno())) != _identity(info):
                raise _ScratchError()
            if policy is not None:
                policy.verify_file(path, fd=stream.fileno())
            stream.seek(0)
            try:
                _lock_exclusive(stream.fileno())
            except OSError:
                raise _ScratchError() from None
            stream.seek(0)
            if stream.read(1) != b"\0":
                raise _ScratchError()
            return cls(stream)
        except BaseException:
            stream.close()
            raise

    def release(self) -> None:
        self._stream.close()


class _ParentLease:
    def __init__(self, root: "_ScratchRoot", ticket: _SessionTicket, lock: _FileLease) -> None:
        self._root = root
        self.ticket = ticket
        self._lock = lock

    def release(self) -> None:
        """Abandon ownership; never delete files."""
        self._lock.release()

    def cleanup(self, *, worker_exit_confirmed: bool) -> _Recovery:
        if worker_exit_confirmed is not True:
            return _Recovery.RETAINED
        try:
            with self._root._guard():
                self.release()
                return self._root._recover_locked(self.ticket)
        except (OSError, RuntimeError, ValueError):
            return _Recovery.RETAINED


class _DirectoryPolicy(Protocol):
    def create_directory(self, path: Path) -> None: ...
    def verify_directory(self, path: Path) -> None: ...
    def verify_file(self, path: Path, *, fd: int | None = None) -> None: ...


class _ScratchRoot:
    """Root lock serializes publication, claims and deletion, not queries."""

    def __init__(
        self, ticket: _RootTicket, *, directory_policy: _DirectoryPolicy | None = None
    ) -> None:
        self.ticket = ticket
        self._directory_policy = directory_policy

    @classmethod
    def create(
        cls, path: Path, *, directory_policy: _DirectoryPolicy | None = None
    ) -> "_ScratchRoot":
        """Create an exclusive root, never adopt an arbitrary existing directory."""
        try:
            if not path.is_absolute() or path.parent.resolve(strict=True) != path.parent:
                raise _ScratchError()
            if directory_policy is None:
                path.mkdir(mode=0o700)
            else:
                directory_policy.create_directory(path)
            _write_new(path / "root.lock", b"\0", directory_policy)
            ticket = _RootTicket(
                path,
                uuid4(),
                _identity(_inspect(path, directory=True)),
                _identity(_inspect(path / "root.lock", directory=False, policy=directory_policy)),
            )
            _write_new(path / "owner", _root_marker(ticket), directory_policy)
            return cls(ticket, directory_policy=directory_policy)
        except (OSError, RuntimeError, ValueError):
            raise _ScratchError() from None

    @classmethod
    def reopen(
        cls, path: Path, *, directory_policy: _DirectoryPolicy | None = None
    ) -> "_ScratchRoot":
        """Reconstruct a known namespace on caller-qualified storage.

        A name or directory alone is not proof. Do not repair incomplete
        roots, replace their locks, or adopt directories without markers.
        """
        try:
            _inspect(path, directory=True)
            if directory_policy is not None:
                directory_policy.verify_directory(path)
            nonce, dev, ino, lock_dev, lock_ino = _read_marker(
                path / "owner",
                prefix=b"RC-SCRATCH-1",
                nonces=1,
                identities=2,
                policy=directory_policy,
            )
            root = cls(
                _RootTicket(
                    path,
                    _marker_nonce(nonce),
                    _marker_identity(dev, ino),
                    _marker_identity(lock_dev, lock_ino),
                ),
                directory_policy=directory_policy,
            )
            with root._guard():
                pass
            return root
        except (OSError, RuntimeError, ValueError):
            raise _ScratchError() from None

    def _discover_session(self, path: Path) -> _SessionTicket:
        _inspect(path, directory=True)
        if self._directory_policy is not None:
            self._directory_policy.verify_directory(path)
        root_nonce, nonce, *values = _read_marker(
            path / "owner",
            prefix=b"RC-SESSION-1",
            nonces=2,
            identities=4,
            policy=self._directory_policy,
        )
        if _marker_nonce(root_nonce) != self.ticket.nonce or path.name != nonce:
            raise _ScratchError()
        identities = tuple(
            _marker_identity(values[i], values[i + 1]) for i in range(0, len(values), 2)
        )
        ticket = _SessionTicket(
            path, _marker_nonce(nonce), identities[0], identities[1], identities[2], identities[3]
        )
        self._verify_session(ticket)
        return ticket

    def recover_abandoned(self) -> _RecoverySummary:
        """Stream a best-effort pass over this namespace only.

        Reacquire root coordination for each candidate. Concurrent changes
        may be seen on a later pass; never assert all abandoned data is gone.
        Counts are safe for diagnostics; names and values are not returned.
        """
        removed = live = retained = 0
        try:
            with self._guard():
                pass
            with os.scandir(self.ticket.path) as entries:
                for entry in entries:
                    if entry.name in ("root.lock", "owner"):
                        continue
                    with self._guard():
                        try:
                            ticket = self._discover_session(self.ticket.path / entry.name)
                            result = self._recover_locked(ticket)
                        except (OSError, RuntimeError, ValueError):
                            result = _Recovery.RETAINED
                    if result is _Recovery.REMOVED:
                        removed += 1
                    elif result is _Recovery.LIVE:
                        live += 1
                    else:
                        retained += 1
        except (OSError, RuntimeError, ValueError):
            return _RecoverySummary(removed, live, retained, complete=False)
        return _RecoverySummary(removed, live, retained)

    def _verify_root(self) -> None:
        if self._directory_policy is not None:
            self._directory_policy.verify_directory(self.ticket.path)
        if _identity(_inspect(self.ticket.path, directory=True)) != self.ticket.identity:
            raise _ScratchError()
        _marker(self.ticket.path / "owner", _root_marker(self.ticket), self._directory_policy)
        if (
            _identity(
                _inspect(self.ticket.path / "root.lock", directory=False, policy=self._directory_policy)
            )
            != self.ticket.lock_identity
        ):
            raise _ScratchError()

    @contextmanager
    def _guard(self) -> Iterator[None]:
        self._verify_root()
        # Internal coordination deadline; no workload deadline.
        deadline = time.monotonic() + 5
        while True:
            try:
                lock = _FileLease.acquire(
                    self.ticket.path / "root.lock", self.ticket.lock_identity, self._directory_policy
                )
                break
            except _BusyError:
                if time.monotonic() >= deadline:
                    raise _ScratchError() from None
                time.sleep(0.02)
        try:
            self._verify_root()
            yield
        finally:
            lock.release()

    def _verify_session(self, ticket: _SessionTicket) -> None:
        if self._directory_policy is not None:
            self._directory_policy.verify_directory(ticket.path)
            self._directory_policy.verify_directory(ticket.path / "spill")
        if (
            ticket.path != self.ticket.path / ticket.nonce.hex
            or _identity(_inspect(ticket.path, directory=True)) != ticket.identity
            or ticket.identity.device != self.ticket.identity.device
        ):
            raise _ScratchError()
        _marker(ticket.path / "owner", _session_marker(self.ticket, ticket), self._directory_policy)
        spill = _inspect(ticket.path / "spill", directory=True)
        if (
            _identity(spill) != ticket.spill_identity
            or spill.st_dev != ticket.identity.device
            or os.path.ismount(ticket.path / "spill")
            or _identity(
                _inspect(ticket.path / "parent.lock", directory=False, policy=self._directory_policy)
            )
            != ticket.parent_identity
            or _identity(
                _inspect(ticket.path / "worker.lock", directory=False, policy=self._directory_policy)
            )
            != ticket.worker_identity
        ):
            raise _ScratchError()

    def create_session(self) -> _ParentLease:
        try:
            with self._guard():
                nonce = uuid4()
                path = self.ticket.path / nonce.hex
                if self._directory_policy is None:
                    path.mkdir(mode=0o700)
                    (path / "spill").mkdir(mode=0o700)
                else:
                    self._directory_policy.create_directory(path)
                    self._directory_policy.create_directory(path / "spill")
                _write_new(path / "parent.lock", b"\0", self._directory_policy)
                _write_new(path / "worker.lock", b"\0", self._directory_policy)
                ticket = _SessionTicket(
                    path,
                    nonce,
                    _identity(_inspect(path, directory=True)),
                    _identity(
                        _inspect(path / "parent.lock", directory=False, policy=self._directory_policy)
                    ),
                    _identity(
                        _inspect(path / "worker.lock", directory=False, policy=self._directory_policy)
                    ),
                    _identity(_inspect(path / "spill", directory=True)),
                )
                parent = _FileLease.acquire(
                    path / "parent.lock", ticket.parent_identity, self._directory_policy
                )
                try:
                    # Publish only after the parent's lease is held.
                    _write_new(path / "owner", _session_marker(self.ticket, ticket), self._directory_policy)
                    self._verify_session(ticket)
                    return _ParentLease(self, ticket, parent)
                except BaseException:
                    parent.release()
                    raise
        except (OSError, RuntimeError, ValueError):
            # Partial creation is retained, not swept without complete proof.
            raise _ScratchError() from None

    def claim_worker(self, ticket: _SessionTicket) -> _FileLease:
        try:
            with self._guard():
                self._verify_session(ticket)
                try:
                    abandoned = _FileLease.acquire(
                        ticket.path / "parent.lock", ticket.parent_identity, self._directory_policy
                    )
                except _BusyError:
                    return _FileLease.acquire(
                        ticket.path / "worker.lock", ticket.worker_identity, self._directory_policy
                    )
                abandoned.release()
                raise _ScratchError()
        except (OSError, RuntimeError, ValueError):
            raise _ScratchError() from None

    def recover(self, ticket: _SessionTicket) -> _Recovery:
        """Only recover a positively identified inactive session."""
        try:
            with self._guard():
                return self._recover_locked(ticket)
        except (OSError, RuntimeError, ValueError):
            return _Recovery.RETAINED

    def _recover_locked(self, ticket: _SessionTicket) -> _Recovery:
        self._verify_session(ticket)
        try:
            parent = _FileLease.acquire(
                ticket.path / "parent.lock", ticket.parent_identity, self._directory_policy
            )
        except _BusyError:
            return _Recovery.LIVE
        try:
            try:
                worker = _FileLease.acquire(
                    ticket.path / "worker.lock", ticket.worker_identity, self._directory_policy
                )
            except _BusyError:
                return _Recovery.LIVE
            try:
                self._validate_deletion(ticket)
            finally:
                worker.release()
        finally:
            parent.release()
        # Both handles must be closed before deletion on Windows. The root
        # lock is still held; no cooperating late worker can claim the session.
        self._verify_session(ticket)
        with os.scandir(ticket.path / "spill") as entries:
            for entry in entries:
                path = ticket.path / "spill" / entry.name
                self._verify_spill_file(path, ticket)
                path.unlink()
        (ticket.path / "spill").rmdir()
        for name in ("parent.lock", "worker.lock", "owner"):
            path = ticket.path / name
            _inspect(path, directory=False, policy=self._directory_policy)
            path.unlink()
        ticket.path.rmdir()
        return _Recovery.REMOVED

    def _validate_deletion(self, ticket: _SessionTicket) -> None:
        expected = {"owner", "parent.lock", "worker.lock", "spill"}
        with os.scandir(ticket.path) as entries:
            for entry in entries:
                if entry.name not in expected:
                    raise _ScratchError()
                expected.remove(entry.name)
        if expected:
            raise _ScratchError()
        # Validate the whole directory before any removal, with bounded
        # memory. Recheck each entry during deletion under root coordination.
        with os.scandir(ticket.path / "spill") as entries:
            for entry in entries:
                self._verify_spill_file(ticket.path / "spill" / entry.name, ticket)

    def _verify_spill_file(self, path: Path, ticket: _SessionTicket) -> None:
        # DuckDB spill files need not have owner-only modes when the enclosing
        # private directory is inaccessible to other users. Never follow links,
        # hardlinks, reparse points, unexpected directories or special files.
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_dev != ticket.identity.device
            or path.resolve(strict=True) != path
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            or (os.name == "posix" and info.st_uid != os.getuid())
        ):
            raise _ScratchError()
        if self._directory_policy is not None:
            self._directory_policy.verify_file(path)
